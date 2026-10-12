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


## Follow-up audit (recurrence beta)

Fixed:
- Recurrence segments included overlapping frames that straddle a transition, blending both environments into each segment's medians. Straddling frames are now excluded.
- A failure while saving recurrence results escaped the GUI callback after the view was partly updated; it is now reported and the rest of the analysis still displays.
- Note timestamps accepted `inf`/`NaN` at the store layer; they now must be finite.

Open (not fixed, documented):
- "Compare recording" does not hash, register, or export the second file, so comparisons leave no auditable record.
- Feature normalization scales use the first item's centroid, so comparison and recurrence distances are slightly asymmetric (A→B ≠ B→A).
- Recurrence runs are appended to the case store on every open, including re-opens of the same evidence.
- Python 3.10/3.11 `wave` rejects WAVE_FORMAT_EXTENSIBLE files (common for 24-bit/multichannel); they fail with an explicit error. Python 3.12+ reads them.
- CI only triggers on `main`, the beta branch, tags, and pull requests; other branches have no build/smoke run until a PR is opened.
- Analysis remains synchronous and whole-file in memory (unchanged from the beta audit).
