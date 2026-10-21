# Audio Environment Fingerprinter

Cross-platform desktop beta for reproducible, explainable acoustic-environment screening. It computes a cryptographic hash of the original file separately from a versioned acoustic feature fingerprint.

## Beta scope

- Reads uncompressed WAV: integer PCM (8/16/24/32 bit), IEEE float, WAVE_FORMAT_EXTENSIBLE, RF64.
- Channel 1 drives the single-channel methods; all channels are kept for inter-channel analysis. No downmix; source is read only.
- Musical description: dominant tones with note names/cents, key, tempo, pitch, mains hum.
- Environment recurrence detection, spectrogram, guided known-location reference records, manual markers with revision history, manifest-verified JSON reports, and a CLI (`analyze`, `compare`, `recurrence`, `spectrogram`, `verify`).
- Computes framewise RMS level, spectral centroid, spectral flatness, and fixed-band power descriptors.
- Marks candidate transitions from adjacent-frame feature differences and shows the measurements behind each candidate.
- Compares two acoustic fingerprints with per-feature differences and an explicitly uncalibrated descriptive score.
- Stores timestamped notes linked to the original evidence SHA-256 in a local SQLite database.
- Exports a JSON analysis record.
- Includes an experimental Schroeder decay-slope RT60 estimate for impulse-response data. It is not an ISO 3382 measurement workflow.

This software does not identify a physical location, estimate the probability of a common location, or establish authenticity. Build workflow definitions do not by themselves establish that downloadable release bundles have passed validation. It is a research beta and its output requires examiner review. The current change-point threshold and similarity score have not been validated on representative forensic datasets.

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

## Build

The GitHub Actions workflow builds Windows, Linux, and macOS (Apple silicon) bundles; pushing a `v*` tag publishes them as a GitHub Release. Each must be built on its target operating system. Local build instructions are in [docs/BUILDING.md](docs/BUILDING.md).

## Documentation

- [Research notes and source register](docs/RESEARCH_NOTES.md)
- [Engineering and method specifications](docs/SPECIFICATIONS.md), [v0.2 additions](docs/SPECIFICATIONS_V2.md)
- [Validation and QA plan](docs/VALIDATION.md)
- [Future feature backlog](docs/FUTURE_FEATURES.md)
- [Project status](PROJECT_STATUS.md)

