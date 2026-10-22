"""Log-magnitude spectrogram and a dependency-free PNG encoder for display/export."""
from __future__ import annotations

import struct
import zlib

import numpy as np

from .validation import audio_input


def compute_spectrogram(samples: np.ndarray, sample_rate: int, n_fft: int = 1024,
                        max_columns: int = 1200, floor_db: float = -100.0) -> dict:
    x, sample_rate = audio_input(samples, sample_rate)
    if type(n_fft) is not int or n_fft < 3 or type(max_columns) is not int or max_columns < 1 or not np.isfinite(floor_db):
        raise ValueError("Expected FFT size >=3, positive column count and finite floor")
    if x.size < n_fft:
        x = np.pad(x, (0, n_fft - x.size))
    hop = x.size if max_columns == 1 else max(n_fft // 2, int(np.ceil((x.size - n_fft) / (max_columns - 1))))
    count = 1 + (x.size - n_fft) // hop
    index = np.arange(n_fft)[None, :] + hop * np.arange(count)[:, None]
    window = np.hanning(n_fft)
    mag = np.abs(np.fft.rfft(x[index] * window, axis=1)) / (window.sum() / 2)
    db = np.maximum(20 * np.log10(np.maximum(mag, 1e-12)), floor_db)
    return {"db": db.T, "frequencies_hz": np.fft.rfftfreq(n_fft, 1.0 / sample_rate),
            "times_s": (np.arange(count) * hop + n_fft / 2) / sample_rate, "n_fft": n_fft, "hop": hop}


_STOPS = np.array([[0, 0, 4], [66, 10, 104], [147, 38, 103], [221, 81, 58], [252, 165, 10], [252, 255, 164]],
                  dtype=np.float64)


def colorize(db: np.ndarray, height: int = 256, dynamic_range_db: float = 80.0) -> np.ndarray:
    """Map a (freq x time) dB array to uint8 RGB, low frequencies at the bottom."""
    db = np.asarray(db, dtype=np.float64)
    if db.ndim != 2 or not all(db.shape) or not np.all(np.isfinite(db)):
        raise ValueError("Spectrogram must be a nonempty finite frequency-by-time matrix")
    if type(height) is not int or height < 1 or not np.isfinite(dynamic_range_db) or dynamic_range_db <= 0:
        raise ValueError("Image height and finite dynamic range must be positive")
    top = float(db.max())
    norm = np.clip((db - (top - dynamic_range_db)) / dynamic_range_db, 0, 1)
    rows = np.linspace(norm.shape[0] - 1, 0, height).astype(int)
    norm = norm[rows]
    pos = norm * (len(_STOPS) - 1)
    lo = np.minimum(pos.astype(int), len(_STOPS) - 2)
    frac = (pos - lo)[..., None]
    return (_STOPS[lo] * (1 - frac) + _STOPS[lo + 1] * frac).astype(np.uint8)


def encode_png(rgb: np.ndarray) -> bytes:
    """Encode an (H, W, 3) uint8 array as PNG."""
    rgb = np.asarray(rgb)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or not all(rgb.shape) or rgb.dtype != np.uint8:
        raise ValueError("PNG input must be a nonempty height-by-width-by-3 uint8 RGB array")
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def spectrogram_png(samples: np.ndarray, sample_rate: int, height: int = 256) -> bytes:
    return encode_png(colorize(compute_spectrogram(samples, sample_rate)["db"], height))
