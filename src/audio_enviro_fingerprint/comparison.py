"""Explainable distance over measurable fingerprint fields.

Every raw value, delta, normalized delta and fractional contribution to the
descriptive score is preserved so no evidence is hidden behind a single number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

MAX_NORMALIZED = 4.0
BAND_SCALE_DB = 15.0
SCALES = {"spectral_flatness": 0.25, "frame_rms_dbfs_p10": 20.0,
          "frame_rms_dbfs_median": 20.0, "median_rms_dbfs": 20.0}
GROUPS = {"spectral_centroid_hz": "spectral", "spectral_flatness": "spectral",
          "frame_rms_dbfs_p10": "level/noise", "frame_rms_dbfs_median": "level/noise",
          "median_rms_dbfs": "level/noise"}
UNITS = {"spectral_centroid_hz": "Hz", "spectral_flatness": "", "frame_rms_dbfs_p10": "dB",
         "frame_rms_dbfs_median": "dB", "median_rms_dbfs": "dB"}
LEVEL_CONFOUNDER_DB = 6.0


@dataclass(frozen=True)
class Comparison:
    score: float
    differences: dict[str, dict]
    explanation: str
    group_contributions: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def ranked(self) -> list[tuple[str, dict]]:
        """Features ordered by contribution to the distance, largest first."""
        return sorted(self.differences.items(), key=lambda item: item[1]["contribution_fraction"],
                      reverse=True)

    def to_dict(self) -> dict:
        return {"score": self.score, "differences": self.differences,
                "group_contributions": self.group_contributions, "warnings": self.warnings,
                "explanation": self.explanation, "score_is_probability": False}


def _features(value: dict) -> dict:
    return value["features"] if "features" in value else value


def _entry(first: float, second: float, scale: float, group: str, unit: str) -> dict:
    delta = second - first
    return {"first": first, "second": second, "delta": delta,
            "normalized_delta": min(abs(delta) / scale, MAX_NORMALIZED), "scale": scale,
            "group": group, "unit": unit,
            "direction": "higher in second" if delta > 0 else "lower in second" if delta < 0 else "equal"}


def compare_fingerprints(first: dict, second: dict) -> Comparison:
    v1, v2 = first.get("version", "aefp-1"), second.get("version", "aefp-1")
    if v1 != v2:
        raise ValueError(f"Fingerprint versions differ: {v1} vs {v2}")
    a, b = _features(first), _features(second)
    differences: dict[str, dict] = {}
    for key in sorted(set(a) & set(b)):
        if key == "band_power_db" and isinstance(a[key], dict) and isinstance(b[key], dict):
            for band in sorted(set(a[key]) & set(b[key])):
                differences[f"band_power_db.{band}"] = _entry(float(a[key][band]), float(b[key][band]),
                                                              BAND_SCALE_DB, "band power", "dB")
        elif key == "spectral_centroid_hz":
            x, y = float(a[key]), float(b[key])
            # Symmetric scale: swapping the two recordings must not change the score.
            differences[key] = _entry(x, y, max((abs(x) + abs(y)) / 2, 100.0), GROUPS[key], UNITS[key])
        elif key in SCALES:
            differences[key] = _entry(float(a[key]), float(b[key]), SCALES[key], GROUPS[key], UNITS[key])
    if not differences:
        raise ValueError("Fingerprints have no comparable numeric acoustic features")
    squares = {key: item["normalized_delta"] ** 2 for key, item in differences.items()}
    total = sum(squares.values())
    for key, item in differences.items():
        item["contribution_fraction"] = squares[key] / total if total else 0.0
    groups: dict[str, float] = {}
    for item in differences.values():
        groups[item["group"]] = groups.get(item["group"], 0.0) + item["contribution_fraction"]
    rms_distance = math.sqrt(total / len(differences))
    score = float(math.exp(-rms_distance))
    warnings = []
    if a.get("sample_rate_hz") != b.get("sample_rate_hz"):
        warnings.append(f"Sample rates differ ({a.get('sample_rate_hz')} vs {b.get('sample_rate_hz')} Hz); "
                        "spectral centroid and flatness span 0 to Nyquist and are not comparable, and fixed "
                        "bands above the lower Nyquist frequency are empty. Resample to a common rate first.")
    level = differences.get("median_rms_dbfs")
    if level and abs(level["delta"]) >= LEVEL_CONFOUNDER_DB:
        warnings.append(f"Median level differs by {level['delta']:+.1f} dB; microphone gain, distance or AGC "
                        "can produce this independent of the environment.")
    if min(float(a.get("duration_seconds", 1e9)), float(b.get("duration_seconds", 1e9))) < 5:
        warnings.append("One recording is shorter than 5 s; medians are poorly constrained.")
    strongest = sorted(differences.items(), key=lambda item: item[1]["contribution_fraction"], reverse=True)[:3]
    details = "; ".join(f"{key}: {item['delta']:+.3g} {item['unit']} ({item['contribution_fraction']:.0%} of distance)"
                        for key, item in strongest)
    explanation = (f"Descriptive similarity score {score:.3f} from {len(differences)} measured feature "
                   f"differences. Largest contributors: {details}. This is a screening aid, not a "
                   "probability of common location or an identification conclusion.")
    return Comparison(score, differences, explanation, groups, warnings)
