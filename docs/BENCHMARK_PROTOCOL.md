# Benchmark and field validation protocol

## Synthetic software benchmark

`audio-enviro-fingerprint benchmark --quick --seed 1` emits JSON for benchmark `aefp-bench-2`. Omitting `--quick` increases the dataset size. The renderer and comparison/transition scenarios were ported from `claude/magical-allen-bw1af4`; recurrence evaluation was adapted to the active frame-return API. Earlier benchmark numbers are not comparable.

Synthetic noise environments vary spectral tilt, resonance, level, exponential impulse response and hum. Independent repeated renders support same/different descriptor comparisons. Confounded renders add gain, band limiting or foreground events. Outputs contain score distributions, synthetic ROC AUC, and comparison/transition threshold sweeps. Recurrence tests A-B-A, A-B-C and C-B plans and reports candidate windows overlapping a constructed return interval. It does not report field precision or recall. The seed and configuration are exported; fixed-seed regression checks deterministic output and finite JSON.

These scenarios exercise software, not scientific suitability. No benchmark result establishes physical-location identification, calibrated error rates or authentication.

## Representative field dataset still required

Collect at least three captures per location per session across two days, including acoustically similar negative locations. Use at least three recorder/microphone combinations and document AGC/noise suppression. Include gain, codec, sample-rate, band-limiting, movement, activity and weather confounders. Capture annotated walk-through transitions and same-room source-change negatives. Record operator, consent/authority, equipment, placement and calibration through the Reference form; hash originals at intake.

Preregister hypotheses and metrics. Split by location before training or threshold selection, so a location cannot occur in both training and test sets. Freeze fingerprint, comparison, transition and recurrence method versions before testing. Report ROC/DET curves, location-bootstrap uncertainty, false-positive rates, device effects and confounder effects. Release the dataset hash manifest, method versions and results for independent review. Only a representative independent field study can support calibrated claims.
