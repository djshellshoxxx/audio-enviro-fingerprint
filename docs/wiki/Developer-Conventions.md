# Developer Conventions

## Style

- Standard library and NumPy only in the core. Keep GUI code (`app.py`) separate from analysis code (`features.py`, `methods/`, `transitions.py`, `comparison.py`).
- Type hints on public functions. Dataclasses for results (`AnalysisResult`, `Fingerprint`, `Transition`, `Comparison`).
- Validate input and fail with `ValueError` (for example non-finite durations in `analyze_audio`, incompatible fingerprint versions).

## Evidence rules

- The source file is read only. Never write to it, and never downmix it.
- Every analysis path starts from a SHA-256 of the file. Load, analysis and export all re-check it.
- Notes and evidence records are keyed by (path, SHA-256). Do not drop that key.
- Outputs are descriptive. Do not add a probability, a location claim or an authenticity verdict. The README and status say this, and the UI text should match.

## Versioning

- The fingerprint format is `aefp-1`. Any change to a feature, a band or the serialisation needs a new version string.
- Comparison refuses different versions. Do not relax that check.
- `make_fingerprint()` uses sorted keys and rejects NaN. Keep the canonical form stable, or bump the version.

## Gotchas

- The change threshold (0.35) and the similarity score are not validated. Treat changes to them as method changes and record the reason in `docs/SPECIFICATIONS.md`.
- The RT60 estimator is experimental and not an ISO 3382 workflow.
- Only integer PCM WAV is supported. Adding formats changes the evidence path, so update the specification first.
- The GUI runs analysis on the main thread.

## How to add a feature

1. Put the analysis in `methods/` or a top-level module, with no Tk imports.
2. If it changes the fingerprint, bump the version and add a serialisation test.
3. Add a test to `tests/test_core.py` (the file is already organised by behaviour).
4. Wire it into `app.py` and the export in `export_json()`.
5. Update the specification and validation docs.

## Known limitations

From `PROJECT_STATUS.md` and the README:

- Research beta. Output needs examiner review.
- Threshold and similarity are not validated on representative forensic datasets.
- Integer PCM WAV only, channel 1 only.
- Build workflows do not prove that release bundles have passed validation.
