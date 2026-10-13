"""Candidate change points from adjacent frame feature differences."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Transition:
    timestamp_seconds: float
    strength: float
    evidence: dict[str, float]


def detect_transitions(analysis, threshold: float = 0.35,
                       minimum_separation_seconds: float = 3.0) -> list[Transition]:
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold must be finite and nonnegative")
    if not math.isfinite(minimum_separation_seconds) or minimum_separation_seconds < 0:
        raise ValueError("Minimum separation must be finite and nonnegative")
    frames = getattr(analysis, "frames", [])
    candidates = []
    for before, after in zip(frames, frames[1:]):
        evidence = {}
        scales = {"rms_dbfs": 15.0, "spectral_centroid_hz": max(before.spectral_centroid_hz, 100.0),
                  "spectral_flatness": 0.25}
        for key, scale in scales.items():
            delta = float(getattr(after, key) - getattr(before, key))
            evidence[key] = delta
        band_names = set(before.band_power_db) & set(after.band_power_db)
        band_deltas = {}
        for name in sorted(band_names):
            delta = float(after.band_power_db[name] - before.band_power_db[name])
            band_deltas[name] = delta
            evidence[f"band_power_db.{name}"] = delta
        # Median normalized changes keep one narrow-band feature from dominating.
        parts = [abs(evidence["rms_dbfs"]) / scales["rms_dbfs"],
                 abs(evidence["spectral_centroid_hz"]) / scales["spectral_centroid_hz"],
                 abs(evidence["spectral_flatness"]) / scales["spectral_flatness"]]
        parts.extend(abs(delta) / 15.0 for delta in band_deltas.values())
        strength = sum(parts) / len(parts)
        if strength >= threshold:
            candidates.append(Transition(after.start_seconds, float(strength), evidence))
    selected = []
    for event in sorted(candidates, key=lambda item: item.strength, reverse=True):
        if all(abs(event.timestamp_seconds - old.timestamp_seconds) >= minimum_separation_seconds for old in selected):
            selected.append(event)
    return sorted(selected, key=lambda item: item.timestamp_seconds)
