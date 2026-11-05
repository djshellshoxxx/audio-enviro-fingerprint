# Developer Code Map

Paths are relative to the repo root. Line numbers are approximate.

## Directory tree

```
audio-enviro-fingerprint/
├── pyproject.toml              package metadata, editable install
├── run_app.py                  entry script used by PyInstaller
├── src/audio_enviro_fingerprint/
│   ├── __init__.py             __version__
│   ├── __main__.py             python -m audio_enviro_fingerprint
│   ├── app.py                  FingerprinterApp (Tk GUI), main()
│   ├── audio_io.py             PCM WAV loader (AudioData, load_wav, _decode_pcm)
│   ├── features.py             analyze_audio(), FrameFeature, AnalysisResult
│   ├── fingerprint.py          make_fingerprint(), Fingerprint (aefp-1, canonical JSON, digest)
│   ├── comparison.py           compare_fingerprints(), Comparison
│   ├── transitions.py          detect_transitions(), Transition
│   ├── integrity.py            sha256_file()
│   ├── case_store.py           CaseStore (SQLite: evidence and notes)
│   └── methods/
│       ├── noise.py            dbfs(), rms_dbfs(), frame_level_summary()
│       ├── spectral.py         describe_spectrum(), BANDS
│       └── reverberation.py    estimate_t20() (Schroeder, experimental RT60)
├── tests/test_core.py          15 unittest cases
├── docs/                       SPECIFICATIONS, RESEARCH_NOTES, VALIDATION, CODE_AUDIT, BUILDING, FUTURE_FEATURES
├── .github/workflows/build-beta.yml   tests and PyInstaller bundles (Ubuntu 24.04 and Windows)
├── PROJECT_STATUS.md, tasks.json
├── shared/, skills/            shared Circuit Drift Labs tooling and bundled skills (not app code)
└── .gitignore
```

## Key symbols

| Symbol (file:approx line) | Purpose |
|---|---|
| `FingerprinterApp` (`app.py:20`) | the Tk window. Toolbar buttons: Open PCM WAV, Compare recording, Export analysis JSON. Tabs: Analysis and Examiner Notes |
| `open_file()`, `compare_file()`, `export_json()`, `save_note()` (`app.py`) | the four user actions |
| `main()` (`app.py:247`) | GUI entry point |
| `load_wav()` (`audio_io.py:41`) | parse the WAV, choose channel 1, return `AudioData` |
| `_decode_pcm()` (`audio_io.py:23`) | integer PCM decode for 8, 16, 24 and 32 bit |
| `analyze_audio()` (`features.py:37`) | framewise analysis. Defaults: 2.0 s frame, 1.0 s hop |
| `make_fingerprint()` (`fingerprint.py:20`) | builds the canonical fingerprint and digest |
| `compare_fingerprints()` (`comparison.py:21`) | version check, per-feature difference, score |
| `detect_transitions()` (`transitions.py:15`) | threshold 0.35, per-feature scales: RMS 15 dB, centroid relative to the earlier frame with a 100 Hz floor |
| `sha256_file()` (`integrity.py:8`) | hash in 1 MiB chunks |
| `CaseStore` (`case_store.py:11`) | `evidence` and `notes` tables, `register_evidence()` (`:37`), `add_note()` (`:49`), `notes_for()` (`:67`) |
| `rms_dbfs()`, `frame_level_summary()` (`methods/noise.py:11`, `:17`) | level methods |
| `describe_spectrum()` (`methods/spectral.py:11`), `BANDS` (`:6`) | spectral method and band table |
| `estimate_t20()` (`methods/reverberation.py:12`) | Schroeder decay estimate |

## Where do I find X / to change X, edit Y

| I want to... | Edit |
|---|---|
| support another WAV format or width | `audio_io.py` (`_decode_pcm`, `load_wav`) |
| use a different channel or add a downmix | `audio_io.py` (channel choice). Note the no-downmix design decision |
| change frame or hop length | `features.py` defaults, and the GUI call in `app.py` |
| add a spectral descriptor | `methods/spectral.py` (`describe_spectrum`), then `features.py` (`FrameFeature`), then `fingerprint.py` |
| change the bands | `methods/spectral.py` (`BANDS`). Bump the fingerprint version |
| change a fingerprint feature | `fingerprint.py`, and bump `aefp-1` to the next version |
| change change-point detection | `transitions.py` (threshold, scales, delta evidence) |
| change the comparison score | `comparison.py` (`exp(-rms_distance)`). The text says it is uncalibrated |
| add an RT60 or other impulse-response method | `methods/reverberation.py` |
| change the GUI layout or buttons | `app.py` |
| change what is exported | `app.py` `export_json()` |
| change note storage | `case_store.py` (schema in `__init__` around lines 19 to 30) |
| change the packaged app | `.github/workflows/build-beta.yml` (PyInstaller command and smoke tests) |

## Gotchas for navigation

- `app.py` holds all GUI logic in one class. Keep analysis logic in the method modules, not in the handlers.
- `shared/` and `skills/` are copies of tooling from other repos. Changes to the app go in `src/`.
