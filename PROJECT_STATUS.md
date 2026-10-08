# Project status

## Current phase

Initial beta implementation and platform packaging. Repository was empty at start; this branch bootstraps the application.

## Verified locally

- PCM WAV integer decoding for supported format widths; analysis uses channel 1.
- SHA-256 for source bytes and versioned canonical acoustic features are separate.
- Framewise RMS, spectral centroid, flatness, and fixed-band power descriptors.
- Candidate transitions with visible per-feature deltas.
- Version-checked, explainable whole-recording fingerprint comparison.
- Experimental Schroeder decay-slope estimator for impulse responses.
- Timestamped SQLite notes bound to the source SHA-256.
- Tk desktop interface and JSON report export.
- Linux source-level test suite: 15 tests passed in the last completed run; rerun after final audit.

## Scientific validation status

Not forensically validated. Tests currently use synthetic signals and basic integrity cases. Comparison score and transition threshold are heuristic. No location attribution, authenticity conclusion, ENF, learned classifier, controlled reference acquisition, or recurrence analysis is implemented.

## Beta limitations

- PCM WAV only; no compressed audio or RF64.
- Only channel 1 is analyzed.
- Full WAV is decoded into memory.
- Tk GUI has not been interactively exercised in this headless environment.
- Windows executable can only be built and smoke-tested on Windows CI/host.
- Known-location acquisition and environment recurrence detection remain TODO.

## Next milestones

1. Finish source audit, edge-case QA, and test suite.
2. Run separate Windows/Linux CI package builds and inspect artifacts.
3. Add or repair features based on CI, then verify launch behavior on both platforms.
4. Develop representative acoustic benchmark protocol and data before treating any score as evidence.
5. Implement the three requested distinctive future features with separate specifications and validation records.

