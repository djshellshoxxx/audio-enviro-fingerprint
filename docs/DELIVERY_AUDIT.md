# Specification acceptance, full application audit and delivery

Date: 2026-10-30 (America/Los_Angeles). Development version: **0.3.0b2**. Integration branch: `codex/spec-audit-usability`; base `4343f34f509216dbecd4e1dd6c86542fe913d672`.

## Scope and finish line

The current beta contract is `SPECIFICATIONS.md` plus its V2/v0.3 supplements. Statements explicitly labeled known gaps/future research are not implemented product promises. The deliverable is a working research desktop/CLI beta with truthful measurements/provenance, preserved evidence, current documentation, branch reconciliation, and five additional usability features. It does not deliver scientific calibration or a release signed for each native platform.

## Requirement traceability

| Requirement | Integrated implementation / acceptance evidence |
|---|---|
| Read-only PCM 8/16/24/32, float32/64, extensible, RF64, all channels | `audio_io.py`; core/extended/input-hardening/WAV-limit/RF64-table tests; bounded metadata and decoded-size checks before sample allocation |
| Local compressed inputs and provenance | `codec_io.py`; real FFmpeg FLAC/stereo and MP3 tests, exact-limit acceptance and over-limit rejection |
| Byte hash separate from acoustic hash; stable analysis input | `integrity.py`, `pipeline.py`; pre/post source hashes and identity/metadata token; nonregular paths and invalid chunk sizes rejected |
| Finite versioned descriptors and comparison | Noise/spectral/hum/musical/fingerprint/comparison modules; numeric/rate/silence/golden-hash tests; tempo/pitch bounds and unavailable silent-channel lag |
| Transitions and recurrence with supporting measurements | `transitions.py`, `recurrence.py`; rounded clocks, exact minimum gap, valid earlier-reference departure, repeated cross-search tests; linear working memory and quadratic time |
| Per-channel metrics and guided references | `multichannel.py`, `reference.py`; channel-delay, silence, clipping, UTC/height/repeat and reference-review tests |
| Evidence-bound notes, marker revisions, append-only acquisitions | `case_store.py`; finite timestamps, foreign keys, marker ownership/history, migration-compatible SQL guards, logical-key REPLACE regression, pinned registration |
| Reports and evidence-safe export | JSON manifests, source recheck, protected source/database aliases and atomic publication; notes/references/marker history/recurrence history preserved |
| CLI and worker GUI | Existing analyze/compare/recurrence/spectrogram/cluster/benchmark/verify commands; Tk analysis/compare/search/export jobs with busy/cancel handling; actual GUI workflows |
| Native packaging | Existing four-target CI retained; local wheel and Linux packaged smoke checked separately below; other native targets require their runners |
| Branch consolidation | Every remote tip inventoried in BRANCH_RECONCILIATION.md; compatible functionality ported, incompatible legacy variants explicitly superseded; exact ancestry checks recorded below |

## Five usability features

1. **Recent recordings:** most recent ten successful opens, de-duplicated; missing files retain the previous result. Invalid/unrecognized preferences are read as empty and their bytes are preserved rather than overwritten, including a recording named `preferences.json` across later opens and restarts.
2. **Quick analysis:** visible desktop toggle skips musical descriptors; skipped tables clear and current hum still updates. CLI keeps its existing `--no-musical` flag.
3. **Timecode annotation and navigation:** seconds, MM:SS and HH:MM:SS with fractional seconds; reject nonfinite/negative/out-of-duration values; select a transition or click the timeline to set note time.
4. **Marker editor:** select a marker, edit time/title, save a new revision. Raw stored precision survives selection/deletion; history remains exportable.
5. **Printable HTML report:** desktop `.html` export or `analyze FILE --format html -o report.html`. Escaped static content, complete JSON record, hashes, limitations and method values; no scripts/external resources. Original JSON remains the `verify` input.

## Audit coverage and disposition

All product application modules under `src/audio_enviro_fingerprint`, associated regression suites, dependency manifest, launcher and release workflow were inspected across independent core, numerical and UI reviews. Bundled skill libraries and inherited generic shared project-creation scripts are not runtime components and were not represented as audited application code.

- [Core audit](AUDIT_CORE.md): CORE-01–03 fixed (nonregular hash hang, invalid hash chunk size, RF64 ancillary sizes).
- [Methods audit](AUDIT_METHODS.md): M-01–05 fixed (tempo range, pitch range, silent-channel lag, malformed fingerprint input, eligible-reference selection). Shared frame-clock validation and stale formula terminology corrected.
- [UI audit](AUDIT_UI.md): UI-01–05 fixed (search direction, blocking jobs, failed apply, timestamp precision, stale musical values).
- Independent final whole-change review found two additional preservation gaps: preferences across successive opens and logical-key SQLite REPLACE; both required failing regressions and were corrected before delivery.
- HTML reviewer found malformed nested report fields raising implementation errors; renderer now rejects them as ValueError with regression coverage.

These reviews and tests establish software behavior only. They do not establish legal chain of custody, authenticity, physical location or forensic error rates. SQL guards protect accidental mutation on the application connection; they are not a security boundary against a database owner. Stat tokens detect ordinary changes; they do not eliminate adversarial filesystem races.

## Verification and consolidated revision

Frozen-source checks: **128 tests PASS, no skips**, including three actual Tk workflows and real FFmpeg FLAC/MP3 tests. Source GUI smoke PASS. Compileall, deterministic quick synthetic benchmark, wheel build, Linux PyInstaller build and packaged GUI smoke PASS; packaged version is 0.3.0b2. Packaged smoke ran without the builder LD_LIBRARY_PATH override. Independent follow-up checks confirm both final-review preservation defects resolved (14 helper/store tests PASS). No release tag or public binary publication performed.

Verification commands:

```bash
DISPLAY=:97 PYTHONPATH=src python -m unittest discover -s tests -q
DISPLAY=:97 AEFP_SMOKE_TEST=1 PYTHONPATH=src python -m audio_enviro_fingerprint
python -m compileall -q src tests
PYTHONPATH=src python -m audio_enviro_fingerprint benchmark --quick
python -m pip wheel --no-deps --no-build-isolation .
# Build follows BUILDING.md with isolated PyInstaller and relocated-library accommodation.
DISPLAY=:97 AEFP_SMOKE_TEST=1 /path/to/dist/AudioEnvironmentFingerprinter/AudioEnvironmentFingerprinter
```

Build/benchmark logs and binaries are retained under `/workspace/work/audio-enviro-fingerprint`. The local virtual display exists only for tests and is stopped at handoff. No additional cloud instances were provisioned. The integration branch and Git graph identify the exact final revision; ancestry checks cover all ten fetched remote heads.

## Remaining limitations and external work

- Full streaming analysis is not implemented. Decoded sample storage is capped; temporary arrays and long-recording runtime still require independent performance work. Recurrence time remains quadratic; decoder/music cancellation is cooperative at documented boundaries.
- Representative controlled/field recordings, calibrated thresholds, cross-device robustness, measured-IR reference validation and accessibility review remain required before broader claims.
- Windows/macOS native bundle validation, signing and notarization require their target runners/credentials. A local Linux build is not evidence those platforms passed.
- Legacy branches' alternative scientific methods, stored reference ranking, selected-channel decoder API and chained reference schema were deliberately superseded/deferred with reasons. Historical commits remain preserved in the consolidated graph; no old scientific variant is silently presented as the current method.
