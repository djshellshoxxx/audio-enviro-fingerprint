# Changelog

## 0.3.0b1 — development

### Added
- Optional local FFmpeg compressed-input decoding with codec/version provenance and size/time limits.
- Cooperative analysis cancellation and linear-memory recurrence queries.
- Transparent multi-recording descriptor grouping and deterministic synthetic benchmark commands.
- Reference records and full marker revision history in GUI reports.
- DC-offset and dropout quality review ported from earlier development.

### Changed
- Fingerprints use `aefp-2` rounded canonical values from the older audited implementation. Regenerate fingerprints to compare against new analyses; mixed versions are rejected.
- Comparisons use `comparison-symmetric-v2`; swapping recordings no longer changes the score. Earlier thresholds require re-evaluation.

### Fixed
- Exports cannot overwrite source evidence or its aliases and are written atomically.
- Reject malformed WAV subtype/block metadata, truncated RF64 metadata, unsupported report algorithms and malformed report objects.
- Reject nonfinite recurrence settings and timestamps; marker revisions cannot switch evidence ownership.
- Failed imports retain the prior evidence binding.

### Remaining
- Full streaming analysis, representative field calibration, remaining legacy-branch reconciliation and research backlog are incomplete. Platform release checks must pass for the final commit before publication.
