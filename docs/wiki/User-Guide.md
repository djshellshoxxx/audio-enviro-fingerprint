# User Guide

## Install and open

Use Python 3.10 or newer, NumPy and Tk. Run `python -m pip install -e .` followed by `python -m audio_enviro_fingerprint`. On Linux, install the distribution's Tk package if `tkinter` is unavailable. Native bundle details are in [BUILDING](../BUILDING.md).

Choose **Open audio…** or press **Ctrl+O**. Native input accepts integer PCM 8/16/24/32-bit WAV, IEEE float 32/64-bit WAV, WAVE_FORMAT_EXTENSIBLE and RF64. Optional local FFmpeg/ffprobe enables supported FLAC, MP3, Ogg/Opus and MPEG-4 audio codecs. Decoder provenance appears in reports. No downmix or resampling is performed.

The current limit is 512 MiB of decoded float64 channel samples. The decoder checks native WAV payload size before reading it. This is not a total-process memory guarantee or full streaming analysis. Unsupported/corrupt/oversized input is rejected; the last successful analysis is retained. Cancel requests stop at cooperative checkpoints, so a current decode or musical stage may finish first.

## Five workflow shortcuts

1. **Recent recordings:** reopen successfully analyzed files from the recent-recordings menu. Missing files report an error and retain the previous result.
2. **Quick analysis:** enable this option to skip key, tempo and pitch analysis when you only need environment descriptors. The Musical tab clearly shows that music was skipped; environment features and evidence hashes remain available.
3. **Time navigation:** enter seconds, `MM:SS` or `HH:MM:SS` in the note time field. Click the timeline or select a candidate to move to that time without retyping it. Times must be finite, nonnegative and within the recording.
4. **Edit selected marker:** select a marker, change its time and label, then save the edit. The store appends a revision and retains the original; deleting also appends a tombstone.
5. **Printable HTML export:** choose HTML when you need a readable report for review or printing. It includes evidence identity, descriptors, candidate findings and examiner records. The JSON export remains the machine-verifiable report; HTML is a human-readable view and is not a signed report.

## Review the seven tabs

- **Analysis:** evidence and fingerprint hashes, median descriptors, candidate transitions and a timeline.
- **Spectrogram:** time/frequency display; clicking places the note time. PNG export writes a separate file.
- **Musical:** heuristic tones, note names, key, pitch and tempo; mains-hum measurements disclose frequency resolution or unavailable short-recording results.
- **Recurrence:** candidates whose frame descriptors returned after an intervening departure. Cross-recording candidates do not require a departure.
- **Channels:** independent channel levels/fingerprints and channel-1-relative spatial metrics. A mono file has no inter-channel metrics.
- **Reference:** document operator, UTC capture time, location label, recording chain, placement, activity, consent/authority, calibration and repeats. Review quality before saving. A self-reported location label never proves a match.
- **Notes & Markers:** add timestamped observations and manual markers, bound to the current evidence hash. Marker changes retain revision history.

Single-channel methods select channel 1 explicitly. Default feature windows are 2 seconds with a 1-second hop. Levels are dBFS, not calibrated sound-pressure levels. Lower frame-level percentiles are not an isolated background-noise measurement.

## Compare and search

**Compare recording…** shows measured raw and normalized feature deltas plus an uncalibrated descriptive score. A larger score means closer descriptors, not a probability of shared location. Comparisons require matching fingerprint schema versions.

**Find environment in other recording…** searches another recording for candidates similar to the loaded recording's environment. Review both time ranges and possible background-source, device, gain and processing confounders.

## Export and verify

Export JSON to preserve evidence provenance, frame measurements, fingerprints, candidate findings, notes, acquisition records and marker history. The source is rehashed before report export; changed evidence prevents export. Exports refuse to overwrite evidence, its aliases or the active case database. Keep originals stable and read-only.

Headless examples:

```bash
python -m audio_enviro_fingerprint analyze recording.wav -o report.json --no-musical
python -m audio_enviro_fingerprint analyze recording.wav --format html -o report.html --no-musical
python -m audio_enviro_fingerprint verify report.json
python -m audio_enviro_fingerprint compare first.wav second.flac
python -m audio_enviro_fingerprint recurrence long.wav exemplar.wav
python -m audio_enviro_fingerprint spectrogram recording.wav spectrogram.png
python -m audio_enviro_fingerprint cluster first.wav second.wav --max-distance 0.25
python -m audio_enviro_fingerprint benchmark --quick --seed 1
```

CLI exit codes are 0 for success, 1 for input/IO failure and 2 for verification mismatch. Read `evidence_checked` as well as `manifest_ok`: a valid report body is distinct from verification of an available original file.

## Scope and interpretation

Candidate transitions and recurrences are places to review. The software does not identify a physical place, estimate the probability of a common place, detect all edits or authenticate recordings. The RT60 helper is experimental and only suitable for a separate measured impulse response; it is not ISO 3382 conformance. Synthetic benchmark success establishes software behavior, not forensic error rates. Representative field recordings and independent validation remain necessary.

At smaller window sizes, use each review tab’s vertical scrollbar or focus its canvas and use Page Up/Page Down/Home/End. Keyboard focus reveals off-screen controls; wide tables have their own horizontal scrollbars.
