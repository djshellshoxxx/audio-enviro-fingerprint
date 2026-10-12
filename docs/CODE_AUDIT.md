# Initial code audit

Date: 2026-10-08  
Scope: initial beta source, tests, storage, analysis math, and packaging workflow.

## Findings and changes

| Severity | Finding | Resolution |
|---|---|---|
| Required | A shortened WAV payload could be silently accepted because the header's declared frame count was not checked against bytes read. | Reader now checks declared frame count against payload length; regression test truncates valid PCM data and verifies rejection. |
| Required | Non-finite transition separation could silently suppress results. | Detector now validates finite, nonnegative separation; regression test covers NaN. |
| Required | Early spectrum power normalization varied with frame/sample rate. | Spectrum now uses a window-energy and sample-rate normalized one-sided periodogram; regression compares equivalent 440 Hz measurements at 8 and 16 kHz. |
| Required | The lower percentile of frame RMS was named as a noise floor, overstating what was measured. | Renamed to `frame_rms_dbfs_p10`; documentation clarifies that it is not isolated background noise. |
| Required | Export recomputed the file hash after analysis, potentially pairing a changed source with stale analysis. | Import pins the original SHA-256, verifies it stayed stable during load, and export stops if the source hash changes. |
| Required | Stereo averaging could cancel anti-phase content. | Analysis selects channel 1 explicitly and reports the channel count; full multichannel review remains TODO. |
| Required | Decay routine returned `20 / slope` while calling it RT60. | It returns `60 / slope` from a -5 to -25 dB regression; synthetic decay test validates this relationship. |
| Required | PyInstaller's standalone script context broke the package-relative import in `__main__.py`. | Packaging now uses top-level `run_app.py` with an absolute package import; CI launches the bundled GUI after build. |

## Review by axis

- **Correctness:** source hash and acoustic fingerprint are separate; invalid formats, truncated PCM, empty analysis, incompatible fingerprint versions, and non-finite transition parameters fail explicitly. Synthetic tests cover core numerical behaviors.
- **Readability:** scientific methods are isolated under `methods/`; evidence storage, comparison, and transition logic are separate modules. One unused WAV test helper was identified and removed.
- **Architecture:** UI orchestrates service modules; modules do not rewrite source files. The current GUI still performs analysis synchronously and decodes a full recording into memory.
- **Security and integrity:** SQL values are parameterized, JSON serialization forbids NaN/Infinity, and evidence changes prevent export. The beta does not sign reports or provide access control, encryption, or a complete chain-of-custody system.
- **Performance:** FFT operates on overlapping fixed windows and can be expensive for long recordings; no memory cap, cancellation, or progress reporting yet. This is documented for the beta.

## Verification

Local Linux checks: 15 unit tests passed; `compileall` passed; package wheel built. Native PyInstaller builds and GUI startup smoke tests run on separate Windows/Linux CI runners because PyInstaller is unavailable locally and outbound package access is blocked.


# Completion audit (0.2.0-beta.1)

Date: 2026-10-12  
Scope: the whole repository after feature completion: source, tests, scripts, CI workflow and docs. Methods: tracing every documented feature to a GUI or CLI entry point, pyflakes, vermin (Python 3.10 minimum), CI log review on Windows and Linux, edge-case QA, and a long-file performance measurement.

| Severity | Finding | Resolution |
|---|---|---|
| Blocker | The same file produced **different fingerprint hashes on Windows and Linux** (seen in CI logs). The hash covered raw floats, and FFT/log results differ between platforms and NumPy builds. Values at the numerical noise floor, such as the flatness of a pure tone (~1e-16), differed entirely. | Fingerprint `aefp-2` rounds every feature to 6 decimal places and normalizes -0.0 before canonical serialization. Verified identical across NumPy 1.26/Python 3.11 and NumPy 2.5/Python 3.12. CI now asserts one expected hash for source runs and packaged binaries on both OSes (`scripts/check_smoke_report.py`). A regression test covers last-bit noise. |
| Required | The documented RT60 estimator was not reachable from the GUI or CLI. | `aefp rt60` CLI command, and an Analysis-tab button with an impulse-response confirmation and caveat. Tested. |
| Required | Case contents (`evidence_list`, saved recurrence runs) could be stored but not viewed. | New Case tab, refreshed after loads and saves. Tested. |
| Required | Peak memory was ~15× the WAV size (2.7 GB for 30 min at 48 kHz), from redundant full-array copies. | No copy of contiguous mono channels, and column-wise centering in the channel statistics. Now 1.35 GB and 15 s. The remainder is the float64 decode; streaming is backlog. |
| Required | The earlier Windows smoke test did not wait for the GUI-subsystem exe, so it could pass without running anything. | `Start-Process -Wait -PassThru` with an exit-code check. Smoke mode returns 1 on failure and must write a report that verifies. |
| Minor | Unused imports and an unused local (`app.py`, `spectral.py`, a test). A Tk `after` callback fired after window destruction. | Removed. The poll callback is cancelled on close. |

Checks that passed: no undefined names. Python 3.10 compatible (vermin, and CI on 3.10). Tk is touched only on the main thread: worker threads post to a queue. SQL is parameterized. Reports use strict JSON (no NaN/Infinity). Edge cases were tested: digital silence, DC-only audio, 8-bit audio, 6 channels, over-range float WAV with an odd-sized extra chunk, truncated data, invalid channel, non-audio input, cancellation, and a source changed during analysis.

Remaining limitations, not defects: in-memory decode, unsigned executables and reports, no accessibility review, and no real-data validation. See PROJECT_STATUS.md.
