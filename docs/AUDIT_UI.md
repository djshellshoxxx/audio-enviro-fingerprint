# UI, CLI and packaging audit — 2026-10-30

Task AEF-103. Read-only production audit against `SPECIFICATIONS.md` and `SPECIFICATIONS_V2.md`; inspected local revision `4343f34` plus maintenance changes in the shared workspace. Source changes are owned by the lead, not this audit.

## Coverage

| Surface | Examined behavior | Result |
|---|---|---|
| `app.py` | Evidence load/apply, progress queue, cancellation, comparison, cross-search, notes, markers, reference save, report/PNG exports, close and smoke path | Findings UI-01–UI-04 below |
| `ui_tabs.py` | Spectrogram render/click, musical/hum, recurrence table, channels and guided reference form | Finding UI-05; stale reference form caveat |
| `cli.py` | Analyze/stdout/output, compare, recurrence, spectrogram, cluster, benchmark, verify, parser and error codes | Commands match current documented contracts; no new confirmed defect in this scope |
| `launcher.py`, `__main__.py`, `run_app.py` | Argument routing and lazy Tk import for CLI | Matches specification |
| `.github/workflows/build-beta.yml` | Four native targets, dependency installation, tests, PyInstaller, GUI smoke, archives/checksums/release | Matches documented unsigned release process; no current platform results established by reading YAML |
| `docs/BUILDING.md`, `pyproject.toml` | Source install, required/optional dependencies, entry point and builder commands | Version and entry point agree; decoded-size text needs updating after maintenance inclusive-limit correction |

## Confirmed findings

### UI-01 — high: cross-recording search reverses the requested search direction

`app.py:274` offers to search the current recording's environment in another recording, then calls `find_recurrences(current, other)`. Cross mode reports one best reference match for each frame of its first argument. Consequently this direction can omit additional occurrences in the selected search recording.

Reproduced with current = 4 seconds of 440 Hz; selected other = 8 seconds of 1500 Hz, 4 seconds of 440 Hz, 8 seconds of 1500 Hz, 4 seconds of 440 Hz. Current call returns only current 0–4 matched to other 8–12; reversing the arguments returns both search candidates 8–12 and 20–24. The result table also needs its “This” and “Other” columns mapped to the corrected argument order.

Acceptance: both occurrences appear in the other-recording column; current-reference times stay 0–4; no source or current result changes.

### UI-02 — high: comparison and cross-search block Tk and cannot be cancelled

`app.py:247` decodes and extracts features synchronously; `app.py:274` runs the full secondary analysis and quadratic cross-recurrence synchronously. Neither action checks `busy`. While either callback runs, Tk cannot repaint, handle Cancel, or close normally. This diverges from the worker/progress convention already implemented for primary analysis and report export. Additionally `apply_result` recomputes the entire source hash on Tk through `CaseStore.register_evidence`, so the end of a primary analysis can block again.

Evidence: call graph from Tk button handlers directly into `load_audio`, `analyze_audio`, `analyze_file`, `find_recurrences`, and `register_evidence`; no worker or scheduling boundary intervenes. Runtime GUI latency requires a display and a large file, neither supplied for this read-only audit.

Acceptance: expensive comparison/search/hash verification runs off Tk; duplicate operations are blocked; cancellation retains current evidence and emits no result window; callbacks apply only completed snapshots on Tk.

### UI-03 — medium: disappearing source causes an uncaught result-application error

`app.py:195` calls `register_evidence` outside an error guard after the worker succeeds. Deleting/moving the source between analysis completion and result application raises `FileNotFoundError` from the Tk callback. The previous result and evidence ID remain, but the examiner gets no controlled application error.

Reproduced without a display by calling `FingerprinterApp.apply_result(SimpleNamespace(store=CaseStore(...), evidence_id=42, result={'old': True}), {'path': missing_path, 'sha256': '0'*64})`: uncaught `FileNotFoundError`. This is distinct from the already tested digest-mismatch branch.

Acceptance: a deleted/unreadable evidence file or database registration failure shows an error and leaves the previous successful evidence binding and visible results intact.

### UI-04 — medium: deleting a marker alters its timestamp through display rounding

`app.py:407` formats marker time with two decimals. `delete_marker` reads that display string and writes it into the tombstone revision. Reproduced using a real `CaseStore`: marker 1.23456 becomes revision timestamps `[1.23456, 1.23]` after deletion through the callback.

Acceptance: deletion reads the authoritative marker record by key, preserving exact stored time and label; missing/deleted selection and SQLite errors are handled. Display formatting must not serve as persistence input.

### UI-05 — medium: skipped musical analysis leaves previous recording's results visible

`ui_tabs.py:MusicalTab.update_result` returns immediately for `musical=None` after changing only the summary. Existing dominant tones, key candidates and hum text remain. Reproduced with a simple widget stand-in: after skipped result, old tones/keys/“60 Hz old hum” remain beside “Musical analysis was skipped”. Current GUI always requests music, but the pipeline and CLI already support skipping and a GUI quick mode would expose this directly.

Acceptance: clear tones and key rows when skipped and update hum independently; switching between full/quick results never shows values from a different evidence recording.

## Other observations and limits

- Reference form fields and `last_review` survive a new evidence load. Shared recorder metadata can be useful, but location/date/consent/placement should not silently look like a reviewed acquisition for the new file. An explicit template/reset affordance is preferable.
- Reference save and marker delete lack the broad error guard used by note save. A locked/unwritable case database can therefore surface as an uncaught callback.
- Native Tk widgets expose keyboard navigation, but only Open has an accelerator; no screen-reader/contrast/platform keyboard audit was executed.
- The single-row toolbar contains many long labels and can clip at the declared 900-pixel minimum width; visual verification requires a display.
- No GUI or native-packaged smoke was run by this audit worker. Existing tests exercise CLI and service modules and do not establish responsiveness or visual accessibility.
- Signed releases, notarization and representative scientific validation remain explicitly excluded by the beta specifications, not hidden acceptance passes.

## Five bounded usability improvements recommended after correctness fixes

1. **Recent recordings and reopen:** save a small local most-recent list of successful evidence paths; show file name/path and handle missing files without discarding current analysis. Do not trust cached hashes as fresh analysis.
2. **Quick analysis toggle:** expose existing `musical=False` through a visible desktop control. Label skipped methods clearly and preserve ordinary acoustic/transition/recurrence/hum/channel analysis.
3. **Marker editing and navigation:** select a marker to populate exact time/label, append an edit revision, and jump note time from marker/transition/recurrence rows. Keep raw values separate from formatted cells.
4. **Readable examiner summary:** explicit HTML or text summary export alongside existing manifest JSON, with provenance, warnings and numerical values. Escape untrusted notes/paths; preserve source/database overwrite protection.
5. **Batch report generation:** CLI `batch` with explicit output directory, per-file successes/errors, deterministic collision-safe naming and nonzero status on partial failures. Reuse `analyze_file`/`write_report`; never silently overwrite evidence or unrelated outputs.

These are proposals for the lead to select and document, not assertions that they are implemented.

## Implementation disposition and verification

All five confirmed findings UI-01–UI-05 are corrected in this session. Comparison/search use worker jobs with cooperative cancellation and busy guards; search direction follows the selected recording's timeline. New pipeline stat tokens support verified SQLite registration without reading the evidence again on Tk, while deleted/changed inputs or registration errors retain the preceding result. Marker edits/deletes use exact stored values and append history. Musical skip clears tables and still updates hum.

Implemented usability features 1–3 from the recommendations (recent recordings, quick mode, marker editing/navigation), extended annotation input with seconds/MM:SS/HH:MM:SS, and wired the lead's HTML export API. The lead selected readable HTML as the fifth feature together with clock/timeline annotation as a separate usability feature; batch reports remain a proposal rather than shipped functionality. Reference forms reset when new evidence is applied, persistence errors are shown, and the toolbar uses two rows to fit the supported desktop width.

Lead review caught a settings/evidence path collision: recent-history publication could replace a WAV deliberately named `preferences.json` in the application home. A failing regression reproduced this; the helper now refuses the source's resolved path and hardlink aliases. Corrupt recent settings containing NUL paths are rejected. These preference failures are nonfatal and never prevent viewing successful analysis.

Verification at handoff: 14 new desktop/helper checks pass, including 3 actual Tk workflows on local display `:97`; the existing `AEFP_SMOKE_TEST=1` GUI workflow passes. The complete integrated suite passed 122 tests before the final two preference regressions were added. The final full-suite count is owned by lead integration. No packaged Windows/macOS or visual screen-reader assessment is claimed here.
