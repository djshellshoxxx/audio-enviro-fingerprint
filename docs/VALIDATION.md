# Validation and QA

## Current automated checks

`PYTHONPATH=src python -m unittest discover -s tests -v` covers source-byte SHA-256, PCM 24-bit decode, invalid WAV rejection, phase-safe channel-1 selection, feature band behavior on a synthetic tone, canonical fingerprint stability, incompatible-version rejection, explainable feature comparison, synthetic transition detection, empty input, SQLite timestamped note persistence, and synthetic exponential decay regression.

These are software regression tests. They are not scientific validation on representative recordings and do not establish sensitivity, specificity, reproducibility across hardware, or forensic suitability.

## Validation records by module

| Module | Validation record | Remaining validation |
|---|---|---|
| SHA-256 | Exact match with Python `hashlib.sha256` on test bytes | Large-file and interrupted-read tests; independent manifest verifier |
| WAV decode | 24-bit known sample and unsupported-file tests | 8/16/32-bit, multichannel, truncated, RF64, unusual sample rates, malformed headers |
| Noise features | Deterministic synthetic values | Silence, colored noise, speech, clipping, AGC, mic gain and codec datasets |
| Spectral features | Synthetic tone band ordering | Known-answer FFT references, window leakage, Nyquist/band-edge tests, compression and device variation |
| Transition detector | Known spectral step | Same-room source changes, room transitions, movement, edits, soft transitions, threshold ROC |
| Fingerprint | Canonical repeatability/version tag | Schema migration, quantization/rounding stability and benchmark dataset versioning |
| Comparison | Near/far synthetic ranking and raw explanation | Calibrate only with representative datasets; uncertainty and alternative hypotheses |
| Schroeder RT60 | Synthetic decay slope | Measured impulse responses with reference instrumentation and qualified protocol; do not claim standard conformance |
| Case notes/export | Note stored with evidence hash and timestamp | Crash recovery, report verification, note revisions, signed chain-of-custody workflow |

## Beta release gate

- All automated unit tests pass on Linux and Windows.
- PyInstaller build completes separately on Linux and Windows.
- Fresh installs launch and open a test PCM WAV on both operating systems.
- Packaged GUI starts and exits under a short CI smoke test on Windows and Linux.
- SHA-256 and fingerprint hashes are independently recomputed from exported data.
- UI presents channel selection, unsupported input limitations, heuristic transition status, and comparison-score caveat.
- Known limitations are shipped with the beta.

Only automated unit tests and the source build are locally testable in the current workspace. Native Windows launch and GUI interaction require the CI runner or a Windows test machine. The CI smoke test validates window construction and startup, not human usability or end-to-end interaction with a recording.

