# Scientific and numerical module audit

Audit date: 2026-10-30 (America/Los_Angeles). Owner: AEF-101 methods reviewer.
Inspected revision: `4343f34f509216dbecd4e1dd6c86542fe913d672`, plus the shared working tree. This is a software-contract audit, not scientific calibration or physical-location validation. Findings below record behavior observed before coordinated repairs; resolution requires rerunning the specified acceptance checks on the integrated revision.

## Requirements and coverage

Sources of truth: `SPECIFICATIONS.md`, `SPECIFICATIONS_V2.md`, `VALIDATION.md`, `BENCHMARK_PROTOCOL.md`, and the current module/API documentation. Older inventory statements are superseded by v0.2/v0.3 additions. Every module in the assigned scientific scope was read, including helper functions.

| Module | Contract examined | Evidence / result |
|---|---|---|
| `methods/noise.py` | Finite mono input, digital RMS and percentile labels, finite floors | Existing core/numeric tests; no new ordinary-input defect found. Values remain dBFS, not SPL/noise isolation. |
| `methods/spectral.py` | Hann one-sided PSD, even/odd scaling, fixed bands, Nyquist, centroid/flatness | Source and synthetic spectral tests reviewed. Integrated band power is implemented, while the older spec calls it mean power; documentation should use integrated band power consistently. Flatness excludes bins at/below a fixed numerical floor; this convention must be frozen before calibration. |
| `methods/reverberation.py` | Reverse energy integration, -5 to -25 dB regression, -60/slope, silent/short rejection | Existing synthetic exponential-decay regression. No ISO measurement or noise-floor compensation claim is warranted. |
| `methods/hum.py` | Resolved harmonic bins, flank median prominence, finite silence output, short-recording disclosure | Existing rate/silence tests and source reviewed. Availability and resolution disclosed; no ENF series or attribution. |
| `methods/musical.py` | Note conversion, peaks/chroma/key, YIN, tempo, summary | Findings METHOD-01/METHOD-02 below; other existing musical and numeric tests reviewed. |
| `methods/quality.py` | Duration/rate/clipping/DC/dropout review | Quality and reference tests reviewed; near-full-scale threshold is explicit. No field suitability established. |
| `features.py` | Complete overlapping windows, sample-quantized starts, finite mono/rate checks | Frame extraction reviewed against recurrence clock repairs. Requested durations remain metadata while actual windows are quantized. |
| `fingerprint.py` | Versioned canonical JSON, six-place quantization, negative-zero normalization, digest | Existing repeatability tests; finding METHOD-04 on direct malformed analysis input. |
| `comparison.py` | Same-schema compatibility, finite differences, symmetric centroid scaling, score explanation | Existing symmetry/version/finite tests reviewed; all reported differences are descriptive. No new defect found. |
| `catalog.py` | 1–64 unique resolved paths, stable ordering, all pair measurements, complete-link merging, cancellation | Existing grouping/order/threshold tests reviewed; source hashes and provenance retained. No new defect found. |
| `transitions.py` | Adjacent deltas, heuristic threshold, strongest-first temporal separation | Existing transition tests reviewed. Implementation aggregates by arithmetic mean; stale median source comment corrected without changing the formula. |
| `recurrence.py` | Normalized distance, departure requirement, cross matches, temporal grouping, bounded working memory | Clock regression repairs reviewed; finding METHOD-05 on reference selection. |
| `multichannel.py` | Independent channel fingerprints, zero-lag/peak correlation, lag/level/mid-side metrics | Existing lag tests; finding METHOD-03 on silent-channel lag. |
| `reference.py` | Required acquisition fields, UTC/height/repeats, technical checks, worst-status aggregation | Existing metadata/quality tests reviewed. Records describe operator claims, not verified location. |
| `spectrogram.py` | Bounded column count, finite mono/rate input, Hann magnitude, orientation, PNG chunks | Existing PNG/numeric tests reviewed. Zero padding for short audio and relative per-image color scale are implementation conventions, not calibrated spectral levels. |
| `validation.py` | Finite real mono arrays, positive integer rates, finite numeric parameters, frame consistency | Helpers reviewed. METHOD-04 exposed missing rate/frame-bound validation; shared validator now checks both before numerical consumers produce results. |
| `benchmark.py` | Deterministic synthetic rendering, comparison/transition/recurrence cases, labels | Existing deterministic finite-JSON test reviewed. Synthetic metrics are correctly distinguished from field performance. |

## Reproducible findings

### METHOD-01 — Medium: tempo can exceed the configured BPM maximum

`estimate_tempo` floors the minimum autocorrelation lag, although restricting BPM from above requires rounding the minimum lag upward. A legal signal and ordinary configured range return a result outside that range.

```python
import numpy as np
from audio_enviro_fingerprint.methods.musical import estimate_tempo
x = np.zeros(8000 * 8)
x[::2048] = 1
print(estimate_tempo(x, 8000, bpm_min=150, bpm_max=220))
# observed: bpm=234.375, confidence=0.967688659266232
```

Acceptance: every non-null estimate is within `[bpm_min, bpm_max]`, including range boundaries that map to fractional lag values; a range with no admissible lag returns unavailable. Preserve the heuristic confidence caveat.

### METHOD-02 — Medium: interpolated pitch can leave its requested frequency range

The integer lag search and parabolic correction do not constrain the resulting frequency to the advertised interval. This is a software bound violation, separate from expected estimation error.

```python
import numpy as np
from audio_enviro_fingerprint.methods.musical import pitch_track
for hz in (60, 1000):
    x = .1 * np.sin(2 * np.pi * hz * np.arange(8000) / 8000)
    print(hz, [p['f0_hz'] for p in pitch_track(x, 8000) if p['f0_hz']][:1])
# observed: 60 -> 59.9250936329588; 1000 -> 1006.6344918759456
```

Acceptance: all reported voiced pitches respect `[fmin, fmax]`; use a deliberate reject/interpolation-bound policy, without silently claiming calibrated accuracy. Cover exact and nearby lower/upper boundary tones and ordinary in-range tones.

### METHOD-03 — Medium: silent channels acquire an arbitrary apparent interchannel delay

For zero-energy demeaned signals, all cross-correlation bins are zero and `argmax` chooses the first lag. At 8 kHz the result is -12 samples / -1.5 ms, despite there being no measurable lag. A nonzero apparent delay can mislead spatial review.

```python
import numpy as np
from audio_enviro_fingerprint.multichannel import channel_pair_metrics
print(channel_pair_metrics(np.zeros(8000), np.zeros(8000), 8000))
# observed: peak_lag_samples=-12, peak_lag_ms=-1.5, peak_correlation=0
```

Acceptance: both-silent, one-silent, and constant/DC-only pairs expose unavailable or explicitly neutral lag consistently with UI/report handling. Preserve known-delay and opposite-polarity tests. An unavailable measurement must not look like a measured physical delay.

### METHOD-04 — Medium: fingerprints accept invalid direct analysis metadata

`make_fingerprint` does not call the shared analysis validator or rate validator. Negative rates/durations yield apparently well-formed, hashed `aefp-2` records. Inconsistent band layouts can instead raise `KeyError`. These violate the advertised independently reusable numerical API contract even though the normal decode pipeline supplies valid metadata.

```python
from audio_enviro_fingerprint.features import AnalysisResult, FrameFeature
from audio_enviro_fingerprint.fingerprint import make_fingerprint
frame = FrameFeature(0, -20, 100, .1, {})
a = AnalysisResult(-1, -1, 2, 1, [frame], {'frame_rms_dbfs_p10': -20})
print(make_fingerprint(a).features)
# observed: sample_rate_hz=-1, duration_seconds=-1.0, plus a valid digest
```

Acceptance: invalid sample rates, negative/nonfinite duration, invalid frame/hop, malformed frame/band data and inconsistent summary input raise `ValueError` before hashing. Preserve both supported comparison versions and valid `aefp-2` canonical bytes/hashes. Validate without introducing unversioned changes to valid numerical fingerprints.

### METHOD-05 — Medium: recurrence rejects valid earlier references after finding an ineligible nearest one

Within-recording mode chooses the minimum-distance reference first, then checks that reference for an intervening departure. If the nearest frame is a recent part of the return, it may lack departure while another within-threshold earlier reference satisfies the complete criterion. The qualifying frame is never tried. This truncates or fragments returns and conflicts with the spec's earlier-frame-plus-departure definition.

```python
from audio_enviro_fingerprint.features import AnalysisResult, FrameFeature
from audio_enviro_fingerprint.recurrence import find_recurrences
frames = [FrameFeature(t, level, 100, .1, {})
          for t, level in enumerate([-20, -100, -21, -21])]
a = AnalysisResult(10, 4, .2, 1, frames, {})
print([r.to_dict() for r in find_recurrences(a, min_gap_seconds=0)])
# observed: return includes t=2 only (end=2.2), excludes t=3
```

At t=3 the t=2 reference is distance zero but has no departure; the t=0 reference has distance ~0.03849 and intervening departure ~3.0792, satisfying defaults.

Acceptance: select the best reference among those satisfying the entire threshold/gap/departure predicate; cover a continuing return, nearer ineligible reference, no valid departure, and cross-recording behavior. Keep working memory linear; measure any runtime change before changing large-recording claims. If existing closest-only semantics are deliberately retained, revise the specification and record the limitation explicitly instead of presenting existential matching as implemented.

## Required software delivery vs research backlog

METHOD-01 through METHOD-05 are concrete software-contract gaps and should be resolved or explicitly accepted before claiming this audit's scope complete. Spectral integrated-power terminology and the transition mean/median comment should also be reconciled; neither justifies silently changing scientific formulas.

Representative field recordings, calibrated error rates/thresholds, cross-device robustness, ISO room measurement, ENF time series, scene/event classification, reflection inference and authenticity assessment require separate research/design and are not delivered by passing these tests. Full streaming decode and performance verification remain documented engineering backlog. Musical framing, hum segment arrays, full-recording channel FFTs and quadratic tempo/recurrence time remain relevant large-recording resource limits even when decoded audio is bounded.

The existing suite provides synthetic software checks, not representative field validation. No finding or repair authorizes location attribution or a probability of common location.

## Repair dispositions and verification

| Finding | Disposition in AEF-101 working tree | Regression evidence |
|---|---|---|
| METHOD-01 | Fixed: admissible integer tempo lags use ceil for minimum lag and floor for maximum; a valid single-lag interval is supported. | Fractional-bound impulse train, no-admissible-lag interval, exact admissible lag. |
| METHOD-02 | Fixed: interpolated pitches outside the requested interval are marked unvoiced with zero confidence, rather than clamped to a fabricated note. | Boundary and nearby tones at 60/61/999/1000 Hz; 440 Hz remains voiced and accurate within the software tolerance. |
| METHOD-03 | Fixed: zero demeaned channel energy yields null peak lag and `lag_available=false`; measurable pairs have `lag_available=true`. UI must display unavailable rather than format null as a number. | Both silent, one silent, DC-only and known delayed-noise channels. |
| METHOD-04 | Fixed: rate/frame metadata and required finite noise summary are checked before hashing. Shared frame validation also protects transition and recurrence consumers from invalid clocks and frames outside the recording. Existing valid serialization is preserved. | Malformed rates/durations/timing/bands/summary rejection; golden existing `aefp-2` hash. |
| METHOD-05 | Fixed: maintain a running departure maximum per earlier reference, filter the complete predicate, then choose nearest eligible reference. | Nearer ineligible reference cannot truncate a continuing return; no-departure negative and cross-recording positive. |

All audit fixes retain the existing method/schema IDs: they enforce documented domains and predicates without introducing a new scientific model or changing the valid fingerprint serialization. Recurrence candidate spans may change where the previous implementation failed its documented predicate; this repair and the application version must remain in report provenance.

Focused regressions were written and observed failing before implementation (`/tmp/aef-method-red.log` in this session). A full shared suite during concurrent implementation ran 109 tests and reported six failures/ten errors in newly added, unfinished GUI/HTML/store tests; numerical tests passed. Those failures are not excused: the lead must rerun the integrated suite after all owners finish. The pre-repair baseline ran 83 tests successfully (`/tmp/aef-method-audit-tests.log`).

A bounded synthetic resource smoke on this executor measured recurrence at 1000 frames: 0.092 s / 400756 peak traced bytes; 2000 frames: 0.142 s / 858766 bytes, including result construction. This is a local sanity check, not a large-field-recording performance certification. The implementation retains one query distance column plus one per-reference departure array, O(n) working memory and O(n²) distance work.

Final AEF-101 focused command:

```bash
PYTHONPATH=src:tests python -m unittest test_method_audit test_extended test_numeric_contracts test_fingerprint_reproducibility test_catalog test_benchmark test_recurrence_timing test_quality test_reference_validation test_core -v
```

Result: **61 tests passed** in 1.920 s, including seven audit tests. Log: `/tmp/aef-method-focused.log` (session-local). Newly added shared-clock regressions were observed failing first in `/tmp/aef-clock-red.log`. Full integrated verification remains the lead's completion gate, including null-lag UI formatting and all concurrent changes.

Later integration snapshot: 122 tests ran in 3.142 s; four errors remained in the in-progress HTML nested-report validation regression and three GUI-related tests were skipped pending a display. All other tests passed (`/tmp/aef-method-integrated.log`). This is an interim observation, not the final integration gate.
