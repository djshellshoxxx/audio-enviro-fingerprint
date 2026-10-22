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
pyinstaller --noconfirm --clean --windowed --name AudioEnvironmentFingerprinter --paths src run_app.py
```

The resulting application folder is in `dist/AudioEnvironmentFingerprinter`. Windows produces an `.exe`; Linux produces a native executable. The GitHub Actions matrix runs this command on Windows, Ubuntu and Apple silicon macOS, smoke-launches the packaged GUI, and uploads separate beta artifacts.

## Beta build identifiers

The source version is `0.3.0b1`. CI names artifacts by operating system and source ref. The first published binaries remain provisional until launched and smoke-tested on their target systems.


## Optional compressed input

Install `ffmpeg` and `ffprobe` and put both on PATH. They are not bundled or required for native WAV analysis. On Ubuntu: `sudo apt-get install ffmpeg`. On Windows/macOS use a trusted FFmpeg distribution and ensure both commands are available before starting the app. Codec availability depends on that installation.

Compressed input uses the first audio stream, preserving its channel count and sample rate. Supported decoder names are FLAC, MP3, Vorbis, Opus, AAC and ALAC in FLAC/MP3/Ogg/MOV-family containers. Automated real-codec integration currently covers FLAC and MP3. Reports record decoder version, codec and output representation. Lossy decoding changes the measured waveform; the evidence digest still covers original bytes.

Compressed decoding has a 512 MiB decoded-float limit and a 300-second timeout; reaching the limit is an error, never a partial result. Native WAV loading and later analysis still load whole recordings into memory. Cancellation is cooperative: hashing, frame extraction and recurrence check inside loops; decoding and musical analysis finish their current stage before observing cancellation.
