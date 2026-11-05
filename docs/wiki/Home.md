# Audio Environment Fingerprinter Wiki

A cross-platform desktop beta for screening acoustic environments in a reproducible, explainable way. It hashes the original file (SHA-256) separately from a versioned acoustic feature fingerprint, so you can say exactly which bytes were analysed and what was measured from them.

**Status:** research beta. The threshold and similarity score are not validated on forensic datasets. Output needs examiner review. It does not identify a place, does not estimate whether two recordings share a location, and does not establish authenticity.

**Who it is for:** examiners and researchers who want repeatable, documented acoustic measurements with a visible audit trail, and developers who want to know how the analysis is built.

## Quick start

1. From source (Python 3.10 or newer, NumPy, Tk): `python -m pip install -e .` then `python -m audio_enviro_fingerprint`
2. Open an uncompressed integer PCM WAV (8, 16, 24 or 32 bit). Analysis uses channel 1.
3. Read the framewise descriptors and the candidate transitions. Each candidate shows the feature deltas behind it.
4. Save timestamped notes. They are bound to the source SHA-256 in a local SQLite file.
5. Export the analysis as JSON. Compare two recordings with **Compare recording…** when you need to.

## Pages

**For users**
- [[User-Guide]]: the app, step by step, and how to read results

**For developers**
- [[Developer-Overview]]: method, design decisions, data flow
- [[Developer-Code-Map]]: where everything lives and where to change it
- [[Developer-Build-and-Test]]: running, tests, CI, packaging
- [[Developer-Conventions]]: rules, gotchas, known limitations

**Repo docs (authoritative)**
- `docs/SPECIFICATIONS.md`: engineering and method specifications
- `docs/RESEARCH_NOTES.md`: research basis and source register
- `docs/VALIDATION.md`: validation and QA plan
- `docs/CODE_AUDIT.md`, `docs/BUILDING.md`, `docs/FUTURE_FEATURES.md`
- `PROJECT_STATUS.md`: what is verified locally
