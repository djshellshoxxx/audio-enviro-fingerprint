"""Known-location reference acquisition records and quality review.

A reference is documentation about an exemplar recording. A self-reported
location label never establishes a match; reviews only check completeness and
technical suitability.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, fields

import numpy as np

SCHEMA = "aefp-reference-1"
REQUIRED = ("location_id", "recorded_utc", "operator", "recorder_make_model", "microphone_make_model",
            "input_chain", "channel_assignment", "placement", "orientation", "height_m",
            "source_signal", "occupancy_activity", "authority_or_consent")


@dataclass
class ReferenceMetadata:
    location_id: str = ""
    recorded_utc: str = ""
    operator: str = ""
    recorder_make_model: str = ""
    recorder_serial: str = ""
    microphone_make_model: str = ""
    microphone_serial: str = ""
    input_chain: str = ""
    channel_assignment: str = ""
    placement: str = ""
    orientation: str = ""
    height_m: str = ""
    source_signal: str = ""
    occupancy_activity: str = ""
    weather: str = ""
    calibration: str = ""
    authority_or_consent: str = ""
    repeat_number: int = 1
    repeats_planned: int = 3
    deviations: str = ""

    def to_dict(self) -> dict:
        return {"schema": SCHEMA, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "ReferenceMetadata":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


def review_reference(meta: ReferenceMetadata, samples: np.ndarray, sample_rate: int) -> dict:
    """Return pass/warn/fail checks. Overall status is the worst individual status."""
    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    missing = [k for k in REQUIRED if not str(getattr(meta, k)).strip()]
    add("required_metadata", "fail" if missing else "pass",
        f"Missing: {', '.join(missing)}" if missing else "All required fields documented")
    duration = len(samples) / sample_rate if sample_rate else 0.0
    add("duration", "pass" if duration >= 60 else "warn" if duration >= 20 else "fail",
        f"{duration:.1f} s (60 s or more recommended)")
    add("sample_rate", "pass" if sample_rate >= 32000 else "warn" if sample_rate >= 16000 else "fail",
        f"{sample_rate} Hz")
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    clipped = float(np.mean(np.abs(samples) >= 0.999)) if len(samples) else 0.0
    add("clipping", "fail" if clipped > 0.001 else "pass", f"{100 * clipped:.3f}% of samples at full scale")
    rms = float(np.sqrt(np.mean(np.square(samples)))) if len(samples) else 0.0
    level = 20 * np.log10(max(rms, 1e-12))
    add("level", "pass" if level > -60 else "warn" if level > -80 else "fail",
        f"RMS {level:.1f} dBFS, peak {20 * np.log10(max(peak, 1e-12)):.1f} dBFS")
    add("repeats", "pass" if meta.repeat_number >= meta.repeats_planned >= 2 else "warn",
        f"Repeat {meta.repeat_number} of {meta.repeats_planned} planned")
    add("calibration", "pass" if meta.calibration.strip() else "warn",
        "Calibration documented" if meta.calibration.strip() else "No calibration documented")
    from .methods.quality import review_quality
    # Preserve the acquisition protocol's duration/rate checks, adding the older
    # development branch's independent DC/dropout checks without duplicate names.
    quality = review_quality(samples, sample_rate)
    checks.extend(c for c in quality["checks"] if c["check"] in ("dc_offset", "silence_fraction"))
    order = {"pass": 0, "warn": 1, "fail": 2}
    overall = max((c["status"] for c in checks), key=order.get)
    return {"schema": SCHEMA, "overall": overall, "checks": checks,
            "caution": "A self-reported location label is not evidence of a match."}
