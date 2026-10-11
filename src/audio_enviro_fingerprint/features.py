"""Framewise, deterministic acoustic feature extraction."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Callable

import numpy as np

from .methods.noise import frame_level_summary, rms_dbfs
from .methods.spectral import describe_spectrum


class AnalysisCancelled(Exception):
    """Raised when a caller-supplied cancel flag is set during analysis."""


@dataclass(frozen=True)
class FrameFeature:
    start_seconds: float
    rms_dbfs: float
    spectral_centroid_hz: float
    spectral_flatness: float
    band_power_db: dict[str, float]


@dataclass(frozen=True)
class AnalysisResult:
    sample_rate: int
    duration_seconds: float
    frame_seconds: float
    hop_seconds: float
    frames: list[FrameFeature]
    noise: dict[str, float]

    def to_dict(self) -> dict:
        return {"sample_rate": self.sample_rate, "duration_seconds": self.duration_seconds,
                "frame_seconds": self.frame_seconds, "hop_seconds": self.hop_seconds,
                "frames": [asdict(frame) for frame in self.frames], "noise": self.noise}


def analyze_audio(samples: np.ndarray, sample_rate: int, frame_seconds: float = 2.0,
                  hop_seconds: float = 1.0, progress: Callable[[float], object] | None = None,
                  cancel=None) -> AnalysisResult:
    """Extract framewise features.

    ``progress`` (optional) receives non-decreasing fractions in [0, 1], ending with 1.0.
    ``cancel`` (optional) is any object with ``is_set()`` (e.g. ``threading.Event``);
    when set, :class:`AnalysisCancelled` is raised before the next frame.
    """
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim != 1 or sample_rate <= 0:
        raise ValueError("Expected mono samples and a positive sample rate")
    if not math.isfinite(frame_seconds) or not math.isfinite(hop_seconds) or frame_seconds <= 0 or hop_seconds <= 0:
        raise ValueError("Frame and hop durations must be finite and positive")
    frame_size = max(2, round(frame_seconds * sample_rate))
    hop_size = max(1, round(hop_seconds * sample_rate))
    starts = range(0, samples.size - frame_size + 1, hop_size) if samples.size >= frame_size else range(0)
    total = len(starts)
    report_every = max(1, total // 200)
    if progress is not None:
        progress(0.0)
    frames = []
    for index, start in enumerate(starts):
        if cancel is not None and cancel.is_set():
            raise AnalysisCancelled("Analysis cancelled")
        segment = samples[start:start + frame_size]
        spectral = describe_spectrum(segment, sample_rate)
        frames.append(FrameFeature(start / sample_rate, rms_dbfs(segment),
                                   spectral["centroid_hz"], spectral["flatness"],
                                   spectral["band_power_db"]))
        if progress is not None and (index + 1) % report_every == 0 and index + 1 < total:
            progress((index + 1) / total)
    if cancel is not None and cancel.is_set():
        raise AnalysisCancelled("Analysis cancelled")
    levels = [frame.rms_dbfs for frame in frames]
    result = AnalysisResult(sample_rate, len(samples) / sample_rate, frame_seconds,
                            hop_seconds, frames, frame_level_summary(levels))
    if progress is not None:
        progress(1.0)
    return result
