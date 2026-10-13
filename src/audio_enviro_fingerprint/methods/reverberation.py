"""RT60 estimate from the -5 to -25 dB decay slope using Schroeder integration.

This method is intended for a measured room impulse response, not arbitrary
programme audio. It is experimental and must not be reported as ISO 3382
compliant unless acquisition and measurement conditions satisfy that standard.
"""
from __future__ import annotations

import numpy as np


def estimate_t20(impulse_response: np.ndarray, sample_rate: int) -> dict:
    signal = np.asarray(impulse_response, dtype=np.float64)
    if sample_rate <= 0 or signal.ndim != 1 or signal.size < sample_rate // 4:
        raise ValueError("Provide at least 0.25 s of mono impulse-response audio")
    energy = signal * signal
    if not np.any(energy):
        raise ValueError("Impulse response is silent")
    integrated = np.cumsum(energy[::-1])[::-1]
    curve = 10 * np.log10(np.maximum(integrated / integrated[0], 1e-12))
    start_candidates = np.flatnonzero(curve <= -5)
    end_candidates = np.flatnonzero(curve <= -25)
    if not start_candidates.size or not end_candidates.size:
        raise ValueError("Impulse response does not contain a measurable -5 to -25 dB decay")
    start = int(start_candidates[0])
    end = int(end_candidates[0])
    if end <= start or curve[start] - curve[end] < 15:
        raise ValueError("Insufficient decay range for T20 estimation")
    times = np.arange(start, end + 1) / sample_rate
    slope, intercept = np.polyfit(times, curve[start:end + 1], 1)
    if slope >= 0:
        raise ValueError("Decay slope is not negative")
    rt60 = float(-60 / slope)
    fit = slope * times + intercept
    residual_rmse = float(np.sqrt(np.mean((curve[start:end + 1] - fit) ** 2)))
    return {"rt60_seconds": rt60, "decay_slope_db_per_second": float(slope),
            "fit_rmse_db": residual_rmse, "range_db": float(curve[start] - curve[end]),
            "method": "schroeder-t20-experimental-v1"}
