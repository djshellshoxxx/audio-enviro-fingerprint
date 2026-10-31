# Changelog

## 0.3.0b2 — audited development build

### Added
- Recent recordings, quick analysis, clock-time annotation/navigation, and precise marker editing with revision history.
- Printable static HTML reports through the GUI and `analyze --format html`, with escaped annotations and evidence-safe atomic exports.
- Append-only SQL guards, evidence-bound saved recurrence runs in report history, and consolidated user/developer wiki.

### Corrected after full application audit
- Reject nonregular evidence before hashing and invalid hash chunk sizes; support RF64 ancillary size-table entries.
- Enforce tempo/pitch bounds, disclose unavailable lag for silent/DC-only channels, and validate direct analysis metadata before hashing.
- Select recurrence references satisfying departure as well as distance/gap, preserving continuing returns.
- Run compare/search off the UI thread, search the selected recording in the correct direction, handle changed/deleted evidence, and clear stale musical/reference displays.
- Preserve evidence used as a preferences path across later opens; prevent logical-key SQL replacement from bypassing append-only guards.

### Previous maintenance fixes

### Fixed
- Enforce the decoded float64 byte limit for native WAV/RF64 before reading sample payloads; skip ancillary chunks with bounded metadata reads.
- Accept complete compressed audio exactly at the configured decoded-size limit.
- Use actual frame timestamps and sample-aligned window spans for recurrence ranges and minimum-gap eligibility.

## 0.3.0b1 — release candidate

### Added
- Native Intel macOS release target alongside Apple silicon, Windows and Linux.
- Packaged GUI smoke verifies background report export, source/manifest hashes and SQLite notes/markers.
- Optional local FFmpeg compressed-input decoding with codec/version provenance and size/time limits.
- Cooperative analysis cancellation and linear-memory recurrence queries.
- Transparent multi-recording descriptor grouping and deterministic synthetic benchmark commands.
- Reference records and full marker revision history in GUI reports.
- DC-offset and dropout quality review ported from earlier development.

### Changed
- Fingerprints use `aefp-2` rounded canonical values from the older audited implementation. Regenerate fingerprints to compare against new analyses; mixed versions are rejected.
- Comparisons use `comparison-symmetric-v2`; swapping recordings no longer changes the score. Earlier thresholds require re-evaluation.

### Fixed
- Enforce RIFF/RF64 container and extension bounds; validate finite reusable numerical inputs and supported fingerprint schemas.
- Preserve finite silence/high-rate reports; hum windows now resolve narrow bands and disclose frequency resolution/unavailable measurements.
- Acquisition reviews validate UTC/height/repeat values and detect positive 8-bit full-scale clipping; reference JSON rejects NaN/Infinity.
- GUI exports protect the active case database and filesystem aliases.
- Reports recheck evidence integrity at export; hashing/serialization run off the UI thread with cooperative cancellation.
- Release errors cannot trigger automatic replacement of existing artifacts.
- Exports cannot overwrite source evidence or its aliases and are written atomically.
- Reject malformed WAV subtype/block metadata, truncated RF64 metadata, unsupported report algorithms and malformed report objects.
- Reject nonfinite recurrence settings and timestamps; marker revisions cannot switch evidence ownership.
- Failed imports retain the prior evidence binding.

### Remaining
- Full streaming analysis, representative field calibration, remaining legacy-branch reconciliation and research backlog are incomplete. Platform release checks must pass for the final commit before publication.
