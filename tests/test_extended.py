import json
import struct
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from audio_enviro_fingerprint.audio_io import load_wav
from audio_enviro_fingerprint.case_store import CaseStore
from audio_enviro_fingerprint.cli import run
from audio_enviro_fingerprint.features import analyze_audio
from audio_enviro_fingerprint.methods.hum import detect_mains_hum
from audio_enviro_fingerprint.methods.musical import (chromagram, dominant_tones, estimate_key,
                                                     estimate_tempo, hz_to_note, pitch_track)
from audio_enviro_fingerprint.multichannel import channel_pair_metrics
from audio_enviro_fingerprint.recurrence import find_recurrences
from audio_enviro_fingerprint.reference import ReferenceMetadata, review_reference
from audio_enviro_fingerprint.report import build_report, verify_report, write_report
from audio_enviro_fingerprint.spectrogram import compute_spectrogram, spectrogram_png

SR = 16000


def tone(freq, seconds, amp=0.3, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    return amp * np.sin(2 * np.pi * freq * t)


def write_wav(path, data, sr=SR, float_format=False, channels=1, extensible=False):
    data = np.asarray(data)
    if float_format:
        payload, tag, bits = data.astype("<f4").tobytes(), 3, 32
    else:
        payload, tag, bits = (np.clip(data, -1, 1) * 32767).astype("<i2").tobytes(), 1, 16
    fmt = struct.pack("<HHIIHH", tag, channels, sr, sr * channels * bits // 8, channels * bits // 8, bits)
    if extensible:
        fmt = struct.pack("<HHIIHH", 0xFFFE, channels, sr, sr * channels * bits // 8, channels * bits // 8, bits)
        fmt += struct.pack("<HHI", 22, bits, 3) + struct.pack("<H", tag) + b"\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(payload)) + payload
    Path(path).write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


class WavFormatTests(unittest.TestCase):
    def test_float_and_extensible_and_all_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            stereo = np.stack([tone(440, 1), -tone(440, 1)], axis=1)
            for kwargs in ({"float_format": True}, {"extensible": True}, {"float_format": True, "extensible": True}):
                p = Path(tmp) / "x.wav"
                write_wav(p, stereo.reshape(-1), channels=2, **kwargs)
                audio = load_wav(p)
                self.assertEqual((audio.channels, audio.all_channels.shape), (2, (SR, 2)))
                self.assertAlmostEqual(float(audio.channel(1)[100]), -float(audio.channel(0)[100]), places=3)
            self.assertEqual(audio.sample_format, "float")

    def test_rejects_nan_float_and_unknown_codec(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "nan.wav"
            write_wav(p, np.array([0.0, np.nan] * 100), float_format=True)
            with self.assertRaises(ValueError):
                load_wav(p)
            raw = bytearray(Path(tmp, "nan.wav").read_bytes())
            raw[20:22] = struct.pack("<H", 0x55)    # MP3 tag
            p.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_wav(p)


class MusicalTests(unittest.TestCase):
    def test_note_naming(self):
        n = hz_to_note(440.0)
        self.assertEqual((n["note"], round(n["cents"])), ("A4", 0))
        self.assertEqual(hz_to_note(261.63)["note"], "C4")
        with self.assertRaises(ValueError):
            hz_to_note(0)

    def test_pitch_and_dominant_tone(self):
        x = tone(220, 3)
        track = [p["f0_hz"] for p in pitch_track(x, SR) if p["f0_hz"]]
        self.assertAlmostEqual(float(np.median(track)), 220.0, delta=1.0)
        self.assertEqual(dominant_tones(x, SR, 1)[0]["note"], "A3")

    def test_key_estimate_c_major(self):
        x = sum(tone(f, 6, 0.2) for f in (261.63, 329.63, 392.0))
        key = estimate_key(chromagram(x, SR))
        self.assertEqual((key["key"], key["mode"]), ("C", "major"))
        self.assertIsNone(estimate_key(np.zeros((3, 12)))["key"])

    def test_tempo_from_click_train(self):
        c = np.zeros(SR * 16)
        c[::SR // 2] = 1.0
        c = np.convolve(c, np.exp(-np.arange(200) / 20.0))[:c.size]
        self.assertAlmostEqual(estimate_tempo(c, SR)["bpm"], 120.0, delta=2.0)
        self.assertIsNone(estimate_tempo(np.zeros(100), SR)["bpm"])

    def test_mains_hum(self):
        rng = np.random.default_rng(1)
        hum = tone(60, 4, 0.1) + tone(120, 4, 0.05) + rng.normal(0, 0.005, 4 * SR)
        self.assertEqual(detect_mains_hum(hum, SR)["fundamental_hz"], 60.0)
        self.assertFalse(detect_mains_hum(rng.normal(0, 0.1, 4 * SR), SR)["detected"])


class RecurrenceTests(unittest.TestCase):
    def _rooms(self):
        rng = np.random.default_rng(2)
        a = rng.normal(0, 0.02, SR * 12)
        b = tone(1500, 12, 0.3) + rng.normal(0, 0.01, SR * 12)
        return a, b, rng

    def test_detects_return_after_departure(self):
        a, b, rng = self._rooms()
        x = np.concatenate([a, b, rng.normal(0, 0.02, SR * 12)])
        found = find_recurrences(analyze_audio(x, SR))
        self.assertTrue(found)
        self.assertGreaterEqual(found[0].later_start_s, 23.0)
        self.assertLessEqual(found[0].earlier_start_s, 2.0)
        self.assertIn("rms_dbfs", found[0].feature_deltas)

    def test_no_recurrence_without_return_and_cross_recording(self):
        a, b, rng = self._rooms()
        self.assertEqual(find_recurrences(analyze_audio(np.concatenate([a, b]), SR)), [])
        cross = find_recurrences(analyze_audio(b, SR), analyze_audio(np.concatenate([a, b]), SR))
        self.assertTrue(cross and cross[0].earlier_start_s >= 11.0)
        with self.assertRaises(ValueError):
            find_recurrences(analyze_audio(a, SR), threshold=1.0, departure=0.5)


class MultichannelTests(unittest.TestCase):
    def test_lag_and_level(self):
        rng = np.random.default_rng(3)
        a = rng.normal(0, 0.1, SR * 2)
        b = np.roll(a, 8) * 0.5
        m = channel_pair_metrics(a, b, SR)
        self.assertEqual(m["peak_lag_samples"], -8)
        self.assertAlmostEqual(m["level_difference_db"], 6.02, delta=0.1)
        anti = channel_pair_metrics(a, -a, SR)
        self.assertAlmostEqual(anti["correlation_zero_lag"], -1.0, places=3)


class ReferenceAndStoreTests(unittest.TestCase):
    def test_review_flags_gaps_and_clipping(self):
        meta = ReferenceMetadata(location_id="Room 1")
        r = review_reference(meta, np.ones(SR), SR)
        status = {c["check"]: c["status"] for c in r["checks"]}
        self.assertEqual((r["overall"], status["required_metadata"], status["clipping"]), ("fail",) * 3)
        full = ReferenceMetadata(**{k: "x" for k in ("location_id", "recorded_utc", "operator", "recorder_make_model",
                                                      "microphone_make_model", "input_chain", "channel_assignment",
                                                      "placement", "orientation", "height_m", "source_signal",
                                                      "occupancy_activity", "authority_or_consent", "calibration")})
        full.repeat_number = 3
        self.assertEqual(review_reference(full, tone(300, 70, 0.1, 48000), 48000)["overall"], "pass")

    def test_store_references_and_marker_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.wav"
            f.write_bytes(b"abc")
            with CaseStore(Path(tmp) / "c.db") as s:
                eid = s.register_evidence(f)
                s.add_reference(eid, ReferenceMetadata(location_id="L").to_dict(), {"overall": "fail"})
                self.assertEqual(s.references()[0]["metadata"]["location_id"], "L")
                key = s.save_marker(eid, 5.0, "door")
                s.save_marker(eid, 6.0, "door (moved)", key)
                self.assertEqual(s.markers_for(eid)[0]["timestamp_seconds"], 6.0)
                self.assertEqual(len(s.markers_for(eid, True)), 2)
                s.save_marker(eid, 6.0, "door (moved)", key, deleted=True)
                self.assertEqual(s.markers_for(eid), [])
                with self.assertRaises(ValueError):
                    s.save_marker(eid, 1.0, "x", 999)


class ReportAndCliTests(unittest.TestCase):
    def test_manifest_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "s.wav"
            src.write_bytes(b"1")
            import hashlib
            rep = Path(tmp) / "r.json"
            write_report(rep, build_report(src, hashlib.sha256(b"1").hexdigest(), {"a": 1}))
            self.assertTrue(verify_report(rep)["manifest_ok"] and verify_report(rep)["evidence_ok"])
            src.write_bytes(b"2")
            self.assertFalse(verify_report(rep)["evidence_ok"])
            data = json.loads(rep.read_text())
            data["sections"]["a"] = 2
            rep.write_text(json.dumps(data))
            self.assertFalse(verify_report(rep)["manifest_ok"])

    def test_spectrogram_png(self):
        png = spectrogram_png(tone(1000, 2), SR, 64)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        spec = compute_spectrogram(tone(1000, 2), SR)
        peak = spec["frequencies_hz"][spec["db"].mean(axis=1).argmax()]
        self.assertAlmostEqual(float(peak), 1000.0, delta=20)

    def test_cli_analyze_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav, rep, png = (Path(tmp) / n for n in ("a.wav", "r.json", "s.png"))
            write_wav(wav, tone(440, 6) + tone(660, 6, 0.1))
            self.assertEqual(run(["analyze", str(wav), "-o", str(rep)]), 0)
            self.assertEqual(run(["verify", str(rep)]), 0)
            self.assertEqual(run(["spectrogram", str(wav), str(png)]), 0)
            self.assertEqual(run(["compare", str(wav), str(wav)]), 0)
            report = json.loads(rep.read_text())
            self.assertEqual(report["sections"]["musical"]["dominant_tones"][0]["note"], "A4")
            self.assertEqual(run(["analyze", str(Path(tmp) / "missing.wav")]), 1)


if __name__ == "__main__":
    unittest.main()
