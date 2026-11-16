# Developer Conventions

## Preserve evidence and clear claims

- Never rewrite original evidence, downmix implicitly or conflate its byte SHA-256 with the acoustic fingerprint.
- Pin source integrity across analysis and recheck it before report export. Protect evidence and active databases from destination aliases.
- Bind notes, markers, acquisitions and saved screening runs to the original evidence record. Preserve prior successful UI state on rejected imports.
- Keep raw measurements and per-feature differences visible. A descriptive score is neither a probability nor a likelihood ratio. No location identification or authenticity verdict is produced.
- Case history is append-only through application APIs and SQL guards. These protections prevent accidental mutation; a user controlling the database can alter it and the beta is not a complete chain-of-custody system.

## Modules and versions

Keep independent measurements in reusable modules without Tk imports. Validate finite real input, positive rates, supported shapes and explicit method settings. New scientific methods require their own method ID, input/output contract, tests, validation record and visible supporting values.

Current fingerprints use `aefp-2`; comparisons reject cross-schema pairs. Changes to features, bands, normalizers or serialization need explicit version/threshold review. Keep canonical JSON finite and deterministic, including negative zero normalization. Do not silently reinterpret legacy segment recurrence as the current frame-return `recurrence-v1`.

## Workflow

Inspect the relevant specification and established tests. Add a meaningful failing regression, implement the smallest coherent correction, run focused and integrated checks, and document limitations. Preserve uncommitted user work. Use exclusive file ownership or isolated worktrees for concurrent changes.

Tk widgets and SQLite stay on the GUI thread; expensive decode, analysis and hashing belong in workers. Cancellation must not publish a partial result. Core methods receive cancellation callbacks without depending on GUI widgets.

Update current user/developer documentation when behavior changes. [SPECIFICATIONS_V2](../SPECIFICATIONS_V2.md), [BENCHMARK_PROTOCOL](../BENCHMARK_PROTOCOL.md) and the latest [project status](../../PROJECT_STATUS.md) take precedence over historical branch narratives.
