import math
import struct
import tempfile
import threading
import unittest
import wave
from pathlib import Path

import numpy as np

from audio_enviro_fingerprint.audio_io import (SUPPORTED_EXTENSIONS, AudioData, load_audio, load_wav,
                                               soundfile_available)
from audio_enviro_fingerprint.features import AnalysisCancelled, analyze_audio

HAS_SOUNDFILE = soundfile_available()
_PCM_GUID = struct.pack("<H", 1) + b"\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
_FLOAT_GUID = struct.pack("<H", 3) + _PCM_GUID[2:]


def _encode_pcm(frames: np.ndarray, width: int) -> bytes:
    if width == 1:
        return (np.round(frames * 127) + 128).astype(np.uint8).tobytes()
    scale = (1 << (8 * width - 1)) - 1
    ints = np.round(frames * scale).astype(np.int64)
    if width == 3:
        return b"".join(int(v & 0xFFFFFF).to_bytes(3, "little") for v in ints.ravel())
    return ints.astype({2: "<i2", 4: "<i4"}[width]).tobytes()


def _write_stdlib(path: Path, frames: np.ndarray, width: int, rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(frames.shape[1])
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(_encode_pcm(frames, width))


def _write_riff(path: Path, fmt: bytes, payload: bytes, declared: int | None = None) -> None:
    size = len(payload) if declared is None else declared
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", size) + payload + (b"\x00" if len(payload) & 1 else b"")
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def _fmt(tag: int, channels: int, rate: int, bits: int, guid: bytes | None = None, valid: int | None = None) -> bytes:
    align = channels * bits // 8
    base = struct.pack("<HHIIHH", tag, channels, rate, rate * align, align, bits)
    if guid is None:
        return base + (struct.pack("<H", 0) if tag != 1 else b"")
    return base + struct.pack("<HHI", 22, valid or bits, 0) + guid


def _stereo(n: int = 400) -> np.ndarray:
    t = np.arange(n) / 8000
    return np.column_stack([0.5 * np.sin(2 * math.pi * 440 * t), -0.25 * np.sin(2 * math.pi * 440 * t)])


class PcmWavTests(unittest.TestCase):
    def test_integer_pcm_widths_round_trip(self):
        frames = _stereo()
        for width in (1, 2, 3, 4):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "pcm.wav"
                _write_stdlib(path, frames, width)
                audio = load_audio(path)
                self.assertIsInstance(audio, AudioData)
                self.assertEqual((audio.channels, audio.sample_rate, audio.source_width_bytes), (2, 8000, width))
                self.assertEqual(audio.channel_data.shape, (400, 2))
                self.assertEqual(audio.channel_data.dtype, np.float64)
                tolerance = 2.0 / (1 << (8 * width - 1)) + 1e-9
                self.assertLess(float(np.max(np.abs(audio.channel_data - frames))), tolerance)
                self.assertEqual(audio.decoder["backend"], "stdlib-wave")
                self.assertEqual(audio.decoder["container"], "WAV")
                self.assertFalse(audio.decoder["lossy"])
                self.assertEqual(audio.decoder["encoding"], "pcm_u8" if width == 1 else f"pcm_s{width * 8}")

    def test_channel_selection_and_accessor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stereo.wav"
            _write_stdlib(path, _stereo(), 2)
            second = load_audio(path, channel=1)
            self.assertEqual(second.selected_channel, 1)
            np.testing.assert_array_equal(second.samples, second.channel_data[:, 1])
            np.testing.assert_array_equal(second.channel(0), load_wav(path).samples)
            with self.assertRaises(ValueError):
                second.channel(2)

    def test_invalid_channel_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stereo.wav"
            _write_stdlib(path, _stereo(), 2)
            for bad in (2, -1, 1.0, True):
                with self.subTest(channel=bad), self.assertRaises(ValueError):
                    load_audio(path, channel=bad)

    def test_truncated_pcm_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.wav"
            _write_stdlib(path, _stereo(), 2)
            path.write_bytes(path.read_bytes()[:-6])
            with self.assertRaises(ValueError):
                load_audio(path)

    def test_empty_and_garbage_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.wav"
            _write_stdlib(empty, np.zeros((0, 1)), 2)
            garbage = Path(tmp) / "garbage.wav"
            garbage.write_bytes(b"RIFF\x04\x00\x00\x00WAVEjunk")
            for path in (empty, garbage, Path(tmp) / "missing.wav"):
                with self.subTest(path=path.name), self.assertRaises(ValueError):
                    load_audio(path)


class RiffWavTests(unittest.TestCase):
    def test_float32_wav(self):
        frames = _stereo().astype("<f4")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "float.wav"
            _write_riff(path, _fmt(3, 2, 8000, 32), frames.tobytes())
            audio = load_audio(path, channel=1)
            self.assertEqual(audio.decoder["encoding"], "float32")
            self.assertEqual(audio.decoder["backend"], "riff-numpy")
            self.assertEqual(audio.source_width_bytes, 0)
            np.testing.assert_array_equal(audio.samples, frames[:, 1].astype(np.float64))

    def test_float_wav_rejects_non_finite(self):
        frames = _stereo().astype("<f4")
        frames[10, 0] = np.nan
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nan.wav"
            _write_riff(path, _fmt(3, 2, 8000, 32), frames.tobytes())
            with self.assertRaises(ValueError):
                load_audio(path)

    def test_extensible_pcm_and_float(self):
        frames = _stereo()
        cases = (("pcm24", _fmt(0xFFFE, 2, 8000, 24, _PCM_GUID), _encode_pcm(frames, 3), "pcm_s24", 3),
                 ("float64", _fmt(0xFFFE, 2, 8000, 64, _FLOAT_GUID), frames.astype("<f8").tobytes(), "float64", 0))
        for name, fmt, payload, encoding, width in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / f"{name}.wav"
                _write_riff(path, fmt, payload)
                audio = load_audio(path)
                self.assertEqual(audio.decoder["encoding"], encoding)
                self.assertEqual(audio.source_width_bytes, width)
                self.assertIn("WAVE_FORMAT_EXTENSIBLE header", audio.decoder["notes"])
                self.assertLess(float(np.max(np.abs(audio.channel_data - frames))), 1e-6)
                np.testing.assert_array_equal(load_wav(path).samples, audio.samples)

    def test_extensible_truncated_rejected(self):
        payload = _encode_pcm(_stereo(), 2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trunc.wav"
            _write_riff(path, _fmt(0xFFFE, 2, 8000, 16, _PCM_GUID), payload[:-10], declared=len(payload))
            with self.assertRaises(ValueError):
                load_audio(path)

    def test_unsupported_wav_codec_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adpcm.wav"
            _write_riff(path, _fmt(2, 1, 8000, 16), b"\x00" * 64)
            with self.assertRaises(ValueError):
                load_audio(path)


class SoundfileTests(unittest.TestCase):
    def test_extensions_listed(self):
        for ext in (".wav", ".flac", ".aiff", ".ogg", ".mp3", ".rf64", ".w64"):
            self.assertIn(ext, SUPPORTED_EXTENSIONS)

    @unittest.skipUnless(HAS_SOUNDFILE, "soundfile not installed")
    def test_flac_round_trip(self):
        import soundfile
        frames = _stereo()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.flac"
            soundfile.write(str(path), frames, 8000, subtype="PCM_16")
            audio = load_audio(path, channel=1)
            self.assertEqual(audio.decoder["backend"], "soundfile")
            self.assertEqual(audio.decoder["container"], "FLAC")
            self.assertFalse(audio.decoder["lossy"])
            self.assertEqual(audio.source_width_bytes, 2)
            self.assertEqual(audio.channels, 2)
            self.assertLess(float(np.max(np.abs(audio.samples - frames[:, 1]))), 1e-4)

    @unittest.skipUnless(HAS_SOUNDFILE, "soundfile not installed")
    def test_lossy_codec_flagged(self):
        import soundfile
        t = np.arange(16000) / 16000
        frames = 0.3 * np.sin(2 * math.pi * 440 * t)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.ogg"
            soundfile.write(str(path), frames, 16000, format="OGG", subtype="VORBIS")
            audio = load_audio(path)
            self.assertTrue(audio.decoder["lossy"])
            self.assertEqual(audio.decoder["encoding"], "vorbis")
            self.assertEqual(audio.source_width_bytes, 0)
            self.assertTrue(any("Lossy" in note for note in audio.decoder["notes"]))

    def test_non_wav_without_decoder_is_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "noise.flac"
            path.write_bytes(b"not really audio data at all")
            with self.assertRaises(ValueError):
                load_audio(path)


class ProgressCancelTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        self.samples = 0.1 * rng.standard_normal(8000 * 12)

    def test_progress_monotonic_and_output_unchanged(self):
        seen = []
        with_progress = analyze_audio(self.samples, 8000, frame_seconds=1, hop_seconds=0.5,
                                      progress=seen.append, cancel=threading.Event())
        plain = analyze_audio(self.samples, 8000, frame_seconds=1, hop_seconds=0.5)
        self.assertEqual(with_progress.to_dict(), plain.to_dict())
        self.assertGreater(len(seen), 2)
        self.assertEqual(seen[0], 0.0)
        self.assertEqual(seen[-1], 1.0)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in seen))
        self.assertTrue(all(b >= a for a, b in zip(seen, seen[1:])))

    def test_progress_reaches_one_without_frames(self):
        seen = []
        analyze_audio(np.zeros(10), 8000, progress=seen.append)
        self.assertEqual(seen[-1], 1.0)

    def test_cancellation(self):
        cancel = threading.Event()
        calls = []

        def progress(value):
            calls.append(value)
            if value > 0.2:
                cancel.set()

        with self.assertRaises(AnalysisCancelled):
            analyze_audio(self.samples, 8000, frame_seconds=1, hop_seconds=0.1, progress=progress, cancel=cancel)
        self.assertLess(calls[-1], 1.0)
        already = threading.Event()
        already.set()
        with self.assertRaises(AnalysisCancelled):
            analyze_audio(self.samples, 8000, cancel=already)


if __name__ == "__main__":
    unittest.main()
