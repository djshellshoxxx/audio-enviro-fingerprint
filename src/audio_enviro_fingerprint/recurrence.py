"""Candidate recurring environment segments within or across recordings.

Segments are the spans between detected transitions. Each segment is summarized
by median frame features, and segment pairs are compared with the same
transparent per-feature normalization used for whole-recording comparisons.
Results are screening candidates only; they do not establish a common location.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import statistics

from .transitions import detect_transitions

SCALAR_SCALES = {"rms_dbfs": 15.0, "spectral_flatness": 0.25}
BAND_SCALE_DB = 15.0
CONFOUNDERS = ("level changes from microphone motion or gain/AGC", "transient foreground sources",
               "codec or noise-suppression processing", "different rooms with similar spectra")


@dataclass(frozen=True)
class Segment:
    segment_id: str
    recording_id: str
    start_seconds: float
    end_seconds: float
    frame_count: int
    features: dict[str, float]


@dataclass(frozen=True)
class Recurrence:
    first: Segment
    second: Segment
    distance: float
    differences: dict[str, dict[str, float]]
    explanation: str


def segment_analysis(analysis, recording_id: str = "recording", transition_threshold: float = 0.35,
                     minimum_separation_seconds: float = 3.0, minimum_frames: int = 2) -> list[Segment]:
    """Split an analysis at detected transitions and summarize each span by median features."""
    if minimum_frames < 1:
        raise ValueError("minimum_frames must be at least 1")
    frames = list(getattr(analysis, "frames", []))
    boundaries = [event.timestamp_seconds for event in
                  detect_transitions(analysis, transition_threshold, minimum_separation_seconds)]
    groups: list[list] = [[]]
    for frame in frames:
        if boundaries and frame.start_seconds >= boundaries[0]:
            boundaries.pop(0)
            groups.append([])
        groups[-1].append(frame)
    segments = []
    for group in groups:
        if len(group) < minimum_frames:
            continue
        features = {key: float(statistics.median(getattr(f, key) for f in group))
                    for key in ("rms_dbfs", "spectral_centroid_hz", "spectral_flatness")}
        for band in sorted(set.intersection(*(set(f.band_power_db) for f in group))):
            features[f"band_power_db.{band}"] = float(statistics.median(f.band_power_db[band] for f in group))
        end = group[-1].start_seconds + analysis.frame_seconds
        segments.append(Segment(f"{recording_id}#{len(segments) + 1}", recording_id,
                                group[0].start_seconds, end, len(group), features))
    return segments


def compare_segments(first: Segment, second: Segment) -> tuple[float, dict[str, dict[str, float]]]:
    """Root-mean-square of capped normalized feature deltas, with every raw delta preserved."""
    centroid_scale = max(abs(first.features.get("spectral_centroid_hz", 0.0)), 100.0)
    differences = {}
    for key in sorted(set(first.features) & set(second.features)):
        if key.startswith("band_power_db."):
            scale = BAND_SCALE_DB
        elif key == "spectral_centroid_hz":
            scale = centroid_scale
        else:
            scale = SCALAR_SCALES[key]
        x, y = first.features[key], second.features[key]
        delta = y - x
        differences[key] = {"first": x, "second": y, "delta": delta,
                            "normalized_delta": min(abs(delta) / scale, 4.0)}
    if not differences:
        raise ValueError("Segments have no comparable features")
    distance = math.sqrt(sum(d["normalized_delta"] ** 2 for d in differences.values()) / len(differences))
    return float(distance), differences


def find_recurrences(segments: list[Segment], max_distance: float = 0.25) -> list[Recurrence]:
    """Pair segments separated by at least one different segment (or from different recordings)."""
    if not math.isfinite(max_distance) or max_distance < 0:
        raise ValueError("max_distance must be finite and nonnegative")
    order = {segment.segment_id: index for index, segment in enumerate(segments)}
    results = []
    for i, first in enumerate(segments):
        for second in segments[i + 1:]:
            same_recording = first.recording_id == second.recording_id
            # Adjacent segments in one recording were split because they differ; a
            # recurrence requires the environment to leave and return.
            if same_recording and order[second.segment_id] - order[first.segment_id] < 2:
                continue
            distance, differences = compare_segments(first, second)
            if distance > max_distance:
                continue
            strongest = sorted(differences.items(), key=lambda item: item[1]["normalized_delta"], reverse=True)[:3]
            details = "; ".join(f"{key}: {item['delta']:+.3g} (normalized {item['normalized_delta']:.2f})"
                                for key, item in strongest)
            explanation = (f"Candidate recurrence {first.segment_id} ({first.start_seconds:.1f}-{first.end_seconds:.1f} s) "
                           f"and {second.segment_id} ({second.start_seconds:.1f}-{second.end_seconds:.1f} s): "
                           f"normalized feature distance {distance:.3f} <= threshold {max_distance:.3f} over "
                           f"{len(differences)} features. Largest differences: {details}. The threshold is an "
                           "unvalidated beta default; possible confounders: " + ", ".join(CONFOUNDERS) +
                           ". This is a screening aid, not an identification conclusion.")
            results.append(Recurrence(first, second, distance, differences, explanation))
    return sorted(results, key=lambda item: item.distance)
