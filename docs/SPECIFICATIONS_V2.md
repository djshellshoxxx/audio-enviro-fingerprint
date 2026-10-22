# Engineering specifications — v0.2 additions

Supplements `SPECIFICATIONS.md`. All methods are descriptive and unvalidated forensically; each returns a `method` id and visible supporting values. Pure-NumPy modules have no UI dependency and may be reused independently.

## Module map

| Module | Contract |
|---|---|
| `audio_io.load_wav(path) -> AudioData` | RIFF/RF64 parser. PCM 8/16/24/32-bit, IEEE float 32/64, `WAVE_FORMAT_EXTENSIBLE`. Rejects other codecs, NaN/Inf floats, truncated or partial-frame payloads. `samples` = channel 1; `all_channels` (n×ch) retained; `channel(i)`. No downmix. |
| `methods/musical.py` | `hz_to_note`, `dominant_tones`, `chromagram`, `estimate_key`, `pitch_track`, `estimate_tempo`, `musical_summary` (id `musical-v1`). |
| `methods/hum.py` | `detect_mains_hum` (id `mains-hum-v1`): 50/60 Hz harmonic prominence vs adjacent spectrum; not an ENF time series. |
| `recurrence.py` | `find_recurrences(a, b=None, threshold, departure, min_gap_seconds)` (id `recurrence-v1`). |
| `multichannel.py` | `analyze_channels`, `channel_pair_metrics` (id `multichannel-v1`). |
| `reference.py` | `ReferenceMetadata`, `review_reference` (schema `aefp-reference-1`). |
| `spectrogram.py` | `compute_spectrogram`, `colorize`, `encode_png`. |
| `report.py` | `build_report`, `write_report`, `verify_report` (schema `aefp-report-2`). |
| `pipeline.py` | `analyze_file` (hash pinned before/after; fails if source changes), `report_sections`, `full_report`. |
| `cli.py` / `launcher.py` | Args → CLI; no args → GUI. |

## Method definitions

**Musical (`musical-v1`).**
- Note naming: MIDI = 69 + 12·log2(f/A4); nearest integer, signed cents. A4 configurable (default 440 Hz).
- Dominant tones: Welch-averaged power spectrum (~1 Hz resolution, 50 % overlap Hann), local maxima 20–4000 Hz, log-parabolic peak interpolation, peaks <3 Hz apart merged; level reported in dB above band median.
- Key: 12-bin chroma (65–2000 Hz) summed over time, correlated (Pearson) with Krumhansl–Kessler major/minor profiles over 24 keys. Reports best key, correlation, next 3 alternatives. Indeterminate for flat/silent chroma.
- Pitch: YIN cumulative-mean-normalized difference, threshold 0.15, 60–1000 Hz, 64 ms frames/32 ms hop; `confidence = 1 − CMND`. Summary uses frames with confidence >0.7 (median f0).
- Tempo: spectral-flux onset envelope (1024/256 STFT), autocorrelation over 40–220 BPM with log-Gaussian prior at 120 BPM (octave-error suppression). `confidence` = normalized autocorrelation peak (not a probability).
- Limitation: designed for monophonic/stationary material; polyphonic speech/noise yields low confidence.

**Mains hum.** Mean power spectrum (32768-pt Hann segments). For base 50 and 60 Hz, harmonics 1–6: peak within ±0.5 Hz over median of the 2–8 Hz flanking ring (dB). Detected if mean of first three harmonics >10 dB. Reports the base with higher prominence.

**Recurrence.** Per analysis frame a vector of fixed-scale normalized features: RMS/15 dB, log2(centroid)/1.5, flatness/0.25, each band power/15 dB. Distance = RMS of component differences (uncalibrated). Within a recording, frame *j* matches earlier frame *i* if `j−i ≥ gap`, `D(i,j) ≤ threshold` (default 0.25), and some intervening frame has `D(i,k) ≥ departure` (default 0.6). Consecutive matched frames merge into one segment ID with mean/min distance, departure peak, and mean signed per-feature differences. Cross-recording mode matches every frame of A to the best frame of B without a departure test. Constants: `CONFOUNDERS` is emitted in every report. Validation required before any threshold is trusted (see VALIDATION.md).

**Multichannel.** Per channel: RMS/peak dBFS and an independent fingerprint. Channel 1 vs k: zero-lag correlation (negative = opposite polarity), peak cross-correlation lag within ±1.5 ms (FFT), level difference, side-to-mid ratio.

**Reference acquisition.** Required fields: location id, UTC time, operator, recorder, microphone, input chain, channel assignment, placement, orientation, height, source signal, occupancy/activity, authority/consent. Checks: required metadata (fail), duration (≥60 s pass, ≥20 s warn), sample rate (≥32 kHz pass, ≥16 kHz warn), clipping (>0.1 % full-scale samples fail), level, repeats, calibration (warn). Overall = worst status. Records are append-only in SQLite and bound to the evidence SHA-256. A self-reported label never produces a match.

**Manual markers.** Append-only revisions `(marker_key, revision)`; deletion is a tombstone revision; history is exportable.

**Report manifest.** `body_sha256` = SHA-256 of canonical JSON (sorted keys, compact separators, no NaN) of everything except `manifest`. `verify` also re-hashes the evidence at `source_path` when present. Detects modification; it is not a signature and offers no authenticity.

## CLI

```
audio-enviro-fingerprint analyze FILE.wav [-o report.json] [--no-musical]
audio-enviro-fingerprint compare A.wav B.wav
audio-enviro-fingerprint recurrence A.wav B.wav     # where B's environment appears in A
audio-enviro-fingerprint spectrogram FILE.wav out.png
audio-enviro-fingerprint verify report.json         # exit 2 on mismatch
```
Exit codes: 0 ok, 1 input/IO error, 2 verification mismatch.

## GUI

Tabs: Analysis (timeline with transitions and recurrence spans), Spectrogram (click sets note time, PNG export), Musical, Recurrence, Channels, Reference (guided form + review), Notes & Markers. Analysis runs on a worker thread with progress; results are applied on the UI thread. `AEFP_SMOKE_TEST=1` analyzes a synthetic stereo file through all tabs and exits non-zero on failure (used by CI on every OS). `AEFP_HOME` overrides the case database directory.

## Packaging and release

CI matrix: ubuntu-24.04 (tar.gz), windows-latest (zip), macos-latest/arm64 (zip of `.app`). Each job: unit tests → PyInstaller → packaged smoke test → archive → artifact. A tag `v*` triggers the `release` job (SHA256SUMS + GitHub Release; tags containing `-beta/-rc/-alpha` are prereleases). Builds are unsigned.

## Known gaps

Full streaming decode is not implemented; whole file decoded in memory; no code signing/notarization; Intel macOS not built; thresholds uncalibrated; ENF, scene classification, and learned models not implemented.

## Completion audit additions — 2026-10-22

`load_audio` selects the strict native WAV parser for RIFF/RF64/WAV; other supported local files use the optional FFmpeg decoder. Its codec provenance is exported under `sections.audio.decoder`. No shell is used; protocol and demuxer allowlists exclude network and playlist inputs. A bounded temporary raw float file is removed on success or error. The decoded size cap fails closed rather than returning a partial recording.

Recurrence computes one query column at a time: linear working memory in frame count (time remains quadratic). Existing distances, thresholds and result semantics are preserved.

`analyze_file(..., cancel_event=threading.Event())` raises `AnalysisCancelled` and returns no partial result. GUI Cancel sets the event; the last completed analysis remains visible. Checkpoints cover stage boundaries and hashing/frame/recurrence loops. Decoder and musical stages are not immediately interruptible.

Report and spectrogram exports use atomic replacement and reject destinations resolving to the source or sharing its inode. Marker revisions cannot change evidence ownership. Note and marker timestamps must be finite and nonnegative.

Implementation references: [FFmpeg stream selection and options](https://ffmpeg.org/ffmpeg.html), [ffprobe JSON output and stream metadata](https://ffmpeg.org/ffprobe.html).

## Branch reconciliation and v0.3 beta

The active application retains v0.2 musical/hum/spectrogram UI modules while porting useful older work individually. `fingerprint.py` now uses the older branch's `aefp-2` canonical serialization: round floats to six decimal places and normalize negative zero. New hashes differ from `aefp-1`; comparisons reject mixed versions. Rounding reduces platform drift but cannot guarantee equality at rounding boundaries.

`comparison-symmetric-v2` normalizes centroid differences by the maximum absolute centroid of both recordings (at least 100 Hz), so swapping input order preserves the score. Other existing scales and the exponential RMS score remain unchanged. The explicit method identifier distinguishes changed scores from earlier comparison output.

`catalog.cluster_recordings(paths, max_distance=0.25)` analyzes 1–64 unique local paths, releases each decoded recording, compares every fingerprint pair, then merges the closest groups only when their maximum cross-group distance is at most the threshold. Distance is `1 - score`. Deterministic sorted input and tie ordering produce stable groups; all source hashes, decoder provenance, feature differences and pair explanations are emitted. Groups indicate descriptor similarity, not room/device identity. CLI: `audio-enviro-fingerprint cluster A.wav B.wav C.flac --max-distance 0.25`.

Reference quality review additionally includes the older branch's DC-offset and silent-block/dropout checks. GUI reports include acquisition records and full marker revision history alongside current markers. Failed imports retain the previous evidence binding, preventing subsequent notes from attaching to a rejected file.

See BENCHMARK_PROTOCOL.md for the ported synthetic benchmark and the outstanding field-data protocol. Broader legacy branch consolidation is not complete; incompatible segmentation, stores and GUI variants require deliberate comparison before integration.
