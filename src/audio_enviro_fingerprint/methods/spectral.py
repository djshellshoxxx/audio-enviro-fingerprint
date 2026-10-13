"""Windowed spectral descriptors with explicit fixed frequency bands."""
from __future__ import annotations

import numpy as np

BANDS = ((0, 125, "0-125 Hz"), (125, 250, "125-250 Hz"),
         (250, 500, "250-500 Hz"), (500, 1000, "500-1000 Hz"),
         (1000, 2000, "1000-2000 Hz"), (2000, 4000, "2000-4000 Hz"))


def describe_spectrum(samples: np.ndarray, sample_rate: int) -> dict:
    if samples.size < 2:
        return {"centroid_hz": 0.0, "flatness": 0.0,
                "band_power_db": {name: -240.0 for _, _, name in BANDS}}
    window = np.hanning(samples.size)
    spectrum = np.abs(np.fft.rfft(samples * window)) ** 2 / (sample_rate * np.sum(window ** 2))
    if samples.size % 2 == 0:
        spectrum[1:-1] *= 2.0
    else:
        spectrum[1:] *= 2.0
    frequencies = np.fft.rfftfreq(samples.size, 1 / sample_rate)
    total = float(spectrum.sum())
    magnitude = np.sqrt(spectrum)
    centroid = float(np.sum(frequencies * spectrum) / total) if total else 0.0
    positive = spectrum[spectrum > 1e-24]
    flatness = float(np.exp(np.mean(np.log(positive))) / np.mean(positive)) if positive.size else 0.0
    bands = {}
    nyquist = sample_rate / 2
    for low, high, name in BANDS:
        mask = (frequencies >= low) & (frequencies < min(high, nyquist + 1e-9))
        power = float(np.sum(spectrum[mask]) * (sample_rate / samples.size)) if np.any(mask) else 0.0
        bands[name] = float(10 * np.log10(max(power, 1e-24)))
    return {"centroid_hz": centroid, "flatness": flatness, "band_power_db": bands}
