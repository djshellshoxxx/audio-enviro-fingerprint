# Benchmark and validation protocol

## 1. Synthetic software benchmark (implemented)

`aefp benchmark [--quick] [--seed N] [--json]` (module `benchmark.py`, version `aefp-bench-1`). **This is a synthetic software benchmark, not forensic validation.** It checks that the pipeline behaves sensibly on signals whose ground truth is known by construction. Identical seed and mode give identical output.

**Simulated rooms:** coloured noise beds (random spectral tilt), a resonance, optional mains hum (50/60/100/120 Hz) and a random level. Each bed is convolved with a synthetic exponentially decaying impulse response (RT60 0.2–1.2 s).

| Scenario | Ground truth | Metrics |
|---|---|---|
| Whole-recording comparison | Repeats of the same room vs. other rooms | Same/different score distributions, ROC AUC, threshold sweep (TPR/FPR) |
| Confounders | Same room with +10 dB gain, 2 kHz band-limit, or 6 foreground events | Confounded-same-room acceptance, ROC AUC vs. different rooms |
| Transitions | Concatenated room segments; half include a +6 dB gain step that is *not* a room change | Precision/recall/F1 at ±2 s tolerance, threshold sweep |
| Recurrence | Recordings A-B-A, A-B-C and C-B | Segment-pair precision/recall/F1 by max distance, ROC AUC |

Example quick-mode result (seed 0): same vs. different room AUC 0.998, falling to 0.670 when same-room pairs are confounded. Transition F1 at the default threshold 0.35 is 0.61, with precision 0.54 and recall 0.70. The gain-step confounder drives the false positives. These numbers show the default thresholds are not tuned and that gain/AGC and band-limiting confound comparisons. **They are not error rates for real recordings.**

## 2. Representative validation dataset (required before evidential use)

### Design

- **Same-location repeats:** ≥ 3 captures per location per session, across ≥ 2 sessions on different days and times.
- **Cross-location negatives:** acoustically similar locations (same building type, similar rooms), not just obviously different ones.
- **Devices:** ≥ 3 recorder/microphone combinations, including phones with AGC/noise suppression on and off.
- **Processing confounders:** lossy codecs at several bit rates, sample-rate conversion, gain changes, band-limiting and telephony channels.
- **Transitions:** walk-throughs between rooms with annotated boundaries, plus same-room source changes (doors, HVAC, speech) as negatives, and known edits/splices.
- **Metadata:** every capture follows `REFERENCE_ACQUISITION.md` and is hashed at intake.

### Procedure

1. Preregister hypotheses, metrics, thresholds to be evaluated, and the train/test split by *location* (no location in both).
2. Freeze the algorithm version (`aefp-2` fingerprint, transition and recurrence code) before scoring the test set.
3. Report ROC/DET curves, AUC with confidence intervals (bootstrap by location), and false-positive rates at candidate thresholds, per device and per confounder.
4. Assess calibration only within a defined evaluative framework (e.g. likelihood ratios with Cllr). Until then the score stays descriptive.
5. Publish the dataset manifest (hashes), code version and results. Any algorithm change requires re-validation and a new version tag.

### Acceptance

No threshold may be presented as validated until steps 1–5 are complete and independently reviewed. Results apply only to the conditions represented in the dataset.
