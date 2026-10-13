import hashlib
import json
import math
import tempfile
import unittest
import wave
from pathlib import Path

from audio_enviro_fingerprint.audio_io import load_wav
from audio_enviro_fingerprint.comparison import compare_fingerprints
from audio_enviro_fingerprint.case_store import CaseStore
from audio_enviro_fingerprint.features import analyze_audio
from audio_enviro_fingerprint.fingerprint import make_fingerprint
from audio_enviro_fingerprint.integrity import sha256_file
from audio_enviro_fingerprint.methods.reverberation import estimate_t20
from audio_enviro_fingerprint.transitions import detect_transitions


class IntegrityTests(unittest.TestCase):
    def test_sha256_is_hash_of_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            path.write_bytes(b"evidence bytes\x00")
            self.assertEqual(sha256_file(path), hashlib.sha256(path.read_bytes()).hexdigest())


class CaseStoreTests(unittest.TestCase):
    def test_persists_timestamped_note_linked_to_original_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "case.sqlite"
            evidence = Path(tmp) / "recording.wav"
            evidence.write_bytes(b"sample")
            with CaseStore(db) as store:
                evidence_id = store.register_evidence(evidence)
                first_digest = store.evidence_record(evidence_id)["sha256"]
                note_id = store.add_note(evidence_id, 12.5, "Fan starts", "Observed increase in low-frequency noise")
                notes = store.notes_for(evidence_id)
                evidence.write_bytes(b"changed")
                changed_id = store.register_evidence(evidence)
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0]["id"], note_id)
            self.assertEqual(notes[0]["timestamp_seconds"], 12.5)
            self.assertEqual(notes[0]["evidence_sha256"], hashlib.sha256(b"sample").hexdigest())
            self.assertNotEqual(evidence_id, changed_id)
            self.assertEqual(first_digest, hashlib.sha256(b"sample").hexdigest())


class AudioIoTests(unittest.TestCase):
    def test_loads_24_bit_pcm_and_preserves_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tone.wav"
            values = [0, 0.5, -0.5, 0]
            packed = bytearray()
            for value in values:
                raw = int(value * ((1 << 23) - 1)) & 0xFFFFFF
                packed.extend((raw & 255, (raw >> 8) & 255, (raw >> 16) & 255))
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(3)
                wf.setframerate(8000)
                wf.writeframes(packed)
            audio = load_wav(path)
            self.assertEqual(audio.sample_rate, 8000)
            self.assertAlmostEqual(audio.duration_seconds, 4 / 8000)
            self.assertAlmostEqual(float(audio.samples[1]), 0.5, places=4)

    def test_selects_first_channel_without_phase_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stereo.wav"
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                wf.writeframes(b"".join(int(v).to_bytes(2, "little", signed=True)
                                         for pair in ((12000, -12000), (9000, -9000)) for v in pair))
            audio = load_wav(path)
            self.assertEqual(audio.channels, 2)
            self.assertGreater(float(abs(audio.samples).mean()), 0.2)

    def test_rejects_non_pcm_wave(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.wav"
            path.write_bytes(b"not a wave")
            with self.assertRaises(ValueError):
                load_wav(path)

    def test_rejects_truncated_pcm_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "truncated.wav"
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                wf.writeframes(b"\x01\x00" * 32)
            path.write_bytes(path.read_bytes()[:-4])
            with self.assertRaises(ValueError):
                load_wav(path)


class FeatureTests(unittest.TestCase):
    def test_tone_has_expected_peak_band(self):
        import numpy as np

        rate = 8000
        t = np.arange(rate * 3) / rate
        samples = 0.4 * np.sin(2 * math.pi * 440 * t)
        result = analyze_audio(samples, rate, frame_seconds=1, hop_seconds=1)
        self.assertEqual(len(result.frames), 3)
        bands = result.frames[0].band_power_db
        self.assertGreater(bands["250-500 Hz"], bands["0-125 Hz"])
        self.assertGreater(bands["250-500 Hz"], bands["1000-2000 Hz"])

    def test_band_power_is_consistent_across_sample_rates(self):
        import numpy as np

        levels = []
        for rate in (8000, 16000):
            t = np.arange(rate * 2) / rate
            result = analyze_audio(0.4 * np.sin(2 * math.pi * 440 * t), rate,
                                  frame_seconds=1, hop_seconds=1)
            levels.append(result.frames[0].band_power_db["250-500 Hz"])
        self.assertAlmostEqual(levels[0], levels[1], delta=1.0)

    def test_fingerprint_has_stable_versioned_serialization(self):
        import numpy as np

        signal = np.sin(2 * math.pi * 300 * np.arange(16000) / 8000) * 0.1
        analysis = analyze_audio(signal, 8000)
        first = make_fingerprint(analysis)
        second = make_fingerprint(analysis)
        self.assertEqual(first.fingerprint_hash, second.fingerprint_hash)
        self.assertEqual(first.version, "aefp-1")
        self.assertEqual(json.loads(first.canonical_json)["version"], "aefp-1")


class ReverberationTests(unittest.TestCase):
    def test_estimates_rt60_from_known_exponential_decay(self):
        import numpy as np

        rate = 8000
        t = np.arange(rate * 3) / rate
        # Amplitude falls 60 dB in 1.2 s, yielding a 1.2 s T20 extrapolation.
        envelope = 10 ** (-60 * t / (20 * 1.2))
        impulse = envelope * np.random.default_rng(42).normal(0, 1, len(t))
        result = estimate_t20(impulse, rate)
        self.assertAlmostEqual(result["rt60_seconds"], 1.2, delta=0.12)
        self.assertEqual(result["method"], "schroeder-t20-experimental-v1")


class ComparisonTests(unittest.TestCase):
    def test_reports_per_feature_differences_and_similarity(self):
        first = {"version": "aefp-1", "features": {"spectral_centroid_hz": 500, "frame_rms_dbfs_p10": -60}}
        same = {"version": "aefp-1", "features": {"spectral_centroid_hz": 510, "frame_rms_dbfs_p10": -59}}
        different = {"version": "aefp-1", "features": {"spectral_centroid_hz": 5000, "frame_rms_dbfs_p10": -25}}
        near = compare_fingerprints(first, same)
        far = compare_fingerprints(first, different)
        self.assertGreater(near.score, far.score)
        self.assertIn("spectral_centroid_hz", near.differences)
        self.assertIn("frame_rms_dbfs_p10", near.differences)
        self.assertIn("normalized_delta", near.differences["frame_rms_dbfs_p10"])
        self.assertIsInstance(near.explanation, str)

    def test_refuses_incompatible_fingerprint_versions(self):
        with self.assertRaises(ValueError):
            compare_fingerprints({"version": "aefp-1", "features": {"x": 1}},
                                 {"version": "aefp-2", "features": {"x": 1}})


class TransitionTests(unittest.TestCase):
    def test_detects_clear_step_change_and_records_feature_evidence(self):
        import numpy as np

        rate = 8000
        t = np.arange(rate * 10) / rate
        left = 0.15 * np.sin(2 * math.pi * 220 * t[:rate * 5])
        right = 0.15 * np.sin(2 * math.pi * 1800 * t[:rate * 5])
        analysis = analyze_audio(np.concatenate([left, right]), rate,
                                 frame_seconds=1, hop_seconds=1)
        events = detect_transitions(analysis, threshold=0.25, minimum_separation_seconds=1)
        self.assertTrue(events)
        self.assertAlmostEqual(events[0].timestamp_seconds, 5.0, delta=1.1)
        self.assertTrue(events[0].evidence)

    def test_empty_or_single_frame_has_no_transition(self):
        event = detect_transitions(type("Analysis", (), {"frames": []})())
        self.assertEqual(event, [])

    def test_rejects_non_finite_minimum_separation(self):
        with self.assertRaises(ValueError):
            detect_transitions(type("Analysis", (), {"frames": []})(), minimum_separation_seconds=float("nan"))


if __name__ == "__main__":
    unittest.main()
