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


## Audit 2 (0.2.0-beta.1)

Independent review of the 0.2 changes. Fixed: reference "immutability" bypass (`INSERT OR REPLACE`, `DROP TRIGGER`, `DROP TABLE`) replaced by a hash chain with honest wording; sample-rate warning corrected; warnings carried into recurrence candidates; boundary frames now excluded; recurrence consolidated to each segment's best earlier match with unique recording IDs enforced; unusable intervening segments reported; comparison inputs recorded with path/SHA-256/channel and bound to the loaded channel; stale comparison UI cleared on new load; startup no longer fails on a damaged reference table; NaN note timestamps rejected; stricter reference field types; 8-bit clipping and tiny-file quality checks; transition strength terms capped; report records parameters and only compared references plus the chain head; Windows smoke test now fails on non-zero exit; Linux release asset is a tar.gz that keeps the executable bit; release tag must equal `__version__`.

Known and not fixed: full-file decode memory (no streaming); comparison fingerprinting still runs on the UI thread; reference file is hashed and decoded in separate reads; flatness uses an absolute power cutoff; vendored `skills/` tree is unrelated to the product; no human GUI walkthrough yet; Tk theme details (checkbox hover colors) unverified.
