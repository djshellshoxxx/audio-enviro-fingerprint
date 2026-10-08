"""Framewise, deterministic acoustic feature extraction."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np

from .methods.noise import frame_level_summary, rms_dbfs
from .methods.spectral import describe_spectrum


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
                  hop_seconds: float = 1.0) -> AnalysisResult:
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim != 1 or sample_rate <= 0:
        raise ValueError("Expected mono samples and a positive sample rate")
    if not math.isfinite(frame_seconds) or not math.isfinite(hop_seconds) or frame_seconds <= 0 or hop_seconds <= 0:
        raise ValueError("Frame and hop durations must be finite and positive")
    frame_size = max(2, round(frame_seconds * sample_rate))
    hop_size = max(1, round(hop_seconds * sample_rate))
    frames = []
    if samples.size >= frame_size:
        for start in range(0, samples.size - frame_size + 1, hop_size):
            segment = samples[start:start + frame_size]
            spectral = describe_spectrum(segment, sample_rate)
            frames.append(FrameFeature(start / sample_rate, rms_dbfs(segment),
                                       spectral["centroid_hz"], spectral["flatness"],
                                       spectral["band_power_db"]))
    levels = [frame.rms_dbfs for frame in frames]
    return AnalysisResult(sample_rate, len(samples) / sample_rate, frame_seconds,
                          hop_seconds, frames, frame_level_summary(levels))
