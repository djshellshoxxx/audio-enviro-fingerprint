"""Shared numerical input contracts for independently reusable methods."""
from __future__ import annotations

import math
from numbers import Integral
import numpy as np


def finite_mono(samples) -> np.ndarray:
    if np.iscomplexobj(samples):
        raise ValueError("Audio must contain real mono samples")
    try:
        values = np.asarray(samples, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("Audio must contain real mono samples") from exc
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("Audio must contain finite mono samples")
    return values


def positive_rate(sample_rate) -> int:
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, Integral) or sample_rate <= 0:
        raise ValueError("Sample rate must be a positive integer")
    return int(sample_rate)


def audio_input(samples, sample_rate) -> tuple[np.ndarray, int]:
    return finite_mono(samples), positive_rate(sample_rate)


def finite_number(value, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if isinstance(value, bool) or not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def validate_frames(analysis) -> None:
    """Reject malformed direct AnalysisResult inputs before producing findings."""
    for name in ("frame_seconds", "hop_seconds"):
        if finite_number(getattr(analysis, name), name) <= 0:
            raise ValueError("Analysis frame and hop durations must be positive")
    if finite_number(analysis.duration_seconds, "duration_seconds") < 0:
        raise ValueError("Analysis duration cannot be negative")
    previous = -1.0
    bands = None
    for frame in analysis.frames:
        start = finite_number(frame.start_seconds, "frame timestamp")
        if start < 0 or start < previous:
            raise ValueError("Frame timestamps must be nonnegative and ordered")
        previous = start
        for name in ("rms_dbfs", "spectral_centroid_hz", "spectral_flatness"):
            finite_number(getattr(frame, name), name)
        if not isinstance(frame.band_power_db, dict) or not all(isinstance(k, str) for k in frame.band_power_db):
            raise ValueError("Band powers must use named frequency bands")
        if bands is not None and set(frame.band_power_db) != bands:
            raise ValueError("Every frame must use the same frequency bands")
        bands = set(frame.band_power_db)
        for name, value in frame.band_power_db.items():
            finite_number(value, name)
