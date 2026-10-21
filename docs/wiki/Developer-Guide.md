# Developer Guide

```sh
python -m pip install -e .                  # Python 3.10+, NumPy, Tk
python -m audio_enviro_fingerprint          # run the app
PYTHONPATH=src python -m unittest discover -s tests -v   # 15 tests pass on this snapshot
```

On Linux, install the distribution's Tk package if `tkinter` is missing. The build workflow is `.github/workflows/build-beta.yml`; `docs/BUILDING.md` explains packaging. Passing the build does not validate the released bundles (README).
