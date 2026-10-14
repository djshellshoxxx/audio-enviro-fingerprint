# Audio Environment Fingerprinter

Cross-platform desktop beta for reproducible, explainable acoustic-environment screening. It computes a cryptographic hash of the original file separately from a versioned acoustic feature fingerprint.

## Beta scope

- Reads uncompressed integer PCM WAV (8, 16, 24, and 32 bit).
- Uses channel 1 for analysis. The source file is read only; no downmix is applied.
- Computes framewise RMS level, spectral centroid, spectral flatness, and fixed-band power descriptors.
- Marks candidate transitions from adjacent-frame feature differences and shows the measurements behind each candidate.
- Compares two acoustic fingerprints with per-feature differences and an explicitly uncalibrated descriptive score.
- Stores timestamped notes linked to the original evidence SHA-256 in a local SQLite database.
- Exports a JSON analysis record.
- Lets the examiner choose which channel to analyze (default 1); analysis runs in the background with progress and cancel.
- **Environment recurrence detection:** splits a recording at candidate transitions and flags segments whose environment departs and later returns, within one recording or across recordings, with thresholds, confounders and uncertainty.
- **Explainable comparison:** every feature's raw values, delta, normalized delta and share of the distance, grouped by spectral / level-noise / band power, with automatic confounder warnings. Compare two recordings or a recording against a stored reference.
- **Known-location reference acquisition:** guided metadata form and checklist, audio quality review, immutable SQLite records bound to the file SHA-256, and re-verification. A location label is never treated as proof.
- Includes an experimental Schroeder decay-slope RT60 estimate for impulse-response data. It is not an ISO 3382 measurement workflow.

This software does not identify a physical location, estimate the probability of a common location, or establish authenticity. It is a research beta and its output requires examiner review. The current change-point threshold and similarity score have not been validated on representative forensic datasets.

## Run from source

Python 3.10 or newer, NumPy, and Tk support are required.

```bash
python -m pip install -e .
python -m audio_enviro_fingerprint
```

On Linux, install the distribution's Tk package if `tkinter` is not included with Python. To run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Releases

Pushing a tag such as `v0.2.0-beta.1` runs the Windows and Linux builds and attaches the zipped application bundles and `SHA256SUMS.txt` to a GitHub pre-release.

## Build

The GitHub Actions workflow builds separate Windows and Linux application bundles. Each must be built on its target operating system. Local build instructions are in [docs/BUILDING.md](docs/BUILDING.md).

## Documentation

- [Research notes and source register](docs/RESEARCH_NOTES.md)
- [Engineering and method specifications](docs/SPECIFICATIONS.md)
- [Validation and QA plan](docs/VALIDATION.md)
- [Future feature backlog](docs/FUTURE_FEATURES.md)
- [Project status](PROJECT_STATUS.md)

