"""Environment recurrence detection within one recording or across two.

A *recurrence* is a later stretch whose measured features return close to an
earlier stretch after an intervening departure. Distances use fixed,
uncalibrated feature scales (same convention as ``comparison``); the raw
per-feature differences are retained for every reported match.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from bisect import bisect_right
import math

import numpy as np

from .control import check_cancelled
from .validation import validate_frames

METHOD = "recurrence-v1"
CONFOUNDERS = ("Similar features can arise from a shared noise source (HVAC, mains hum) in "
               "different places.", "Level changes from gain or microphone distance can mimic departures.",
               "Distances are uncalibrated; a match is a review candidate, not an identification.")


@dataclass(frozen=True)
class Recurrence:
    segment_id: str
    earlier_start_s: float
    earlier_end_s: float
    later_start_s: float
    later_end_s: float
    mean_distance: float
    min_distance: float
    departure_peak: float | None
    feature_deltas: dict[str, float]
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


def frame_vectors(analysis) -> tuple[np.ndarray, list[str]]:
    """Normalized per-frame feature matrix (frames x features) and feature names."""
    validate_frames(analysis)
    names = ["rms_dbfs", "log2_centroid_hz", "spectral_flatness"]
    band_names = sorted(analysis.frames[0].band_power_db) if analysis.frames else []
    names += [f"band_power_db.{b}" for b in band_names]
    rows = []
    for f in analysis.frames:
        row = [f.rms_dbfs / 15.0, math.log2(max(f.spectral_centroid_hz, 20.0)) / 1.5,
               f.spectral_flatness / 0.25]
        row += [f.band_power_db[b] / 15.0 for b in band_names]
        rows.append(row)
    return np.asarray(rows, dtype=np.float64).reshape(len(rows), len(names)), names


def _distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    diff = a[:, None, :] - b[None, :, :]
    return np.sqrt(np.mean(diff * diff, axis=2))


def find_recurrences(analysis, other=None, threshold: float = 0.25, departure: float = 0.6,
                     min_gap_seconds: float = 6.0, *, should_cancel=None) -> list[Recurrence]:
    """Find returns to an earlier environment.

    With ``other`` given, every frame of ``analysis`` is matched against ``other``
    (no departure requirement; cross-recording matches are reported as-is).
    """
    if (not all(math.isfinite(v) for v in (threshold, departure, min_gap_seconds))
            or threshold <= 0 or departure <= threshold or min_gap_seconds < 0):
        raise ValueError("Require 0 < threshold < departure and nonnegative gap")
    if not analysis.frames:
        return []
    va, names = frame_vectors(analysis)
    timestamps = [frame.start_seconds for frame in analysis.frames]
    cross = other is not None
    if cross:
        if not other.frames:
            return []
        vb, names_b = frame_vectors(other)
        if names != names_b:
            raise ValueError("Recordings use different band layouts; cannot compare")
    else:
        vb = va
    matches = []                              # (j in analysis, i in reference, distance, depart)
    departure_peaks = np.zeros(len(va)) if not cross else None
    for j in range(len(va)):
        check_cancelled(should_cancel)
        # Subtracting decimal timestamps can place an exact gap boundary a
        # few float rounding steps below its reference timestamp.
        tolerance = 2 * math.ulp(max(abs(timestamps[j]), min_gap_seconds))
        limit = (len(vb) if cross else bisect_right(
            timestamps, timestamps[j] - min_gap_seconds + tolerance, hi=j))
        # One query column and one running departure maximum per earlier
        # reference retain linear working memory and quadratic total work.
        col = _distances(vb if cross else vb[:j], va[j:j + 1])[:, 0]
        eligible = np.flatnonzero(col[:limit] <= threshold)
        if not cross:
            eligible = eligible[departure_peaks[eligible] >= departure]
        if eligible.size:
            i = int(eligible[np.argmin(col[eligible])])
            peak = None if cross else float(departure_peaks[i])
            matches.append((j, i, float(col[i]), peak))
        if not cross:
            # Update after matching, so the current frame cannot count as its
            # own intervening departure; only i < k < j may qualify.
            np.maximum(departure_peaks[:j], col, out=departure_peaks[:j])
    results = []
    run = []
    for m in matches + [None]:
        if m is not None and run and m[0] == run[-1][0] + 1:
            run.append(m)
            continue
        if run:
            results.append(_summarize(run, va, vb, names, analysis, other, len(results) + 1))
        run = [m] if m is not None else []
    return results


def _summarize(run, va, vb, names, analysis, other, number) -> Recurrence:
    js = [m[0] for m in run]
    refs = [m[1] for m in run]
    dists = [m[2] for m in run]
    deltas = np.mean([va[j] - vb[i] for j, i, *_ in run], axis=0)
    peaks = [m[3] for m in run if m[3] is not None]
    reference = other if other is not None else analysis
    # Feature extraction quantizes window sizes to complete samples. Stored
    # timestamps and the same quantization keep report ranges on the audio clock.
    span = max(2, round(analysis.frame_seconds * analysis.sample_rate)) / analysis.sample_rate
    ref_span = max(2, round(reference.frame_seconds * reference.sample_rate)) / reference.sample_rate
    later = (analysis.frames[js[0]].start_seconds,
             min(analysis.duration_seconds, analysis.frames[js[-1]].start_seconds + span))
    earlier = (reference.frames[min(refs)].start_seconds,
               min(reference.duration_seconds, reference.frames[max(refs)].start_seconds + ref_span))
    peak = max(peaks) if peaks else None
    text = (f"Frames {len(run)} matched with mean distance {np.mean(dists):.3f}"
            + (f" after departure peak {peak:.2f}" if peak is not None else " (cross-recording)")
            + ". Review before relying on this match.")
    return Recurrence(f"R{number}", earlier[0], earlier[1], later[0], later[1],
                      float(np.mean(dists)), float(np.min(dists)), peak,
                      {n: float(d) for n, d in zip(names, deltas)}, text)
