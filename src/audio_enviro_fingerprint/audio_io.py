"""Conservative PCM WAV reader. Source bytes are never rewritten."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import wave

import numpy as np


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int
    channels: int
    source_width_bytes: int

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate


def _decode_pcm(raw: bytes, width: int) -> np.ndarray:
    if width == 1:
        return (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    if width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if width == 3:
        octets = np.frombuffer(raw, dtype=np.uint8)
        if len(octets) % 3:
            raise ValueError("Truncated 24-bit PCM sample data")
        triples = octets.reshape(-1, 3).astype(np.int32)
        values = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
        values = (values ^ 0x800000) - 0x800000
        return values.astype(np.float64) / 8388608.0
    if width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    raise ValueError(f"Unsupported PCM sample width: {width * 8}-bit")


def load_wav(path: str | Path) -> AudioData:
    """Read integer PCM WAV and analyze channel 1 without destructive downmixing."""
    try:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE":
                raise ValueError("Only uncompressed PCM WAV is supported in this beta")
            channels = source.getnchannels()
            width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.getnframes()
            raw = source.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"Unable to read PCM WAV: {exc}") from exc
    if channels < 1 or rate < 1 or not raw:
        raise ValueError("WAV contains no analyzable audio frames")
    expected_bytes = frames * channels * width
    if len(raw) != expected_bytes:
        raise ValueError("WAV payload is truncated or inconsistent with its declared frame count")
    scalar = _decode_pcm(raw, width)
    if len(scalar) % channels:
        raise ValueError("WAV data ends in a partial channel frame")
    audio = scalar.reshape(-1, channels)
    # Averaging channels can cancel out-of-phase content. Channel 1 is selected
    # deterministically; the original multichannel file remains untouched.
    return AudioData(audio[:, 0], rate, channels, width)

