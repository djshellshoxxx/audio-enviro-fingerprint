# Future feature backlog

Items are unimplemented unless explicitly marked otherwise. Prioritize scientific validation and provenance before adding learned classification.

## Three distinctive features requested for this project

1. **Environment recurrence detection** — identify when an environment segment disappears and later returns within a recording or across recordings. Store segment IDs, matching features, threshold rationale, confounders, and uncertainty. Validate on repeated passes through known rooms and negative controls. **Implemented (beta):** `recurrence.py` splits recordings at detected transitions, summarizes segments by median features, and reports candidate non-adjacent/cross-recording segment pairs with per-feature deltas, an unvalidated threshold and listed confounders. The Recurrence tab searches the loaded recording plus any added recordings, and runs are saved to the case database. Still needed: validation on known rooms (docs/BENCHMARK_PROTOCOL.md).
2. **Explainable fingerprint comparisons** — expose exactly which spectral, noise, reverberant, and other measurable characteristics drive similarities/differences. Preserve raw measurements and per-feature contributions. **Implemented (beta):** per-feature raw and normalized deltas, each feature's share of the distance, and level/spectral-shape/band-power group summaries, in the Compare tab, CLI and API. Extend it as each new independent method is added, and do not collapse evidence into an opaque score.
3. **Known-location reference acquisition** — guided exemplar capture documenting location identifier, date/time, recorder/microphone make/model/serial, input chain, channel, sample rate, placement, orientation, height, source signal, environmental occupancy/activity, weather when relevant, calibration, operator, repeats, and deviations. Add controlled capture checklist, consent/authority fields, immutable source hashes, and reference-quality review. Never claim a match solely from a self-reported location label. **Implemented (beta):** `reference.py` and the References tab (metadata form, checklist, quality grade, ranking with caveat), stored in the case database. Protocol: docs/REFERENCE_ACQUISITION.md. Consent fields and source hashes are included. Immutable storage beyond the hash binding is not.

## Other high-value work from the master directive

- Recording recurrence search across a case and aligned segment matching.
- Controlled reference-environment catalog, clustering and candidate comparison.
- ~~Manual transition markers with revision history~~ (implemented). Editable segmentation is still open.
- Reflection/echo analysis, event recognition, mechanical signatures, electrical network frequency, stereo/spatial features (descriptive inter-channel statistics implemented), device/microphone confounders, and scene classification as individually validated modules.
- Robustness explorer for codec, sample-rate conversion, noise suppression, AGC, microphone motion, and background source changes.
- Blind comparison mode, method-agreement explorer, reference quality scoring, multi-recording reconstruction, and reproducibility package.
- ~~Report manifest verification~~ (implemented as `aefp-report-2`). Signed manifests and examiner-configurable report templates are still open.
- ~~Cancellable analysis and progress reporting~~ (implemented). Larger-file streaming and performance benchmarks are still open.

