"""Musical descriptors: pitch names, dominant tones, chroma/key, pitch track, tempo.

All outputs are descriptive measurements with visible supporting values. Key and
tempo are heuristic estimates; ``confidence`` values are not probabilities.
"""
from __future__ import annotations

import numpy as np

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
# Krumhansl-Kessler (1982) probe-tone profiles.
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def hz_to_note(frequency_hz: float, a4_hz: float = 440.0) -> dict:
    """Nearest equal-tempered note, octave, and signed cents deviation."""
    if not np.isfinite(frequency_hz) or frequency_hz <= 0:
        raise ValueError("Frequency must be positive and finite")
    midi = 69.0 + 12.0 * np.log2(frequency_hz / a4_hz)
    nearest = int(round(midi))
    return {"note": f"{NOTE_NAMES[nearest % 12]}{nearest // 12 - 1}", "midi": nearest,
            "cents": float((midi - nearest) * 100.0), "frequency_hz": float(frequency_hz)}


def note_to_hz(midi: float, a4_hz: float = 440.0) -> float:
    return float(a4_hz * 2.0 ** ((midi - 69.0) / 12.0))


def _frames(samples: np.ndarray, size: int, hop: int) -> np.ndarray:
    if samples.size < size:
        samples = np.pad(samples, (0, size - samples.size))
    count = 1 + (samples.size - size) // hop
    index = np.arange(size)[None, :] + hop * np.arange(count)[:, None]
    return samples[index]


def _stft_power(samples: np.ndarray, size: int, hop: int) -> np.ndarray:
    return np.abs(np.fft.rfft(_frames(samples, size, hop) * np.hanning(size), axis=1)) ** 2


def dominant_tones(samples: np.ndarray, sample_rate: int, count: int = 5,
                   min_hz: float = 20.0, max_hz: float = 4000.0, a4_hz: float = 440.0) -> list[dict]:
    """Strongest stationary spectral peaks (Welch average) labelled as musical notes."""
    size = 1 << int(np.clip(np.ceil(np.log2(sample_rate)), 10, 16))   # ~1 Hz resolution
    power = _stft_power(np.asarray(samples, dtype=np.float64), size, size // 2).mean(axis=0)
    freqs = np.fft.rfftfreq(size, 1.0 / sample_rate)
    band = (freqs >= min_hz) & (freqs <= min(max_hz, sample_rate / 2 - 1))
    if not band.any() or power[band].max() <= 0:
        return []
    idx = np.flatnonzero(band)[1:-1]
    local = idx[(power[idx] > power[idx - 1]) & (power[idx] >= power[idx + 1])]
    floor = np.median(power[band])
    peaks = []
    for i in local[np.argsort(power[local])[::-1]]:
        # parabolic interpolation on log power refines the frequency estimate
        a, b, c = np.log(np.maximum(power[i - 1:i + 2], 1e-30))
        shift = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
        f = float((i + shift) * sample_rate / size)
        if any(abs(f - p["frequency_hz"]) < 3.0 for p in peaks):
            continue
        info = hz_to_note(f, a4_hz)
        info["level_db_above_median"] = float(10 * np.log10(power[i] / max(floor, 1e-30)))
        peaks.append(info)
        if len(peaks) >= count:
            break
    return peaks


def chromagram(samples: np.ndarray, sample_rate: int, a4_hz: float = 440.0,
               fmin: float = 65.0, fmax: float = 2000.0) -> np.ndarray:
    """Return a (frames, 12) chroma matrix, C = column 0."""
    size = 1 << int(np.clip(np.ceil(np.log2(sample_rate * 0.186)), 10, 15))
    power = _stft_power(np.asarray(samples, dtype=np.float64), size, size // 2)
    freqs = np.fft.rfftfreq(size, 1.0 / sample_rate)
    ok = (freqs >= fmin) & (freqs <= min(fmax, sample_rate / 2))
    midi = 69.0 + 12.0 * np.log2(freqs[ok] / a4_hz)
    pitch_class = np.round(midi).astype(int) % 12
    chroma = np.zeros((power.shape[0], 12))
    for pc in range(12):
        chroma[:, pc] = power[:, ok][:, pitch_class == pc].sum(axis=1)
    return chroma


def estimate_key(chroma: np.ndarray) -> dict:
    """Krumhansl-Schmuckler key estimate with ranked alternatives (correlations)."""
    profile = np.asarray(chroma, dtype=np.float64).sum(axis=0)
    if profile.sum() <= 0 or np.ptp(profile) == 0:
        return {"key": None, "mode": None, "correlation": 0.0, "alternatives": [],
                "chroma": [0.0] * 12}
    profile = profile / profile.sum()
    scores = []
    for mode, template in (("major", _MAJOR), ("minor", _MINOR)):
        for tonic in range(12):
            r = float(np.corrcoef(profile, np.roll(template, tonic))[0, 1])
            scores.append((r, NOTE_NAMES[tonic], mode))
    scores.sort(reverse=True)
    best = scores[0]
    return {"key": best[1], "mode": best[2], "correlation": best[0],
            "alternatives": [{"key": k, "mode": m, "correlation": r} for r, k, m in scores[1:4]],
            "chroma": [float(x) for x in profile]}


def estimate_tuning_cents(samples: np.ndarray, sample_rate: int, a4_hz: float = 440.0) -> float | None:
    """Median cents offset of the strongest tonal peaks from the equal-tempered grid."""
    tones = [t for t in dominant_tones(samples, sample_rate, 8, 80.0, 2000.0, a4_hz)
             if t["level_db_above_median"] > 12.0]
    return float(np.median([t["cents"] for t in tones])) if tones else None


def pitch_track(samples: np.ndarray, sample_rate: int, fmin: float = 60.0, fmax: float = 1000.0,
                frame_seconds: float = 0.064, hop_seconds: float = 0.032,
                threshold: float = 0.15) -> list[dict]:
    """Per-frame f0 via the YIN difference function (de Cheveigne & Kawahara, 2002)."""
    x = np.asarray(samples, dtype=np.float64)
    size = int(frame_seconds * sample_rate)
    hop = max(1, int(hop_seconds * sample_rate))
    tau_min, tau_max = max(2, int(sample_rate / fmax)), min(size // 2, int(sample_rate / fmin))
    if tau_max <= tau_min + 1 or x.size < size:
        return []
    out = []
    for n, frame in enumerate(_frames(x, size, hop)):
        frame = frame - frame.mean()
        if np.sqrt(np.mean(frame ** 2)) < 1e-4:
            out.append({"time_s": n * hop / sample_rate, "f0_hz": None, "confidence": 0.0})
            continue
        # difference function through FFT autocorrelation
        w = size - tau_max
        seg = frame[:w]
        spec = np.fft.rfft(frame, 2 * size)
        acf = np.fft.irfft(np.conj(np.fft.rfft(seg, 2 * size)) * spec)[:tau_max + 1]
        cum = np.concatenate(([0.0], np.cumsum(frame ** 2)))
        energy = cum[w:w + tau_max + 1][: tau_max + 1] - cum[: tau_max + 1]
        d = np.sum(seg ** 2) + energy - 2 * acf
        d[0] = 0
        cmnd = np.ones_like(d)
        running = np.cumsum(d[1:])
        cmnd[1:] = d[1:] * np.arange(1, d.size) / np.maximum(running, 1e-30)
        below = np.flatnonzero(cmnd[tau_min:] < threshold)
        if below.size:
            tau = tau_min + below[0]
            while tau + 1 <= tau_max and cmnd[tau + 1] < cmnd[tau]:
                tau += 1
            a, b, c = cmnd[tau - 1], cmnd[tau], cmnd[min(tau + 1, tau_max)]
            denom = a - 2 * b + c
            tau_f = tau + (0.5 * (a - c) / denom if denom else 0.0)
            out.append({"time_s": n * hop / sample_rate, "f0_hz": float(sample_rate / tau_f),
                        "confidence": float(1.0 - b)})
        else:
            out.append({"time_s": n * hop / sample_rate, "f0_hz": None, "confidence": 0.0})
    return out


def estimate_tempo(samples: np.ndarray, sample_rate: int, bpm_min: float = 40.0,
                   bpm_max: float = 220.0) -> dict:
    """Tempo from the autocorrelation of a spectral-flux onset envelope."""
    x = np.asarray(samples, dtype=np.float64)
    size, hop = 1024, 256
    if x.size < size * 8:
        return {"bpm": None, "confidence": 0.0, "onset_count": 0}
    mag = np.sqrt(_stft_power(x, size, hop))
    flux = np.maximum(np.diff(np.log1p(100 * mag), axis=0), 0).sum(axis=1)
    flux = flux - flux.mean()
    if not np.any(flux):
        return {"bpm": None, "confidence": 0.0, "onset_count": 0}
    rate = sample_rate / hop
    acf = np.correlate(flux, flux, "full")[flux.size - 1:]
    acf = acf / acf[0]
    lag_lo, lag_hi = int(rate * 60 / bpm_max), min(int(rate * 60 / bpm_min), acf.size - 1)
    if lag_hi <= lag_lo + 1:
        return {"bpm": None, "confidence": 0.0, "onset_count": 0}
    lags = np.arange(lag_lo, lag_hi + 1)
    # mild log-Gaussian prior around 120 BPM suppresses octave errors
    prior = np.exp(-0.5 * (np.log2((rate * 60 / lags) / 120.0) / 1.0) ** 2)
    best = lags[np.argmax(acf[lags] * prior)]
    peak = float(acf[best])
    onsets = int(np.sum((flux[1:-1] > flux[:-2]) & (flux[1:-1] >= flux[2:]) & (flux[1:-1] > flux.std())))
    return {"bpm": float(rate * 60 / best), "confidence": max(0.0, min(1.0, peak)),
            "onset_count": onsets}


def musical_summary(samples: np.ndarray, sample_rate: int, a4_hz: float = 440.0) -> dict:
    """One-call musical description used by the GUI, CLI, and reports."""
    chroma = chromagram(samples, sample_rate, a4_hz)
    track = [p for p in pitch_track(samples, sample_rate) if p["f0_hz"] and p["confidence"] > 0.7]
    pitch = None
    if track:
        median_f0 = float(np.median([p["f0_hz"] for p in track]))
        pitch = {**hz_to_note(median_f0, a4_hz), "voiced_frames": len(track)}
    return {"method": "musical-v1", "a4_hz": a4_hz, "key": estimate_key(chroma),
            "tempo": estimate_tempo(samples, sample_rate),
            "dominant_tones": dominant_tones(samples, sample_rate, a4_hz=a4_hz),
            "tuning_offset_cents": estimate_tuning_cents(samples, sample_rate, a4_hz),
            "median_pitch": pitch}
