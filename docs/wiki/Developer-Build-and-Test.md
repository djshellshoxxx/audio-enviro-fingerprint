# Developer Build and Test

## Source and unit checks

Python 3.10+ is supported; native CI uses Python 3.12. Install NumPy and Tk, with FFmpeg/ffprobe on PATH for optional compressed-input integration tests.

```bash
python -m pip install -e .
python -m audio_enviro_fingerprint
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m audio_enviro_fingerprint benchmark --quick --seed 1
```

Tests cover strict native input, metadata/container bounds, source integrity, finite numerical behavior, fingerprints, descriptor comparison, recurrence/transition scenarios, acquisition review, case persistence and exports. Run the full suite after changes; consult current audit/verification documents for exact counts rather than treating a historical count as a requirement.

## Packaging

Each operating system builds its own PyInstaller bundle; see [BUILDING](../BUILDING.md).

```bash
python -m pip install . pyinstaller
pyinstaller --noconfirm --clean --windowed --name AudioEnvironmentFingerprinter --paths src run_app.py
```

CI `.github/workflows/build-beta.yml` targets `ubuntu-24.04`, `windows-latest`, `macos-26` (ARM64) and `macos-15-intel`. It runs unit tests, builds, executes a packaged GUI smoke (`AEFP_SMOKE_TEST=1`), then archives the bundle. Linux uses a headless display. Test a final revision on every platform before declaring its native release verified.

A `v*` tag triggers GitHub Release publication after the build matrix. Builds are unsigned; signing/notarization is not configured. Publishing a tag is an external release action, not a necessary part of local development or branch consolidation.

## Troubleshooting

- Missing `tkinter`: install the distribution's Tk support; headless CLI remains separate from GUI startup.
- No display: use a permitted local X server for Linux GUI tests or a native CI runner.
- Missing FFmpeg: WAV remains supported natively; optional codec tests are skipped and compressed imports report the missing tools.
- Import errors: use the editable installation or `PYTHONPATH=src`.
- Large recordings: the decoded sample cap is not full streaming or a peak-memory guarantee; recurrence time remains quadratic.

Passing software checks does not supply representative field calibration, platform signing or validation of physical-location attribution.
