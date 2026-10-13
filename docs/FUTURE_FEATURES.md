# Future feature backlog

All ideas here are unimplemented unless explicitly marked otherwise. Prioritize scientific validation and provenance before adding learned classification.

## Three distinctive features requested for this project

1. **Environment recurrence detection** — identify when an environment segment disappears and later returns within a recording or across recordings. Store segment IDs, matching features, threshold rationale, confounders, and uncertainty. Validate on repeated passes through known rooms and negative controls. The current beta compares whole-recording summaries only; it does not establish recurrence.
2. **Explainable fingerprint comparisons** — expose exactly which spectral, noise, reverberant, and other measurable characteristics drive similarities/differences. Preserve raw measurements and per-feature contributions. The beta has a preliminary version for spectral/noise features; complete it as each independent method is implemented, and do not collapse evidence into an opaque score.
3. **Known-location reference acquisition** — guided exemplar capture documenting location identifier, date/time, recorder/microphone make/model/serial, input chain, channel, sample rate, placement, orientation, height, source signal, environmental occupancy/activity, weather when relevant, calibration, operator, repeats, and deviations. Add controlled capture checklist, consent/authority fields, immutable source hashes, and reference-quality review. Never claim a match solely from a self-reported location label.

## Other high-value work from the master directive

- Recording recurrence search across a case and aligned segment matching.
- Controlled reference-environment catalog, clustering and candidate comparison.
- Manual transition markers and editable segmentation with revision history.
- Reflection/echo analysis, event recognition, mechanical signatures, electrical network frequency, stereo/spatial features, device/microphone confounders, and scene classification as individually validated modules.
- Robustness explorer for codec, sample-rate conversion, noise suppression, AGC, microphone motion, and background source changes.
- Blind comparison mode, method-agreement explorer, reference quality scoring, multi-recording reconstruction, and reproducibility package.
- Case export with manifest verification and examiner-configurable report templates.
- Larger-file streaming, cancellable analysis, progress reporting, and performance benchmarks.

