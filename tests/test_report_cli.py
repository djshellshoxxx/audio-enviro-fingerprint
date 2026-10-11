import contextlib
import io
import json
import math
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from audio_enviro_fingerprint import __version__
from audio_enviro_fingerprint.benchmark import format_summary, match_events, roc_auc, run_benchmark
from audio_enviro_fingerprint.cli import main
from audio_enviro_fingerprint.comparison import compare_fingerprints
from audio_enviro_fingerprint.features import AnalysisCancelled
from audio_enviro_fingerprint.pipeline import analyze_file, bundle_report
from audio_enviro_fingerprint.report import verify_report, write_report


def _write_wav(path, freqs, seconds=6, rate=8000, channels=1):
    t = np.arange(rate * seconds) / rate
    mono = np.concatenate([0.2 * np.sin(2 * math.pi * f * t) for f in freqs])
    data = np.repeat(mono[:, None], channels, axis=1)
    if channels > 1:
        data[:, 1] *= -0.5
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((data * 32767).astype("<i2").tobytes())


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class PipelineReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.wav = self.dir / "a.wav"
        _write_wav(self.wav, [220, 1800, 220], channels=2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pipeline_report_verifies_and_detects_tampering(self):
        bundle = analyze_file(self.wav, channel=1, settings={"transition_threshold": 0.25})
        self.assertEqual(bundle.audio.selected_channel, 1)
        self.assertEqual(bundle.channel_summary["channel_count"], 2)
        self.assertTrue(bundle.transitions)
        self.assertTrue(bundle.recurrences)
        report = bundle_report(bundle, __version__, notes=[{"title": "n"}])
        self.assertEqual(report["analysis_settings"]["transition_threshold"], 0.25)
        target = write_report(report, self.dir / "r.json")
        self.assertTrue(verify_report(target, evidence_path=self.wav)["ok"])
        tampered = json.loads(target.read_text())
        tampered["transitions"] = []
        result = verify_report(tampered)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["report_sha256"]["ok"])
        tampered = json.loads(target.read_text())
        tampered["fingerprint"]["features"]["spectral_flatness"] += 0.1
        self.assertFalse(verify_report(tampered)["checks"]["fingerprint_sha256"]["ok"])
        other = self.dir / "b.wav"
        _write_wav(other, [440])
        self.assertFalse(verify_report(target, evidence_path=other)["checks"]["evidence_file"]["ok"])

    def test_pipeline_rejects_short_recordings_and_unknown_settings(self):
        short = self.dir / "short.wav"
        _write_wav(short, [440], seconds=1)
        with self.assertRaises(ValueError):
            analyze_file(short)
        with self.assertRaises(ValueError):
            analyze_file(self.wav, settings={"bogus": 1})

    def test_pipeline_cancellation(self):
        class Flag:
            def is_set(self):
                return True
        with self.assertRaises(AnalysisCancelled):
            analyze_file(self.wav, cancel=Flag())

    def test_comparison_contributions_and_groups(self):
        a = {"version": "aefp-1", "features": {"spectral_centroid_hz": 500.0, "frame_rms_dbfs_p90": -30.0,
                                               "band_power_db": {"0-125 Hz": -60.0}}}
        b = {"version": "aefp-1", "features": {"spectral_centroid_hz": 600.0, "frame_rms_dbfs_p90": -10.0,
                                               "band_power_db": {"0-125 Hz": -60.0}}}
        result = compare_fingerprints(a, b)
        self.assertAlmostEqual(sum(result.contributions.values()), 1.0)
        self.assertEqual(set(result.groups), {"band_power", "level", "spectral_shape"})
        self.assertAlmostEqual(result.score, math.exp(-result.distance))
        self.assertGreater(result.contributions["frame_rms_dbfs_p90"], result.contributions["spectral_centroid_hz"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.wav = self.dir / "a.wav"
        _write_wav(self.wav, [220, 1800])

    def tearDown(self):
        self.tmp.cleanup()

    def test_analyze_then_verify(self):
        out = self.dir / "r.json"
        code, _, err = _run(["analyze", str(self.wav), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("Evidence SHA-256", err)
        self.assertEqual(_run(["verify-report", str(out), "--evidence", str(self.wav)])[0], 0)
        data = json.loads(out.read_text())
        data["notes"].append({"title": "inserted"})
        out.write_text(json.dumps(data))
        self.assertEqual(_run(["verify-report", str(out)])[0], 1)

    def test_compare_json_and_errors(self):
        other = self.dir / "b.wav"
        _write_wav(other, [3000, 3000])
        code, out, _ = _run(["compare", str(self.wav), str(other), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertLess(payload["score"], 1.0)
        self.assertIn("not a location identification", payload["caveat"])
        bad = self.dir / "bad.wav"
        bad.write_bytes(b"not audio at all")
        self.assertEqual(_run(["analyze", str(bad)])[0], 2)
        self.assertEqual(_run(["analyze", str(self.wav), "--channel", "3"])[0], 2)


class BenchmarkTests(unittest.TestCase):
    def test_quick_benchmark_is_deterministic_and_sane(self):
        first = run_benchmark(seed=1, quick=True)
        second = run_benchmark(seed=1, quick=True)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertIn("not forensic validation", first["label"])
        self.assertGreater(first["comparison"]["roc_auc"], 0.5)
        self.assertGreater(first["transitions"]["at_default"]["recall"], 0.0)
        self.assertIn("NOT FORENSIC VALIDATION", format_summary(first))

    def test_metric_helpers(self):
        self.assertEqual(match_events([5.2, 9.0], [5.0, 20.0], 1.0), (1, 1, 1))
        self.assertEqual(roc_auc([2.0, 3.0], [1.0]), 1.0)
        self.assertTrue(math.isnan(roc_auc([], [1.0])))
        code, out, _ = _run(["benchmark", "--quick", "--json"])
        self.assertEqual(code, 0)
        json.loads(out)


if __name__ == "__main__":
    unittest.main()
