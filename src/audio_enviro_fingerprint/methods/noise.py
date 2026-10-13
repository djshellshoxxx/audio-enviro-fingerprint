"""Amplitude and background-noise descriptors (descriptive, not source separation)."""
from __future__ import annotations

import numpy as np


def dbfs(amplitude: float, floor: float = 1e-12) -> float:
    return float(20.0 * np.log10(max(float(amplitude), floor)))


def rms_dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -240.0
    return dbfs(float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))))


def frame_level_summary(frame_levels_dbfs: list[float]) -> dict[str, float]:
    if not frame_levels_dbfs:
        return {"frame_rms_dbfs_p10": -240.0, "frame_rms_dbfs_median": -240.0,
                "frame_rms_dbfs_p90": -240.0}
    values = np.asarray(frame_levels_dbfs, dtype=np.float64)
    return {
        "frame_rms_dbfs_p10": float(np.percentile(values, 10)),
        "frame_rms_dbfs_median": float(np.median(values)),
        "frame_rms_dbfs_p90": float(np.percentile(values, 90)),
    }
