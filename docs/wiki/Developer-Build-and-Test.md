# Developer Build and Test

## Toolchain

- Python 3.10 or newer for source runs. CI uses 3.12
- NumPy
- Tk: on Linux, install the distribution's Tk package if `tkinter` is missing
- PyInstaller for bundles
- Linux CI uses `xvfb-run` for a headless GUI smoke launch

## Run from source

```
python -m pip install -e .
python -m audio_enviro_fingerprint
```

## Tests

```
PYTHONPATH=src python -m unittest discover -s tests -v
```

`tests/test_core.py` has 15 cases. They cover:

- SHA-256 of the original bytes
- notes linked to the original hash
- 24-bit PCM load and duration
- channel 1 selection without phase cancellation
- rejection of non-PCM and truncated WAVs
- band peak for a tone, and band power across sample rates
- fingerprint serialisation stability
- RT60 from a known exponential decay
- per-feature differences and similarity, and refusal of mismatched versions
- a clear step change detected as a transition with evidence
- no transitions for empty or one-frame input
- rejection of a non-finite minimum separation

## Build

Each platform has to build on its own OS. Local instructions are in `docs/BUILDING.md`. The CI commands are:

```
python -m pip install . pyinstaller
pyinstaller --noconfirm --clean --windowed --name AudioEnvironmentFingerprinter --paths src run_app.py
```

Output is `dist/AudioEnvironmentFingerprinter/`.

## CI (`.github/workflows/build-beta.yml`)

- Matrix: `ubuntu-24.04` and `windows-latest`, Python 3.12
- Steps: install, run unit tests, build the bundle, smoke launch the bundle (Linux under `xvfb-run`, Windows directly)
- Each OS builds its own bundle

## Release

The workflow builds bundles. The README says that a successful build does not by itself show a bundle has been validated. Check `docs/VALIDATION.md` before calling a release validated.

## Troubleshooting

- `tkinter` missing on Linux: install the Tk package for your distribution.
- Unit tests cannot import the package: use `PYTHONPATH=src`, or install with `pip install -e .`.
