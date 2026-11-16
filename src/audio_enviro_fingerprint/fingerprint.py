"""Versioned acoustic descriptors; independent of cryptographic evidence hashes.

Feature values are rounded to ``DECIMAL_PLACES`` before canonical
serialization. Floating-point results differ between platforms and NumPy
builds (FFT, log implementations); without rounding, the same file produced
different fingerprint hashes on Windows and Linux. Absolute rounding is used
rather than significant digits, because values at the numerical noise floor
(e.g. the flatness of a pure tone, ~1e-16) differ entirely between builds.
A value lying within ~1e-10 of a rounding boundary can still round
differently; that is rare and is reported as a hash mismatch, never hidden.
aefp-2 = aefp-1 features + rounded serialization.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import numpy as np

from .features import AnalysisResult

VERSION = "aefp-2"
DECIMAL_PLACES = 6  # 1e-6 dB / Hz / flatness units: far below physical resolution


def quantize(value):
    """Round floats to DECIMAL_PLACES, recursively; -0.0 becomes 0.0 so it serializes identically."""
    if isinstance(value, dict):
        return {key: quantize(item) for key, item in value.items()}
    if isinstance(value, float):
        return round(value, DECIMAL_PLACES) or 0.0
    return value


@dataclass(frozen=True)
class Fingerprint:
    version: str
    features: dict
    fingerprint_hash: str
    canonical_json: str


def make_fingerprint(analysis: AnalysisResult) -> Fingerprint:
    if not analysis.frames:
        raise ValueError("At least one complete analysis frame is required")
    frames = analysis.frames
    features = {
        "sample_rate_hz": int(analysis.sample_rate),
        "spectral_centroid_hz": float(np.median([f.spectral_centroid_hz for f in frames])),
        "spectral_flatness": float(np.median([f.spectral_flatness for f in frames])),
        "frame_rms_dbfs_p10": float(analysis.noise["frame_rms_dbfs_p10"]),
        "median_rms_dbfs": float(np.median([f.rms_dbfs for f in frames])),
        "band_power_db": {key: float(np.median([f.band_power_db[key] for f in frames]))
                          for key in frames[0].band_power_db},
        "frame_count": len(frames),
        "duration_seconds": float(analysis.duration_seconds),
    }
    features = quantize(features)
    payload = {"version": VERSION, "features": features}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Fingerprint(VERSION, features, digest, canonical)
