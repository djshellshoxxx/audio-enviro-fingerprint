# Build and run

## Development install

Requires CPython 3.10+, NumPy and Tkinter/Tk. The optional `formats` extra installs `soundfile`, which provides FLAC/AIFF/OGG/MP3/RF64/W64 decoding.

```bash
python -m pip install -e ".[formats]"
python -m audio_enviro_fingerprint
```

On Debian or Ubuntu, Tk may need the system `python3-tk` package. Run the checks with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v          # GUI tests skip without a display
PYTHONPATH=src xvfb-run -a python -m unittest discover -s tests  # headless Linux, including GUI tests
```

## Packaged builds

Build in a clean virtual environment **on the target OS**. PyInstaller bundles platform-specific bootloaders and libraries, so a Windows `.exe` cannot be produced on Linux.

```bash
python -m pip install ".[formats]" pyinstaller
python scripts/build_bundle.py            # dist/AudioEnvironmentFingerprinter/ (folder)
python scripts/build_bundle.py --onefile  # dist/AudioEnvironmentFingerprinter-standalone(.exe)
```

`scripts/build_bundle.py` runs PyInstaller with `--windowed`. It collects all package submodules, and bundles libsndfile (`_soundfile_data`) when `soundfile` is installed.

## Smoke test of a packaged build

```bash
python scripts/make_smoke_wav.py smoke.wav
AEFP_SMOKE_TEST=1 AEFP_SMOKE_FILE=smoke.wav AEFP_SMOKE_REPORT=report.json ./dist/AudioEnvironmentFingerprinter/AudioEnvironmentFingerprinter
aefp verify-report report.json --evidence smoke.wav
```

In smoke mode the app analyzes the file, writes the report, and exits with status 0. It exits 1 on any error. A temporary case database is used. Without `AEFP_SMOKE_FILE`, it only opens and closes the window. On Windows, the GUI-subsystem executable must be waited on explicitly (`Start-Process -Wait -PassThru`).

## CI

`.github/workflows/build-beta.yml` runs on pushes to `main` and `claude/**` branches, on PRs, on `v*-beta*` tags, and on manual dispatch:

1. **test:** unit tests on Python 3.10 and 3.12, Ubuntu and Windows (GUI tests run under Xvfb on Linux), plus a headless CLI analyze/verify smoke test.
2. **package:** PyInstaller builds on Ubuntu and Windows. Windows builds both the folder and the single-file exe. Each binary is smoke-tested by analyzing a WAV and verifying the report it wrote. The artifacts are then uploaded.

## Version

Source version `0.2.0-beta.1` (`pyproject.toml`: `0.2.0b1`). Binaries are unsigned research-beta builds.
