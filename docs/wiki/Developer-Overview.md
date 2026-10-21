# Developer Overview

## What it is

A Python 3.10+ desktop app (Tk, ttk) for acoustic-environment screening. The package is `audio_enviro_fingerprint` under `src/`. It has no native code and no network use. Dependency: NumPy. Packaging is PyInstaller (windowed bundle), built for Windows and Linux in CI.

## Design decisions (and why)

**Two identities for one file.** The SHA-256 of the original bytes identifies the evidence. The acoustic fingerprint is a separate, versioned summary of the features (`aefp-1`). Keeping them apart means a feature change does not change the evidence hash, and a hash match does not imply two features are the same.

**Read only, no downmix.** Channel 1 is used directly (`audio_io.load_wav`). No mixing is applied, so no phase cancellation can hide content. The test `test_selects_first_channel_without_phase_cancellation` covers this.

**Strict input.** Only uncompressed integer PCM WAV is accepted (8, 16, 24 and 32-bit). Non-PCM and truncated payloads are rejected (`test_rejects_non_pcm_wave`, `test_rejects_truncated_pcm_payload`). Silent guessing is worse than a refusal for evidence work.

**Hash before and after load.** `app.py` hashes the file before and after decoding, and refuses if they differ. Export hashes the file again and refuses if it has changed.

**Explainable outputs, not verdicts.** Transitions report per-feature deltas (`evidence`). Comparison reports per-feature differences and an explicitly uncalibrated score. Nothing is presented as a probability or a location match.

**Versioned canonical serialisation.** `make_fingerprint()` builds a canonical JSON (sorted keys, no NaN) and hashes it. Comparison refuses mismatched versions (`ValueError`). Changing a feature means bumping the version.

**Fixed, documented frequency bands.** `methods/spectral.py` defines the bands explicitly (`BANDS`), so band power is comparable between runs.

**Local SQLite for notes.** `case_store.py` stores examiner notes and evidence records in one SQLite file. Each note is tied to the source SHA-256, with a uniqueness rule on (path, hash).

## Method

```
WAV file ──► sha256_file() ──────────────────────────► evidence record (SHA-256)
   │
   ▼
load_wav()  (PCM decode, channel 1, float samples, sample rate)
   │
   ▼
analyze_audio(frame 2.0 s, hop 1.0 s)
   ├─ rms_dbfs per frame                  methods/noise.py
   ├─ describe_spectrum per frame         methods/spectral.py (centroid, flatness, BANDS)
   └─ frame_level_summary                 methods/noise.py
   │
   ├──► detect_transitions(threshold 0.35)   transitions.py (adjacent-frame deltas, evidence)
   │
   └──► make_fingerprint()  ──► canonical JSON (aefp-1) ──► SHA-256 digest
                                     │
                       compare_fingerprints()  (per-feature diff, exp(-RMS) score)

RT60: estimate_t20() (methods/reverberation.py), Schroeder curve on impulse responses
```

## Threads

Everything runs on the Tk main thread. The app has no worker threads, so a large file blocks the window until analysis finishes.

## Data

- `AudioData` (`audio_io.py:12`): samples, sample rate, channel info
- `FrameFeature`, `AnalysisResult` (`features.py:14`, `:23`): per-frame values and the result. `to_dict()` gives the export form
- `Fingerprint` (`fingerprint.py:13`): version, features, digest, canonical JSON
- `Transition` (`transitions.py:9`): time, features, deltas as evidence
- `Comparison` (`comparison.py:9`): score, differences, explanation

See [[Developer-Code-Map]] for locations and [[Developer-Conventions]] for the rules.
