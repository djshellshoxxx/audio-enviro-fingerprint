# Audio Environment Fingerprinter

Cross-platform desktop research beta for reproducible, explainable acoustic-environment screening. It computes a cryptographic hash of the original file separately from a versioned acoustic feature fingerprint. Every result shows the measurements behind it.

## Features

- **Input:** PCM, IEEE-float and extensible WAV built in. FLAC, AIFF, OGG/Opus, MP3, RF64 and W64 via the optional `soundfile` backend, which is bundled in packaged builds. Decoder provenance is recorded and lossy sources are flagged. See [docs/AUDIO_INPUT.md](docs/AUDIO_INPUT.md).
- **Channels:** all channels are kept and one is selected for analysis (no downmix). Per-channel and inter-channel statistics support stereo and multichannel review.
- **Features:** framewise RMS level, spectral centroid, spectral flatness and fixed-band power. Background analysis with progress and cancel.
- **Transitions:** candidate change points with per-feature deltas, plus manual markers with reasoned edits, soft deletion and full revision history.
- **Environment recurrence:** segments between transitions, matched within and across recordings, with per-feature deltas and listed confounders. Runs are saved to the case database.
- **Explainable comparison:** per-feature raw and normalized differences, each feature's share of the distance, and a feature-group summary. The score is explicitly uncalibrated.
- **Known-location references:** a controlled-capture metadata form with checklist, quality grading and a caveated ranking against the reference catalog. See [docs/REFERENCE_ACQUISITION.md](docs/REFERENCE_ACQUISITION.md).
- **Evidence handling:** SHA-256 at import, re-checked after decoding and at export. Timestamped notes and markers bound to the evidence hash in SQLite.
- **Reports:** `aefp-report-2` JSON with a hash manifest, plus a verifier in the GUI and CLI.
- **Synthetic benchmark** and a validation protocol. See [docs/BENCHMARK_PROTOCOL.md](docs/BENCHMARK_PROTOCOL.md).
- **Experimental** Schroeder decay-slope RT60 estimate for measured impulse responses. This is not an ISO 3382 workflow.

This software does not identify a physical location, estimate the probability of a common location, or establish authenticity. Its output requires examiner review. Thresholds and the similarity score have not been validated on representative forensic datasets.

## Download (Windows standalone)

Each CI run on GitHub Actions ("Build beta") publishes:

- `audio-enviro-fingerprint-windows-standalone-<sha>`: a single `AudioEnvironmentFingerprinter-standalone.exe`. No installation or Python is needed.
- `audio-enviro-fingerprint-windows-<sha>` and `audio-enviro-fingerprint-linux-<sha>`: application folders. These start faster than the single-file exe.

The executables are unsigned. Windows SmartScreen may ask for confirmation on first launch.

## Run from source

Python 3.10+, NumPy and Tk are required. `soundfile` is optional and adds the codecs listed above.

```bash
python -m pip install -e ".[formats]"
python -m audio_enviro_fingerprint            # desktop app
aefp analyze recording.wav --out report.json  # headless CLI
aefp verify-report report.json --evidence recording.wav
aefp compare a.wav b.wav
aefp benchmark --quick
```

Case data is stored in `~/.audio-enviro-fingerprint/cases.sqlite3`. Set `AEFP_DATA_DIR` to override the location. Run the tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GUI tests run when a display is available. On headless Linux, use `xvfb-run`.

## Build

See [docs/BUILDING.md](docs/BUILDING.md). CI builds and smoke-tests the Windows (folder and single-file) and Linux bundles on their own operating systems.

## Documentation

- [Research notes and source register](docs/RESEARCH_NOTES.md)
- [Engineering and method specifications](docs/SPECIFICATIONS.md)
- [Audio input and provenance](docs/AUDIO_INPUT.md)
- [Reference acquisition protocol](docs/REFERENCE_ACQUISITION.md)
- [Benchmark and validation protocol](docs/BENCHMARK_PROTOCOL.md)
- [Validation and QA](docs/VALIDATION.md)
- [Code audit](docs/CODE_AUDIT.md)
- [Future feature backlog](docs/FUTURE_FEATURES.md)
- [Project status](PROJECT_STATUS.md)
