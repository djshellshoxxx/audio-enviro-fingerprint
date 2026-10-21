"""Mains-hum (50/60 Hz) detection: a tonal-interference descriptor, not full ENF analysis."""
from __future__ import annotations

import numpy as np


def detect_mains_hum(samples: np.ndarray, sample_rate: int, harmonics: int = 6) -> dict:
    """Compare narrow-band power at 50 and 60 Hz harmonics with neighbouring spectrum."""
    x = np.asarray(samples, dtype=np.float64)
    size = 1 << 15
    if x.size < size or sample_rate < 400:
        return {"method": "mains-hum-v1", "detected": False, "reason": "recording too short or low rate"}
    segs = x[: (x.size // size) * size].reshape(-1, size) * np.hanning(size)
    power = (np.abs(np.fft.rfft(segs, axis=1)) ** 2).mean(axis=0)
    freqs = np.fft.rfftfreq(size, 1.0 / sample_rate)
    out = {}
    for base in (50.0, 60.0):
        ratios = []
        for k in range(1, harmonics + 1):
            f = base * k
            if f >= sample_rate / 2 - 5:
                break
            peak = power[(abs(freqs - f) <= 0.5)].max()
            ring = (abs(freqs - f) > 2.0) & (abs(freqs - f) <= 8.0)
            ratios.append(float(10 * np.log10(peak / max(np.median(power[ring]), 1e-30))))
        out[base] = ratios
    best = max(out, key=lambda b: np.mean(out[b][:3]) if out[b] else -1e9)
    ratios = out[best]
    detected = bool(ratios and np.mean(ratios[:3]) > 10.0)
    return {"method": "mains-hum-v1", "detected": detected,
            "fundamental_hz": best if detected else None,
            "harmonic_prominence_db": {f"{best * (i + 1):g} Hz": r for i, r in enumerate(ratios)},
            "note": "Prominence over adjacent spectrum; not an ENF time series."}
