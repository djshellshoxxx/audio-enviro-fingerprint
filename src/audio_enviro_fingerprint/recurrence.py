"""Environment recurrence detection within and across recordings.

A recording is split into segments at candidate transitions. Segment
fingerprints are compared pairwise; a pair is a *recurrence candidate* when the
descriptive similarity is high AND (within one recording) an intervening segment
was measurably different, i.e. the environment departed and returned.

All thresholds are heuristic and uncalibrated. Output is a list of candidates for
examiner review with raw measurements, thresholds, confounders and uncertainty;
it never asserts that two segments share a physical location.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math

import numpy as np

from .comparison import compare_fingerprints
from .fingerprint import fingerprint_from_frames

METHOD_VERSION = "recurrence-v1"
MIN_SEGMENT_FRAMES = 2
MATCH_SCORE_THRESHOLD = 0.80
DEPARTURE_MARGIN = 0.15

THRESHOLD_RATIONALE = (
    "MATCH_SCORE_THRESHOLD=0.80 (descriptive score, ~RMS normalized distance 0.22) and "
    "DEPARTURE_MARGIN=0.15 (an intervening segment must score at least this much lower against the "
    "earlier segment than the returning segment does) are engineering defaults chosen to be conservative "
    "on synthetic data. They are NOT calibrated on representative recordings; ROC calibration against "
    "repeated passes through known rooms and negative controls is required before any reliance.")

CONFOUNDERS = (
    "Background source (HVAC, traffic, crowd) recurring in different places",
    "Microphone gain, AGC, noise suppression or codec changes between segments",
    "Microphone distance, orientation or handling noise",
    "Transition boundary uncertainty of about one analysis window",
    "Similar rooms with similar size/materials (e.g., repeated hotel rooms or corridors)",
)


@dataclass(frozen=True)
class Segment:
    segment_id: str
    recording_id: str
    start_seconds: float
    end_seconds: float
    frame_count: int
    usable: bool
    fingerprint: dict | None
    within_segment_spread: dict[str, float]
    note: str = ""


@dataclass(frozen=True)
class RecurrenceCandidate:
    first_segment: str
    second_segment: str
    score: float
    cross_recording: bool
    intervening: list[dict]
    differences: dict
    features_closest: list[str]
    features_furthest: list[str]
    exceeds_spread: dict[str, bool]
    boundary_uncertainty_seconds: float
    gap_seconds: float
    warnings: list = field(default_factory=list)
    unusable_intervening: int = 0
    confounders: tuple = CONFOUNDERS
    thresholds: dict = field(default_factory=lambda: {
        "match_score": MATCH_SCORE_THRESHOLD, "departure_margin": DEPARTURE_MARGIN,
        "min_segment_frames": MIN_SEGMENT_FRAMES, "method": METHOD_VERSION})
    rationale: str = THRESHOLD_RATIONALE

    def to_dict(self) -> dict:
        data = asdict(self)
        data["confounders"] = list(self.confounders)
        return data


def segment_recording(analysis, transitions, recording_id: str) -> list[Segment]:
    """Split frames at transition times.

    A transition timestamp ``ts`` lies within one hop of the true change time T (T in [ts, ts + guard],
    guard = frame_seconds - hop_seconds). Conservatively, only frames ending at or before ``ts`` are pure
    "before" frames and only frames starting at or after ``ts + guard`` are pure "after" frames; frames
    in between mix both environments and are excluded from segment fingerprints.
    """
    if not recording_id:
        raise ValueError("recording_id is required and must be unique per recording")
    frames = analysis.frames
    if not frames:
        return []
    guard = max(0.0, analysis.frame_seconds - analysis.hop_seconds)
    times = sorted(t.timestamp_seconds for t in transitions if 0 < t.timestamp_seconds < analysis.duration_seconds)
    bounds = [0.0] + times + [analysis.duration_seconds]
    segments = []
    for index, (start, end) in enumerate(zip(bounds, bounds[1:])):
        lo = start + (guard if index > 0 else 0.0)
        hi = end
        inside = [f for f in frames
                  if f.start_seconds >= lo - 1e-9 and f.start_seconds + analysis.frame_seconds <= hi + 1e-9]
        sid = f"{recording_id}#S{index + 1}"
        usable = len(inside) >= MIN_SEGMENT_FRAMES
        if not inside:
            segments.append(Segment(sid, recording_id, start, end, 0, False, None, {}, "no unmixed frame"))
            continue
        fp = fingerprint_from_frames(inside, analysis.sample_rate, end - start)
        spread = {"spectral_centroid_hz": float(np.std([f.spectral_centroid_hz for f in inside])),
                  "spectral_flatness": float(np.std([f.spectral_flatness for f in inside])),
                  "median_rms_dbfs": float(np.std([f.rms_dbfs for f in inside]))}
        note = "" if usable else f"fewer than {MIN_SEGMENT_FRAMES} unmixed frames; not used for matching"
        segments.append(Segment(sid, recording_id, start, end, len(inside), usable, fp.features, spread, note))
    return segments


def _compare(a: Segment, b: Segment):
    return compare_fingerprints({"version": "aefp-1", "features": a.fingerprint},
                                {"version": "aefp-1", "features": b.fingerprint})


def find_recurrences(segments: list[Segment], frame_seconds: float = 2.0,
                     match_threshold: float = MATCH_SCORE_THRESHOLD,
                     departure_margin: float = DEPARTURE_MARGIN) -> list[RecurrenceCandidate]:
    """Report, for each segment, its best-scoring earlier match (consolidated, not all pairs).

    Segments must be listed in recording order and have unique IDs. Cross-recording pairs are scored on
    similarity only (no departure test is possible), so they are reported as "similar segment" candidates.
    """
    if not (math.isfinite(match_threshold) and 0 < match_threshold <= 1 and math.isfinite(departure_margin)
            and departure_margin >= 0):
        raise ValueError("Invalid recurrence thresholds")
    ids = [s.segment_id for s in segments]
    if len(set(ids)) != len(ids):
        raise ValueError("Segment IDs must be unique; give each recording a distinct recording_id")
    following = {}
    for rec in {s.recording_id for s in segments}:
        same = [s for s in segments if s.recording_id == rec]
        following.update({x.segment_id: y.segment_id for x, y in zip(same, same[1:])})
    usable = [s for s in segments if s.usable]
    found = []
    for j, b in enumerate(usable):
        best = None
        for a in usable[:j]:
            cross = a.recording_id != b.recording_id
            if not cross and following.get(a.segment_id) == b.segment_id:
                continue  # adjacent segments are a continuation, not a return
            comparison = _compare(a, b)
            if comparison.score < match_threshold:
                continue
            intervening, unusable_between = [], 0
            if not cross:
                for s in segments:
                    if s.recording_id == a.recording_id and a.end_seconds <= s.start_seconds and s.end_seconds <= b.start_seconds:
                        if s.usable:
                            intervening.append({"segment": s.segment_id, "score_vs_first": _compare(a, s).score})
                        else:
                            unusable_between += 1
                if not any(comparison.score - i["score_vs_first"] >= departure_margin for i in intervening):
                    continue  # no demonstrated departure: same environment persisted
            if best is None or (comparison.score, j) > (best[0].score, best[3]):
                best = (comparison, a, (intervening, unusable_between, cross), j)
        if best is None:
            continue
        comparison, a, (intervening, unusable_between, cross), _ = best
        ranked = comparison.ranked()
        exceeds = {}
        for key in ("spectral_centroid_hz", "spectral_flatness", "median_rms_dbfs"):
            spread = max(a.within_segment_spread.get(key, 0.0), b.within_segment_spread.get(key, 0.0))
            exceeds[key] = bool(key in comparison.differences and abs(comparison.differences[key]["delta"]) > 2 * spread)
        found.append(RecurrenceCandidate(
            a.segment_id, b.segment_id, comparison.score, cross, intervening, comparison.differences,
            [k for k, _ in ranked[-3:]], [k for k, _ in ranked[:3]], exceeds,
            frame_seconds, max(0.0, b.start_seconds - a.end_seconds) if not cross else 0.0,
            warnings=comparison.warnings, unusable_intervening=unusable_between))
    return sorted(found, key=lambda c: c.score, reverse=True)
