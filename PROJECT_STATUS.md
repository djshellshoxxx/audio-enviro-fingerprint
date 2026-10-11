# Project status

## Current phase

Feature-complete research beta `0.2.0-beta.1`. All backlog items in `tasks.json` are implemented to beta level. Scientific validation on representative real-world data has not been done (see "Scientific validation status").

## Implemented and verified locally (Linux, Python 3.12, Xvfb)

- Input: PCM/float/extensible WAV (built in), FLAC/AIFF/OGG/MP3/RF64/W64 via optional soundfile. Decoder provenance and lossy flag recorded.
- Multichannel: all channels retained, any channel selectable, descriptive inter-channel statistics.
- Separate SHA-256 evidence hash and versioned `aefp-1` acoustic fingerprint. The hash is re-checked after decode and at export.
- Framewise RMS, centroid, flatness and band descriptors, with background analysis, progress and cancellation.
- Transition candidates with per-feature deltas. Manual markers with reasoned edits, soft delete and revision history.
- Environment recurrence within and across recordings, with saved runs.
- Explainable comparison: per-feature deltas, contribution shares and group summary.
- Known-location reference acquisition: metadata form, checklist, grading and caveated ranking.
- Case database schema v2 with in-place migration from the 0.1 schema.
- `aefp-report-2` export with hash manifest and verifier (GUI and CLI).
- Headless CLI (`aefp analyze | compare | verify-report | benchmark`).
- Deterministic synthetic benchmark.
- Test suite: 59 tests passing, including end-to-end GUI workflow tests under Xvfb.
- Linux PyInstaller bundle built and smoke-tested locally with WAV and FLAC input.

## Verified in CI only

The Windows folder build and the Windows single-file executable can only be built and smoke-tested on the Windows runner. See the "Build beta" workflow runs for this branch.

## Scientific validation status

Not forensically validated. The synthetic benchmark shows that gain/AGC and band-limiting confound comparisons, and that default thresholds are untuned (transition F1 ≈ 0.6 on synthetic data). The comparison score is descriptive and not calibrated. No location attribution, authenticity conclusion, ENF analysis or learned classifier is provided. The real-data protocol is in `docs/BENCHMARK_PROTOCOL.md`.

## Known limitations

- Whole-file in-memory decode. Very long recordings need proportional RAM.
- Analysis uses one selected channel at a time. Spatial statistics are descriptive.
- Reports have a hash manifest but are not digitally signed. There is no multi-user access control or encryption.
- Executables are unsigned.
- Accessibility (screen reader) review has not been done.

## Next milestones

1. Acquire the representative validation dataset and run the preregistered protocol.
2. Calibrate (or replace) thresholds and the descriptive score from that data.
3. Streaming decode for long recordings; signed report manifests.
4. Additional independent methods from `docs/FUTURE_FEATURES.md`, each with its own validation record.
