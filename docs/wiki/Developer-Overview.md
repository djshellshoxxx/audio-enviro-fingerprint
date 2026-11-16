# Developer Overview

The application is Python 3.10+ with NumPy and a native Tk/ttk interface. Headless CLI commands import Tk lazily through `launcher.py`; core numerical modules have no GUI dependency. Optional codecs use a restricted local FFmpeg child process, never a shell or remote playlist.

## Data flow

`analyze_file(path)` resolves a regular local file, records its original-byte SHA-256, decodes to `AudioData`, extracts `AnalysisResult` frames, constructs a versioned fingerprint and runs transitions, recurrence, hum, channels and optional musical analysis. It verifies source integrity before returning. The source hash and acoustic fingerprint hash are deliberately separate.

`full_report(result)` builds `aefp-report-2` sections and a canonical-body SHA-256 manifest. Reports retain algorithm IDs, decoder provenance and limitations. `write_report` rechecks source bytes before atomically writing a destination distinct from evidence and protected database paths.

SQLite stores original evidence references, timestamped notes, acquisition reviews and append-only manual marker revisions. Compatible legacy persistence additions use the current schema rather than parallel stores with incompatible APIs.

## Method versions

- Acoustic fingerprints: current `aefp-2`, rounded canonical serialization with normalized negative zero.
- Comparison: `comparison-symmetric-v2`, named feature deltas and uncalibrated score.
- Recurrence: current `recurrence-v1` fixed-scale frame-vector returns with departure checks; historical segment-based branches are incompatible alternatives.
- Musical/hum/multichannel: independently identified heuristic modules, with caveats in reports.

The original specification remains historical context; [SPECIFICATIONS_V2](../SPECIFICATIONS_V2.md) supplements it. Changing measured feature definitions or serialization requires explicit version/reproducibility review.

## Execution and resources

Tk owns widgets and SQLite connections; background workers perform expensive analysis/report work and send outcomes through a queue. Cancellation is cooperative. Frame extraction and recurrence include checkpoints. Full decoded audio remains in memory within the configured decoded-byte limit. Recurrence uses linear working memory but quadratic time.

Four native CI targets build separately: Linux x86_64, Windows x86_64, macOS ARM64 and macOS Intel. Unsigned build artifacts and successful synthetic tests do not establish scientific calibration.
