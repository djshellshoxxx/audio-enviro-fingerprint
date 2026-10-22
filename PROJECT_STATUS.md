# Project status

## Implementation baseline

Development continues from `claude/intelligent-darwin-gmqz81` (5b8a216), which contains the v0.2 implementation absent from main. Implemented: PCM/float/extensible/RF64 WAV decoding, per-channel fingerprints and spatial metrics, candidate transitions and recurrence, reference acquisition and quality review, append-only markers and notes, musical and mains-hum descriptors, spectrogram PNG, CLI, GUI tabs, and manifest-bearing reports.

## Completion audit — 2026-10-22

Added regression coverage and fixes for forged extensible subtype GUIDs, inconsistent WAV block alignment/byte rate, truncated RF64 metadata, unsupported report manifest algorithms, malformed report JSON, and nonfinite recurrence settings.

The unit suite uses synthetic signals; passing it does not establish scientific calibration. Local Tk is importable, but no display/Xvfb is available for GUI smoke testing. Platform bundles require the Windows/Linux/macOS CI matrix.

## Remaining work

- Compressed audio decoding with decoder provenance.
- Bounded-memory analysis, cancellation, progress and performance verification on large recordings.
- Representative field benchmark acquisition and scientific calibration.
- ENF time series, scene/event classification, reflection analysis, robustness exploration, blind comparisons, and broader case reconstruction remain future research features in docs/FUTURE_FEATURES.md.
- Code signing/notarization and Intel macOS builds remain unavailable.

This project is not feature complete. SPECIFICATIONS_V2.md supplements the original beta specification; older documentation must not be read as a current inventory.
