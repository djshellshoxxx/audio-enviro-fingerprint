"""Explainable distance over measurable fingerprint fields."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Comparison:
    score: float
    differences: dict[str, dict[str, float]]
    explanation: str


def _features(value: dict) -> dict:
    if "features" in value:
        return value["features"]
    return value


def compare_fingerprints(first: dict, second: dict) -> Comparison:
    v1, v2 = first.get("version", "aefp-1"), second.get("version", "aefp-1")
    if v1 != v2:
        raise ValueError(f"Fingerprint versions differ: {v1} vs {v2}")
    a, b = _features(first), _features(second)
    scales = {"spectral_centroid_hz": max(abs(float(a.get("spectral_centroid_hz", 1))), 100.0),
              "spectral_flatness": 0.25, "frame_rms_dbfs_p10": 20.0,
              "frame_rms_dbfs_median": 20.0, "median_rms_dbfs": 20.0}
    differences = {}
    normalized = []
    for key in sorted(set(a) & set(b)):
        if key in ("band_power_db",) and isinstance(a[key], dict) and isinstance(b[key], dict):
            for band in sorted(set(a[key]) & set(b[key])):
                delta = float(b[key][band]) - float(a[key][band])
                normalized_delta = min(abs(delta) / 15.0, 4.0)
                differences[f"band_power_db.{band}"] = {"first": float(a[key][band]), "second": float(b[key][band]), "delta": delta, "normalized_delta": normalized_delta}
                normalized.append(normalized_delta)
        elif key in scales:
            x, y = float(a[key]), float(b[key])
            delta = y - x
            normalized_delta = min(abs(delta) / scales[key], 4.0)
            differences[key] = {"first": x, "second": y, "delta": delta, "normalized_delta": normalized_delta}
            normalized.append(normalized_delta)
    if not normalized:
        raise ValueError("Fingerprints have no comparable numeric acoustic features")
    rms_distance = math.sqrt(sum(x * x for x in normalized) / len(normalized))
    score = float(math.exp(-rms_distance))
    strongest = sorted(differences.items(), key=lambda item: item[1]["normalized_delta"], reverse=True)[:3]
    details = "; ".join(f"{key}: {item['delta']:+.3g} (normalized {item['normalized_delta']:.2f})" for key, item in strongest)
    explanation = (f"Descriptive similarity score {score:.3f} from {len(normalized)} measured feature "
                   f"differences. Largest raw differences: {details}. This is a screening aid, not a "
                   "probability of common location or an identification conclusion.")
    return Comparison(score, differences, explanation)
