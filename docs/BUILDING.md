# Build and run

## Development install

Requires CPython 3.10+, NumPy, and Tkinter/Tk.

```bash
python -m pip install -e .
python -m audio_enviro_fingerprint
```

On Debian or Ubuntu, Tk may need the system `python3-tk` package. Run checks with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Local packaged build

Use a clean virtual environment on the target OS. The build must be performed on each target platform because PyInstaller bundles platform-specific bootloaders and libraries.

```bash
python -m pip install . pyinstaller
pyinstaller --noconfirm --clean --windowed --name AudioEnvironmentFingerprinter --paths src src/audio_enviro_fingerprint/__main__.py
```

The resulting application folder is in `dist/AudioEnvironmentFingerprinter`. Windows produces an `.exe`; Linux produces a native executable. The GitHub Actions matrix runs this command on Windows and Ubuntu, smoke-launches the packaged GUI, and uploads separate beta artifacts.

## Beta build identifiers

The source version is `0.1.0-beta.1`. CI names artifacts by operating system and source ref. The first published binaries remain provisional until launched and smoke-tested on their target systems.

