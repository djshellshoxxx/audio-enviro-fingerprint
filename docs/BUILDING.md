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

The resulting application folder is in `dist/AudioEnvironmentFingerprinter`. Windows produces an `.exe`; Linux produces a native executable. The GitHub Actions matrix runs this command on Windows, Ubuntu and Apple silicon and Intel macOS, smoke-launches the packaged GUI, and uploads separate beta artifacts.

## Beta build identifiers

The source version is `0.3.0b1`. CI names artifacts by operating system and source ref. The first published binaries remain provisional until launched and smoke-tested on their target systems.


## Optional compressed input

Install `ffmpeg` and `ffprobe` and put both on PATH. They are not bundled or required for native WAV analysis. On Ubuntu: `sudo apt-get install ffmpeg`. On Windows/macOS use a trusted FFmpeg distribution and ensure both commands are available before starting the app. Codec availability depends on that installation.

Compressed input uses the first audio stream, preserving its channel count and sample rate. Supported decoder names are FLAC, MP3, Vorbis, Opus, AAC and ALAC in FLAC/MP3/Ogg/MOV-family containers. Automated real-codec integration currently covers FLAC and MP3. Reports record decoder version, codec and output representation. Lossy decoding changes the measured waveform; the evidence digest still covers original bytes.

Compressed decoding has a 512 MiB decoded-float limit and a 300-second timeout; reaching the limit is an error, never a partial result. Native WAV loading and later analysis still load whole recordings into memory. Cancellation is cooperative: hashing, frame extraction and recurrence check inside loops; decoding and musical analysis finish their current stage before observing cancellation.

## Cloud-host Python library discovery

This cloud Python distribution is relocated and its `sysconfig` build-time
`LIBDIR` can be stale. If PyInstaller reports unresolved Tcl/Tk shared libraries,
set `LD_LIBRARY_PATH` for the builder to the actual Python base prefix's `lib`
directory. The final packaged smoke must run without that override, proving the
libraries were included rather than borrowed from the host. This is a Linux
cloud-host accommodation; CI's standard Python installations use the normal
build command above.

## Automated releases

The native CI matrix builds Linux x86-64, Windows x86-64, macOS arm64
(`macos-26`) and macOS x86-64 (`macos-15-intel`). Each job runs the complete
unit suite and then the packaged GUI smoke workflow: synthetic stereo analysis,
all tab selection, SQLite notes/markers, JSON export, and manifest/source-hash
verification. A failed platform prevents release publication.

To publish a new beta from a reviewed branch, dispatch **Build and release**
with a new `release_tag`, for example `v0.3.0-beta.1`. Use a new tag for a new
build; an existing release is never overwritten automatically. The release
contains one archive per platform plus `SHA256SUMS.txt`. These are unsigned
research builds; signature/notarization credentials and field calibration are
separate requirements.
