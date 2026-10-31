# Specification, consolidation, audit and usability implementation plan

> **For agentic workers:** Execute bounded tasks with exclusive module ownership and regression tests before fixes; lead integrates and reviews.

**Goal:** Deliver the current beta specification, reconcile available branch work, audit all application modules, and add five usability improvements.

**Architecture:** Preserve Python/NumPy methods, SQLite evidence binding, native Tk desktop, CLI, and read-only evidence. Add small persisted preferences/timecode helpers and an escaped static HTML view of the existing manifest-bearing report. Keep original JSON as the verification artifact.

**Tech Stack:** Python >=3.10, NumPy, Tk, SQLite; optional local FFmpeg.

**Spec:** docs/SPECIFICATIONS.md and docs/SPECIFICATIONS_V2.md; V2 and later additions override historical inventory. Original user directive authorizes autonomous routine design, implementation, workers and integration; no design approval pause required.

## Design choices

Reuse current architecture rather than merge incompatible alternate applications wholesale. Compare remote branches and port remaining useful behavior; preserve historical refs and record supersession. User asked consolidation, not deletion of branch history or public release. Signed native bundles and scientific validation require external facilities/data and are tracked separately, never claimed by software tests.

Five usability features chosen by lead: (1) persisted recent recording menu with missing-file recovery, (2) quick analysis toggle that skips musical descriptors and visibly clears stale values, (3) seconds/MM:SS/HH:MM:SS input plus timeline/transition navigation, (4) edit selected marker with append-only history and precise timestamps, (5) readable printable HTML report retaining evidence/fingerprint identifiers and limitations with all analyst text escaped. These serve repeated review, slow files, accurate annotation and sharing without adding new scientific claims.

## Global constraints

- No modification of source evidence, no output over evidence/case aliases; no NaN/Infinity in report data.
- Same fingerprint schema and descriptive threshold meaning; changed implementations receive explicit provenance/version consideration.
- Python >=3.10; avoid new runtime dependencies.
- Fix concrete defects with failing regressions; full integrated suite and actual Tk smoke before completion.

## Review focus

1. Changed/deleted evidence at worker completion must retain last successful analysis and report actionable error.
2. Invalid paths/FIFOs must fail before hashing, never block UI/pipeline.
3. Time boundaries, silence, sample rounding and configured frequency/BPM limits must produce truthful measurements.
4. Missing/corrupt preferences and recent paths must not prevent startup.
5. HTML exports must escape markup, preserve source/database protection and recheck evidence.

## Tasks and ownership

| ID | Owner / owned surfaces | Dependencies | Status / required acceptance |
|---|---|---|---|
| AEF-101 | audit: methods, fingerprint, multichannel, recurrence + new focused tests; AUDIT_METHODS.md | current specs | DONE: audit coverage then regression-fix bounds/lag/recurrence/metadata defects |
| AEF-102 | wav_limit: audio_io, integrity, pipeline, report, case_store, control + focused tests; AUDIT_CORE.md | current specs | DONE: audit coverage; reject invalid hash chunks and nonregular inputs, support valid RF64 tables |
| AEF-103 | ui_audit: app, ui_tabs, preferences/timecode helper + GUI regressions; AUDIT_UI.md | AEF-101/102 contracts preserved | DONE: audit then fix GUI workflow failures and implement usability features 1–4 |
| AEF-104 | branch_reconcile: BRANCH_RECONCILIATION.md; proposed ports only until ownership transfer | remote branch enumeration | DONE: inventory every tip, ancestor/unique changes, preserve useful additions without legacy regressions |
| AEF-105 | lead: html_report.py, cli.py, HTML tests, documentation/tasks and integration git state | report.build_report/write_export, UI adapter uses write_html_report | DONE: static HTML via CLI and GUI, evidence recheck and safe atomic export |
| AEF-106 | lead and independent final reviewer: suite, real GUI smoke, benchmark, package, full diff | all above | INTEGRATING: fix all material findings, consolidated commit and honest limitations |

### Execution steps for each implementation

- [x] Read owned source/spec and audit; write failing real-behavior regression and observe expected failure.
- [x] Implement smallest correction/addition; run focused tests.
- [x] Peer review boundary changes; lead runs integrated tests, synthetic benchmark, compile/package and GUI smoke.
- [ ] Update audit finding disposition and specification traceability; create local consolidated commit only after review.

## Feature interfaces

HTML module produces `render_html_report(report: dict) -> str` and `write_html_report(path, report, *, protected_paths=(), should_cancel=None) -> None`. Uses existing schema and evidence SHA-256; GUI export worker may choose it with a format argument. CLI analyze accepts `--format json|html` (default json), requiring explicit output for html or prints HTML to stdout with no incidental text.

GUI owns preferences helper API internally. All background jobs publish queue events; SQLite stays on Tk thread. Comparison/search input result snapshot cannot switch while busy. Marker delete/edit reads exact stored record keyed by selection, never reparses display rounding.

## Resource and delivery state

Baseline HEAD 4343f34; previous session's tested diff remains preserved. One Linux environment, bounded workers with exclusive files, no paid resources added. Shell Git fetch is currently blocked by unavailable proxy; GitHub read connector works. Native Windows/macOS builds and field-data calibration must be reported separately from local software completion.
