"""Per-channel analysis and inter-channel (stereo/spatial) descriptors."""
from __future__ import annotations

import numpy as np

from .features import analyze_audio
from .validation import audio_input, finite_number
from .fingerprint import make_fingerprint

METHOD = "multichannel-v1"


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(max(np.sqrt(np.mean(x * x)), 1e-12)))


def channel_pair_metrics(a: np.ndarray, b: np.ndarray, sample_rate: int, max_lag_ms: float = 1.5) -> dict:
    """Zero-lag correlation, level difference, inter-channel lag, and mid/side balance."""
    a, sample_rate = audio_input(a, sample_rate)
    b, _ = audio_input(b, sample_rate)
    max_lag_ms = finite_number(max_lag_ms, "Maximum lag")
    if not a.size or not b.size or max_lag_ms < 0:
        raise ValueError("Channel pairs require nonempty audio and a nonnegative lag limit")
    n = min(a.size, b.size)
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    denom = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    corr0 = float(np.sum(a * b) / denom) if denom > 0 else 0.0
    max_lag = min(n - 1, int(sample_rate * max_lag_ms / 1000.0))
    size = 1 << int(np.ceil(np.log2(2 * n)))
    xc = np.fft.irfft(np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size)), size)
    lags = np.arange(-max_lag, max_lag + 1)
    values = xc[lags % size]
    best = int(lags[np.argmax(np.abs(values))])
    peak = float(values[np.argmax(np.abs(values))] / denom) if denom > 0 else 0.0
    mid, side = (a + b) / 2, (a - b) / 2
    return {"correlation_zero_lag": corr0, "level_difference_db": _rms_db(a) - _rms_db(b),
            "peak_lag_samples": best, "peak_lag_ms": 1000.0 * best / sample_rate,
            "peak_correlation": peak, "side_to_mid_db": _rms_db(side) - _rms_db(mid)}


def analyze_channels(audio, frame_seconds: float = 2.0, hop_seconds: float = 1.0) -> dict:
    """Independent fingerprints per channel plus metrics for channel 1 vs each other channel."""
    if audio.all_channels is None or audio.channels < 1:
        raise ValueError("Audio does not retain per-channel data")
    channels = []
    for index in range(audio.channels):
        samples = audio.channel(index)
        analysis = analyze_audio(samples, audio.sample_rate, frame_seconds, hop_seconds)
        fp = make_fingerprint(analysis) if analysis.frames else None
        channels.append({"channel": index + 1, "rms_dbfs": _rms_db(samples),
                         "peak_dbfs": float(20 * np.log10(max(np.max(np.abs(samples)), 1e-12))),
                         "fingerprint_sha256": fp.fingerprint_hash if fp else None,
                         "features": fp.features if fp else None})
    pairs = [{"channels": [1, k + 1], **channel_pair_metrics(audio.channel(0), audio.channel(k), audio.sample_rate)}
             for k in range(1, audio.channels)]
    return {"method": METHOD, "channel_count": audio.channels, "channels": channels, "pairs": pairs}
