"""Recording-quality review used for reference exemplars (descriptive checks only)."""
from __future__ import annotations

import numpy as np

from ..validation import audio_input

def dbfs(value):
    return float(20 * np.log10(max(float(value), 1e-12)))

CLIP_LEVEL = 0.991  # 8-bit positive full scale decodes to 127/128 = 0.992
MIN_REFERENCE_SECONDS = 30.0
MIN_SAMPLE_RATE = 16000


def review_quality(samples: np.ndarray, sample_rate: int) -> dict:
    x, sample_rate = audio_input(samples, sample_rate)
    if x.ndim != 1 or x.size == 0 or sample_rate <= 0 or not np.all(np.isfinite(x)):
        raise ValueError("Expected non-empty mono samples and a positive sample rate")
    peak = float(np.max(np.abs(x)))
    clipped = float(np.mean(np.abs(x) >= CLIP_LEVEL))
    dc = float(np.mean(x))
    frame = max(1, sample_rate // 10)
    n = x.size // frame
    silent = 0.0
    if x.size < frame:
        silent = float(20 * np.log10(max(float(np.sqrt(np.mean(x ** 2))), 1e-12)) < -70.0)
    if n:
        levels = 20 * np.log10(np.maximum(np.sqrt(np.mean(x[:n * frame].reshape(n, frame) ** 2, axis=1)), 1e-12))
        silent = float(np.mean(levels < -70.0))
    duration = x.size / sample_rate
    checks = []

    def check(name, status, value, detail):
        checks.append({"check": name, "status": status, "value": value, "detail": detail})

    check("duration", "pass" if duration >= MIN_REFERENCE_SECONDS else "warn", duration,
          f"At least {MIN_REFERENCE_SECONDS:.0f} s recommended for a stable median fingerprint")
    check("sample_rate", "pass" if sample_rate >= MIN_SAMPLE_RATE else "warn", sample_rate,
          f"At least {MIN_SAMPLE_RATE} Hz recommended so the 0-4 kHz bands are not Nyquist-limited")
    check("clipping", "pass" if clipped == 0 else "fail" if clipped > 0.001 else "warn", clipped,
          "Fraction of samples at full scale; clipping distorts spectra")
    check("peak_dbfs", "pass" if peak < CLIP_LEVEL else "warn", dbfs(peak), "Peak level; headroom indicator")
    check("dc_offset", "pass" if abs(dc) < 0.01 else "warn", dc, "Mean sample value; large offsets bias low bands")
    check("silence_fraction", "pass" if silent < 0.2 else "fail" if silent > 0.8 else "warn", silent,
          "Fraction of 100 ms blocks below -70 dBFS (possible dropout or muted input)")
    statuses = {c["status"] for c in checks}
    overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {"overall": overall, "checks": checks, "method": "reference-quality-v1"}
