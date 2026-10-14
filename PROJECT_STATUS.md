# Project status

## Current phase

0.2.0-beta.1: the three requested distinctive features (recurrence detection, explainable comparison, reference acquisition) are implemented on top of the 0.1 beta core, plus channel selection and cancellable background analysis.

## Verified locally (Linux, headless)

- 31 automated tests pass (core integrity/decode/features/transitions plus recurrence A-B-A, continuous and A-B negatives, cross-recording match/negative control, comparison symmetry and contribution sums, reference validation, immutability triggers, hash re-verification, quality review, channel selection, cancellation, report serialization).
- The Tk GUI cannot run locally (no Tk in this container). It is built and smoke-launched on Windows and Linux CI only; interactive use has not been exercised by a human.

## Scientific validation status

Not forensically validated. All thresholds (transition 0.35, recurrence match 0.80 / departure margin 0.15, quality limits) are heuristic and tested only on synthetic noise. Scores are descriptive, not probabilities. No location attribution or authenticity conclusion is produced.

## Known limitations

- PCM WAV only (no compressed audio, no RF64); full file decoded into memory.
- One channel analyzed at a time.
- Recurrence boundaries are uncertain by about one analysis window.
- Reference metadata is self-reported; the software cannot verify it.
- No signed manifests, encryption or multi-user access control.

## Not implemented (needs data or external validation)

Codec support with provenance, scientific benchmark/calibration on representative recordings, ENF, event recognition, scene classification, stereo/spatial features.
