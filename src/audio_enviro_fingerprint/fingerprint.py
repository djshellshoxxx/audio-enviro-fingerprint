"""Versioned acoustic descriptors; independent of cryptographic evidence hashes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import numpy as np

from .features import AnalysisResult


@dataclass(frozen=True)
class Fingerprint:
    version: str
    features: dict
    fingerprint_hash: str
    canonical_json: str


def make_fingerprint(analysis: AnalysisResult) -> Fingerprint:
    return fingerprint_from_frames(analysis.frames, analysis.sample_rate, analysis.duration_seconds,
                                   analysis.noise["frame_rms_dbfs_p10"])


def fingerprint_from_frames(frames, sample_rate: int, duration_seconds: float,
                            rms_p10: float | None = None) -> Fingerprint:
    """Median-feature fingerprint (aefp-1) over any contiguous set of frames."""
    if not frames:
        raise ValueError("At least one complete analysis frame is required")
    if rms_p10 is None:
        rms_p10 = float(np.percentile([f.rms_dbfs for f in frames], 10))
    features = {
        "sample_rate_hz": int(sample_rate),
        "spectral_centroid_hz": float(np.median([f.spectral_centroid_hz for f in frames])),
        "spectral_flatness": float(np.median([f.spectral_flatness for f in frames])),
        "frame_rms_dbfs_p10": float(rms_p10),
        "median_rms_dbfs": float(np.median([f.rms_dbfs for f in frames])),
        "band_power_db": {key: float(np.median([f.band_power_db[key] for f in frames]))
                          for key in frames[0].band_power_db},
        "frame_count": len(frames),
        "duration_seconds": float(duration_seconds),
    }
    payload = {"version": "aefp-1", "features": features}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Fingerprint("aefp-1", features, digest, canonical)
