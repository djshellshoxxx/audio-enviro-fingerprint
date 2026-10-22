# Project status

## Implementation baseline

Development continues from `claude/intelligent-darwin-gmqz81` (5b8a216), which contains the v0.2 implementation absent from main. Implemented: PCM/float/extensible/RF64 WAV decoding, per-channel fingerprints and spatial metrics, candidate transitions and recurrence, reference acquisition and quality review, append-only markers and notes, musical and mains-hum descriptors, spectrogram PNG, CLI, GUI tabs, and manifest-bearing reports.

## Completion audit — 2026-10-22

Added regression coverage and fixes for forged extensible subtype GUIDs, inconsistent WAV block alignment/byte rate, truncated RF64 metadata, unsupported report manifest algorithms, malformed report JSON, and nonfinite recurrence settings.

The unit suite uses synthetic signals; passing it does not establish scientific calibration. Local Tk is importable, but no display/Xvfb is available for GUI smoke testing. Platform bundles require the Windows/Linux/macOS CI matrix.

## Additional implemented work

- Optional local FFmpeg decoding with first-stream selection, no downmix or resampling, decoder/version/codec provenance, restricted demuxers/protocols, timeout and decoded-size limits. FLAC and MP3 integration tests passed locally.
- Atomic report/PNG exports refuse to overwrite evidence, including symlink and hardlink aliases.
- Cooperative GUI cancellation retains the previous result and publishes no partial result. A running decode or musical analysis may finish its current stage before cancellation takes effect.
- Marker revisions stay bound to their original evidence; nonfinite note/marker times are rejected.

## Remaining work

- Full streaming decode and performance verification on large recordings. Recurrence now uses linear working memory; cooperative cancellation is implemented for hashing, frame extraction, recurrence and pipeline stage boundaries.
- Representative field benchmark acquisition and scientific calibration.
- ENF time series, scene/event classification, reflection analysis, robustness exploration, blind comparisons, and broader case reconstruction remain future research features in docs/FUTURE_FEATURES.md.
- Code signing/notarization and Intel macOS builds remain unavailable.

This project is not feature complete. SPECIFICATIONS_V2.md supplements the original beta specification; older documentation must not be read as a current inventory.
