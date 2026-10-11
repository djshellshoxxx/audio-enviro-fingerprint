# Known-location reference acquisition

A reference recording is an exemplar captured under a documented, controlled protocol at a location described by the operator. The location label is **self-reported metadata**. The software does not verify it. A high similarity score against a reference is a screening observation, never a location identification or a probability of common origin.

## Capture protocol (checklist)

The quality review scores each item of `reference.CAPTURE_CHECKLIST`:

1. Location identifier recorded, using a stable site/room ID rather than free text alone.
2. Capture time recorded as ISO-8601 with a timezone (UTC preferred).
3. Operator recorded.
4. Consent / legal authority for capture documented.
5. Recorder make/model **and** serial documented.
6. Microphone make/model documented.
7. Input chain documented (cables, preamp, gain, any processing such as AGC/noise suppression, which should be disabled).
8. Channel and sample rate documented. The rate must match the decoded file.
9. Placement, orientation and height documented.
10. Source signal documented (ambient only, or the stimulus used).
11. Occupancy and activity documented (people, HVAC, machinery, traffic).
12. Weather documented when relevant (outdoor or open-window capture).
13. Calibration documented (e.g. reference tone level, or "uncalibrated").
14. Deviations from protocol documented ("none" is an explicit answer).
15. Source SHA-256 recorded. The app records it automatically from the evidence hash.
16. Repeat series captured: at least 3 captures of the same location (`MIN_REPEATS`).

Recommended practice: capture at least 30 s (`MIN_DURATION_SECONDS`) per repeat, with the same device and settings. Capture repeats at different times when the question involves time-varying sources. Capture negative-control locations with the same equipment.

## Metadata fields

`ReferenceMetadata`: `location_id`, `captured_at_utc`, `operator`, `recorder_make_model`, `recorder_serial`, `microphone_make_model`, `input_chain`, `channel` (zero-based), `sample_rate_hz`, `placement`, `orientation`, `height_m`, `source_signal`, `occupancy_activity`, `weather`, `calibration`, `repeat_index` (≥ 1), `deviations`, `consent_authority`, `notes`.

Required for storage: `location_id`, `captured_at_utc` (with timezone), `operator`, `recorder_make_model`, `microphone_make_model`, `sample_rate_hz` > 0, `consent_authority`, `source_signal` and `placement`. `height_m` must be finite and non-negative when given.

## Quality grading (beta rules, unvalidated)

- **insufficient**: metadata invalid, decoded sample rate differs from the documented rate, or the documented channel does not exist. The app refuses to save the reference.
- **C**: duration under 30 s, clipping reported, `repeat_index` exceeds the repeat count, or checklist under 60 % complete.
- **B**: duration or repeat count not supplied, fewer than 3 repeats, no source hash, or checklist incomplete.
- **A**: every checklist item satisfied and no issues.

## Storage and ranking

References are stored in the case database (`reference_recordings`), bound to the evidence row and its SHA-256, with the latest stored fingerprint for that channel. `rank_against_references` compares a query fingerprint with every reference that has the same fingerprint version. Incompatible references are listed as *skipped* rather than silently dropped, and sample-rate differences are noted. Every row carries the ranking caveat. The query recording itself is excluded from its own ranking.

## Interpretation limits

Ranking reflects only the measured descriptors in the fingerprint. Those descriptors are sensitive to device, placement, occupancy, time of day, codec and processing. Without a validated dataset and a calibrated evaluative framework (see `BENCHMARK_PROTOCOL.md`), rankings support investigative triage only.
