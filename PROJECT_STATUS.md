# Project status

## Implementation baseline

Development continues from `claude/intelligent-darwin-gmqz81` (5b8a216), which contains the v0.2 implementation absent from main. Implemented: PCM/float/extensible/RF64 WAV decoding, per-channel fingerprints and spatial metrics, candidate transitions and recurrence, reference acquisition and quality review, append-only markers and notes, musical and mains-hum descriptors, spectrogram PNG, CLI, GUI tabs, and manifest-bearing reports.

## Completion audit — 2026-10-22

Added regression coverage and fixes for forged extensible subtype GUIDs, inconsistent WAV block alignment/byte rate, truncated RF64 metadata, unsupported report manifest algorithms, malformed report JSON, and nonfinite recurrence settings.

The unit suite uses synthetic signals; passing it does not establish scientific calibration. Local Tk GUI smoke has passed with a user-space Xvfb display, exercising synthetic analysis and all tabs. Platform bundles require the Windows/Linux/macOS CI matrix.

## Additional implemented work

- Optional local FFmpeg decoding with first-stream selection, no downmix or resampling, decoder/version/codec provenance, restricted demuxers/protocols, timeout and decoded-size limits. FLAC and MP3 integration tests passed locally.
- Atomic report/PNG exports refuse to overwrite evidence, including symlink and hardlink aliases.
- Cooperative GUI cancellation retains the previous result and publishes no partial result. A running decode or musical analysis may finish its current stage before cancellation takes effect.
- Marker revisions stay bound to their original evidence; nonfinite note/marker times are rejected.

- Catalog grouping now exposes all pair measurements and deterministic complete-link groups via CLI. Comparison scores are symmetric and labeled `comparison-symmetric-v2`.
- Ported `aefp-2` reproducible serialization, DC/dropout quality checks, and synthetic benchmarking from older branches; adapted benchmark recurrence to the active API.
- Reports retain reference records and marker history; rejected imports preserve the prior evidence binding.
- Windows CI build/package/GUI smoke test succeeded for commit 20b8de3; later changes require a fresh CI run. Linux/macOS jobs were still queued at that checkpoint.

## Remaining work

- Full streaming decode and performance verification on large recordings. Recurrence now uses linear working memory; cooperative cancellation is implemented for hashing, frame extraction, recurrence and pipeline stage boundaries.
- Representative field benchmark acquisition and scientific calibration (synthetic benchmark is implemented).
- Reconcile remaining incompatible modules and UI behavior from older branches before declaring repository completion.
- ENF time series, scene/event classification, reflection analysis, robustness exploration, blind comparisons, and broader case reconstruction remain future research features in docs/FUTURE_FEATURES.md.
- Code signing/notarization remains unavailable. Intel macOS now has a dedicated native CI job; build results must be checked before claiming a released binary.

This project is not feature complete. SPECIFICATIONS_V2.md supplements the original beta specification; older documentation must not be read as a current inventory.

## Cloud release preparation — 2026-10-22

- Reused the existing completion-audit branch rather than rebuilding features
  already implemented outside main.
- Report exports now recheck source integrity immediately before writing, and
  GUI report/PNG exports protect the active SQLite case database and aliases.
- Added regression tests for protected database paths and changed evidence.
- Expanded packaged GUI smoke to persist notes/markers, verify an exported
  report against its source, and select every notebook tab.
- Added Intel macOS to the native matrix and removed error-driven asset
  replacement; publishing an existing tag fails without clobbering artifacts.
- Scientific field calibration, streaming decode, and future research methods
  remain explicitly unfinished; a successful software build does not complete
  those research requirements.

Required provenance-contract review also corrected semantic UTC/height/repeat
validation, positive 8-bit clipping detection, and nonfinite reference JSON
storage, with focused regression coverage. These checks establish metadata
well-formedness only; they do not verify operator claims or calibrate methods.

Final input-contract hardening bounds RIFF/RF64 chunk parsing by declared
container sizes, validates finite direct numerical inputs, and preserves both
supported fingerprint schema versions. Full report JSON invariants cover stereo
silence and tones across 8–192 kHz. Hum analysis no longer emits infinite values
for silence or crashes on empty high-rate harmonic bins, and discloses actual
frequency resolution and unavailable short-recording results.
