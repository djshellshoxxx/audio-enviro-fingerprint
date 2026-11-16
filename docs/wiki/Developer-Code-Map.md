# Developer Code Map

Paths below are relative to the repository root. `shared/` and `skills/` are bundled general tooling, not application runtime modules.

| Area | Files and responsibility |
|---|---|
| Entrypoints | `run_app.py` for PyInstaller; package `__main__.py` and `launcher.py` dispatch GUI versus CLI; `cli.py` owns commands. |
| Desktop interface | `app.py` orchestrates worker results, case actions and main window; `ui_tabs.py` owns tab widgets. |
| Native audio | `audio_io.py`: strict RIFF/RF64, PCM/float/extensible input, all channels retained, channel 1 selected. |
| Optional codecs | `codec_io.py`: local restricted FFmpeg/ffprobe, provenance, timeout and decoded-size caps. |
| Numerical inputs | `validation.py`: reusable finite signal/rate/feature contracts. |
| Analysis | `features.py`: `FrameFeature`, `AnalysisResult`, sample-aligned frame extraction. |
| Independent measurements | `methods/noise.py`, `spectral.py`, `musical.py`, `hum.py`, `quality.py`, `reverberation.py`. |
| Fingerprints and comparisons | `fingerprint.py`: canonical features/hash; `comparison.py`: transparent pair differences; `catalog.py`: deterministic complete-link descriptor groups. |
| Candidate events | `transitions.py`: adjacent-frame changes; `recurrence.py`: fixed-scale return candidates and actual-time intervals. |
| Spatial descriptors | `multichannel.py`: channel fingerprints, levels, polarity/correlation and limited lag. |
| Reference acquisition | `reference.py`: acquisition metadata and quality review. |
| Spectrogram | `spectrogram.py`: STFT/colorization/PNG generation independent of Tk. |
| Integrity and cancellation | `integrity.py`: original-byte hashing and atomic protected exports; `control.py`: cooperative cancellation. |
| Persistence | `case_store.py`: evidence, notes, acquisition records, marker history and compatible audit persistence. |
| Orchestration and reports | `pipeline.py`: one-call analysis and report sections; `report.py`: canonical-body manifest, export and verification. |
| Software benchmarks | `benchmark.py`; `docs/BENCHMARK_PROTOCOL.md` distinguishes synthetic checks from field validation. |
| Checks | `tests/test_*.py` use unittest with synthetic signals and real optional FFmpeg integration. |
| Packaging | `pyproject.toml`, `.github/workflows/build-beta.yml`, `docs/BUILDING.md`. |

Before changing a behavior, identify its specification contract and add a failing regression. Keep method work outside Tk handlers. Avoid replacing current stores/manifest shapes with legacy branch alternatives; [branch reconciliation](../BRANCH_RECONCILIATION.md) records those decisions.
