"""Explainable distance over measurable fingerprint fields."""
from __future__ import annotations

from dataclasses import dataclass, field
import math

LEVEL_SCALE_DB = 20.0
BAND_SCALE_DB = 15.0
MAX_NORMALIZED_DELTA = 4.0
LEVEL_KEYS = ("frame_rms_dbfs_p10", "frame_rms_dbfs_median", "frame_rms_dbfs_p90", "median_rms_dbfs")
SPECTRAL_SHAPE_KEYS = ("spectral_centroid_hz", "spectral_flatness")


@dataclass(frozen=True)
class Comparison:
    score: float
    differences: dict[str, dict[str, float]]
    explanation: str
    # Share of the summed squared normalized distance contributed by each feature
    # (sums to 1; all zero when every compared feature is identical).
    contributions: dict[str, float] = field(default_factory=dict)
    # Per feature group: mean normalized delta, feature count and summed contribution.
    groups: dict[str, dict] = field(default_factory=dict)
    # Root-mean-square of capped normalized deltas; score == exp(-distance).
    distance: float = 0.0


def _features(value: dict) -> dict:
    if "features" in value:
        return value["features"]
    return value


def feature_group(key: str) -> str:
    """Name of the explanatory group a compared feature belongs to."""
    if key.startswith("band_power_db."):
        return "band_power"
    if key in SPECTRAL_SHAPE_KEYS:
        return "spectral_shape"
    if key in LEVEL_KEYS:
        return "level"
    return "other"


def compare_fingerprints(first: dict, second: dict) -> Comparison:
    v1, v2 = first.get("version", "aefp-1"), second.get("version", "aefp-1")
    if v1 != v2:
        raise ValueError(f"Fingerprint versions differ: {v1} vs {v2}")
    a, b = _features(first), _features(second)
    scales = {"spectral_centroid_hz": max(abs(float(a.get("spectral_centroid_hz", 1))), 100.0),
              "spectral_flatness": 0.25}
    scales.update({key: LEVEL_SCALE_DB for key in LEVEL_KEYS})
    differences = {}
    for key in sorted(set(a) & set(b)):
        if key in ("band_power_db",) and isinstance(a[key], dict) and isinstance(b[key], dict):
            for band in sorted(set(a[key]) & set(b[key])):
                delta = float(b[key][band]) - float(a[key][band])
                normalized_delta = min(abs(delta) / BAND_SCALE_DB, MAX_NORMALIZED_DELTA)
                differences[f"band_power_db.{band}"] = {"first": float(a[key][band]), "second": float(b[key][band]),
                                                        "delta": delta, "normalized_delta": normalized_delta}
        elif key in scales:
            x, y = float(a[key]), float(b[key])
            delta = y - x
            normalized_delta = min(abs(delta) / scales[key], MAX_NORMALIZED_DELTA)
            differences[key] = {"first": x, "second": y, "delta": delta, "normalized_delta": normalized_delta}
    if not differences:
        raise ValueError("Fingerprints have no comparable numeric acoustic features")
    for key, item in differences.items():
        if not (math.isfinite(item["first"]) and math.isfinite(item["second"])):
            raise ValueError(f"Fingerprint feature {key} is not finite")
    normalized = [item["normalized_delta"] for item in differences.values()]
    squared_total = sum(x * x for x in normalized)
    rms_distance = math.sqrt(squared_total / len(normalized))
    score = float(math.exp(-rms_distance))
    contributions = {key: (item["normalized_delta"] ** 2 / squared_total if squared_total else 0.0)
                     for key, item in differences.items()}
    grouped: dict[str, list[str]] = {}
    for key in differences:
        grouped.setdefault(feature_group(key), []).append(key)
    groups = {name: {"mean_normalized_delta": float(sum(differences[k]["normalized_delta"] for k in keys) / len(keys)),
                     "feature_count": len(keys),
                     "contribution": float(sum(contributions[k] for k in keys))}
              for name, keys in sorted(grouped.items())}
    strongest = sorted(differences.items(), key=lambda item: item[1]["normalized_delta"], reverse=True)[:3]
    details = "; ".join(f"{key}: {item['delta']:+.3g} (normalized {item['normalized_delta']:.2f})" for key, item in strongest)
    group_text = ", ".join(f"{name} {info['mean_normalized_delta']:.2f}" for name, info in groups.items())
    explanation = (f"Descriptive similarity score {score:.3f} from {len(normalized)} measured feature "
                   f"differences. Largest raw differences: {details}. Mean normalized difference by group: "
                   f"{group_text}. This is a screening aid, not a "
                   "probability of common location or an identification conclusion.")
    return Comparison(score, differences, explanation, contributions, groups, float(rms_distance))
