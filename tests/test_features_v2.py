import json
import tempfile
import threading
import unittest
import wave
from pathlib import Path

import numpy as np

from audio_enviro_fingerprint.audio_io import load_wav
from audio_enviro_fingerprint.case_store import CaseStore
from audio_enviro_fingerprint.comparison import compare_fingerprints
from audio_enviro_fingerprint.features import AnalysisCancelled, analyze_audio
from audio_enviro_fingerprint.fingerprint import make_fingerprint
from audio_enviro_fingerprint.methods.quality import review_quality
from audio_enviro_fingerprint.recurrence import find_recurrences, segment_recording
from audio_enviro_fingerprint.reference import (declared_rate_conflict, validate_reference_metadata)
from audio_enviro_fingerprint.report import build_report
from audio_enviro_fingerprint.transitions import detect_transitions

SR = 8000


def room(seed, seconds, tilt, level):
    """Noise whose spectrum is tilted: tilt<0 dark room, tilt>0 bright room."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec *= (np.maximum(f, 20) / 500.0) ** tilt
    x = np.fft.irfft(spec, n)
    return level * x / np.sqrt(np.mean(x ** 2))


def write_wav(path, channels):
    data = np.stack(channels, axis=1) if len(channels) > 1 else channels[0][:, None]
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1]); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def aba():
    return np.concatenate([room(1, 20, -1.0, 0.05), room(2, 20, 1.5, 0.05), room(3, 20, -1.0, 0.05)])


class RecurrenceTests(unittest.TestCase):
    def test_detects_return_to_first_environment(self):
        analysis = analyze_audio(aba(), SR)
        segs = segment_recording(analysis, detect_transitions(analysis))
        found = find_recurrences(segs)
        self.assertTrue(found, "A-B-A recording must yield a recurrence candidate")
        top = found[0]
        self.assertFalse(top.cross_recording)
        self.assertTrue(top.intervening)
        self.assertIn("confounders", top.to_dict())
        self.assertGreater(top.boundary_uncertainty_seconds, 0)

    def test_continuous_environment_is_not_recurrence(self):
        x = room(1, 60, -1.0, 0.05)
        analysis = analyze_audio(x, SR)
        segs = segment_recording(analysis, detect_transitions(analysis))
        self.assertEqual(find_recurrences(segs), [])

    def test_a_then_b_only_has_no_recurrence(self):
        x = np.concatenate([room(1, 30, -1.0, 0.05), room(2, 30, 1.5, 0.05)])
        analysis = analyze_audio(x, SR)
        segs = segment_recording(analysis, detect_transitions(analysis))
        self.assertEqual(find_recurrences(segs), [])

    def test_cross_recording_match_and_negative_control(self):
        a1 = analyze_audio(room(1, 30, -1.0, 0.05), SR)
        a2 = analyze_audio(room(7, 30, -1.0, 0.05), SR)
        b = analyze_audio(room(2, 30, 1.5, 0.05), SR)
        s1 = segment_recording(a1, [], "r1"); s2 = segment_recording(a2, [], "r2"); sb = segment_recording(b, [], "r3")
        hits = find_recurrences(s1 + s2)
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].cross_recording)
        self.assertEqual(find_recurrences(s1 + sb), [])

    def test_short_segments_are_not_matched(self):
        analysis = analyze_audio(room(1, 2.5, -1.0, 0.05), SR)
        segs = segment_recording(analysis, [])
        self.assertFalse(segs[0].usable)

    def test_invalid_thresholds_rejected(self):
        with self.assertRaises(ValueError):
            find_recurrences([], match_threshold=float("nan"))


class ComparisonV2Tests(unittest.TestCase):
    def fp(self, x):
        return make_fingerprint(analyze_audio(x, SR))

    def test_contributions_sum_to_one_and_are_symmetric(self):
        a, b = self.fp(room(1, 20, -1.0, 0.05)), self.fp(room(2, 20, 1.5, 0.2))
        ab = compare_fingerprints({"version": a.version, "features": a.features}, {"version": b.version, "features": b.features})
        ba = compare_fingerprints({"version": b.version, "features": b.features}, {"version": a.version, "features": a.features})
        self.assertAlmostEqual(sum(i["contribution_fraction"] for i in ab.differences.values()), 1.0)
        self.assertAlmostEqual(ab.score, ba.score)
        self.assertAlmostEqual(sum(ab.group_contributions.values()), 1.0)
        self.assertTrue(any("level" in w for w in ab.warnings))
        self.assertFalse(ab.to_dict()["score_is_probability"])

    def test_identical_has_zero_contribution_and_score_one(self):
        a = self.fp(room(1, 20, -1.0, 0.05))
        c = compare_fingerprints(a.features, a.features)
        self.assertEqual(c.score, 1.0)

    def test_sample_rate_warning(self):
        a = self.fp(room(1, 20, -1.0, 0.05)).features
        b = dict(a, sample_rate_hz=16000)
        self.assertTrue(any("Sample rates" in w for w in compare_fingerprints(a, b).warnings))


GOOD = {k: "x" for k in ("location_identifier", "operator", "authority_basis", "recorder_make_model",
        "recorder_serial", "microphone_make_model", "microphone_serial", "input_chain", "channel",
        "placement", "orientation", "source_signal", "occupancy_activity")}
GOOD.update(acquisition_datetime="2026-10-14T09:30:00+00:00", sample_rate_hz=8000, height_m=1.5,
            checklist_confirmed=True)


class ReferenceTests(unittest.TestCase):
    def test_validation_reports_missing_and_bad_fields(self):
        self.assertTrue(validate_reference_metadata({}))
        self.assertEqual(validate_reference_metadata(GOOD), [])
        self.assertTrue(validate_reference_metadata(dict(GOOD, acquisition_datetime="yesterday")))
        self.assertTrue(validate_reference_metadata(dict(GOOD, height_m="-1")))
        self.assertTrue(validate_reference_metadata(dict(GOOD, checklist_confirmed=False)))

    def test_reference_is_immutable_and_hash_bound(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "ref.wav"
            write_wav(wav, [room(1, 40, -1.0, 0.05)])
            audio = load_wav(wav)
            quality = review_quality(audio.samples, audio.sample_rate)
            with CaseStore(Path(tmp) / "c.sqlite") as store:
                rid = store.add_reference(wav, GOOD, quality)
                self.assertEqual(store.verify_reference(rid), {"reference_id": rid, "source_hash_matches": True, "metadata_hash_matches": True})
                with self.assertRaises(sqlite3.DatabaseError):
                    store.connection.execute("UPDATE reference_exemplars SET source_path='x'")
                with self.assertRaises(sqlite3.DatabaseError):
                    store.connection.execute("DELETE FROM reference_exemplars")
                with self.assertRaises(ValueError):
                    store.add_reference(wav, {}, quality)
                wav.write_bytes(wav.read_bytes() + b"\0")
                self.assertFalse(store.verify_reference(rid)["source_hash_matches"])

    def test_declared_rate_conflict(self):
        self.assertIsNone(declared_rate_conflict(GOOD, 8000))
        self.assertIn("differs", declared_rate_conflict(GOOD, 44100))


class QualityTests(unittest.TestCase):
    def test_flags_clipping_dc_short_and_silence(self):
        bad = review_quality(np.ones(SR), SR)
        self.assertEqual(bad["overall"], "fail")
        good = review_quality(room(1, 40, -1.0, 0.05), SR)
        self.assertNotEqual(good["overall"], "fail")
        self.assertEqual(review_quality(np.zeros(SR * 40), SR)["overall"], "fail")
        with self.assertRaises(ValueError):
            review_quality(np.array([]), SR)


class ChannelAndCancelTests(unittest.TestCase):
    def test_channel_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "s.wav"
            write_wav(p, [np.full(SR, 0.1), np.full(SR, 0.5)])
            self.assertAlmostEqual(load_wav(p, 1).samples[0], 0.5, places=3)
            self.assertEqual(load_wav(p, 1).channel_index, 1)
            with self.assertRaises(ValueError):
                load_wav(p, 2)

    def test_cancellation_and_progress(self):
        ev = threading.Event(); ev.set()
        with self.assertRaises(AnalysisCancelled):
            analyze_audio(room(1, 20, -1.0, 0.05), SR, cancel=ev)
        seen = []
        analyze_audio(room(1, 30, -1.0, 0.05), SR, progress=seen.append)
        self.assertTrue(seen and all(0 <= v <= 1 for v in seen))


class ReportTests(unittest.TestCase):
    def test_report_serializes_with_recurrence(self):
        analysis = analyze_audio(aba(), SR)
        r = build_report(source_path="x.wav", sha256="0" * 64, channel_index=0, channel_count=1,
                         analysis=analysis, fingerprint=make_fingerprint(analysis), notes=[])
        text = json.dumps(r, allow_nan=False)
        self.assertEqual(json.loads(text)["schema_version"], "aefp-report-2")
        self.assertTrue(r["recurrence"]["candidates"])


if __name__ == "__main__":
    unittest.main()
