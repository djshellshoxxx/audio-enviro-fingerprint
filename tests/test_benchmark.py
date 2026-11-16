import json
import unittest

from audio_enviro_fingerprint.benchmark import run_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_quick_benchmark_is_reproducible_and_serializable(self):
        first = run_benchmark(seed=1, quick=True)
        second = run_benchmark(seed=1, quick=True)
        self.assertEqual(first, second)
        json.dumps(first, allow_nan=False)
        self.assertEqual(first['benchmark_version'], 'aefp-bench-2')
        self.assertIn('not forensic validation', first['label'])
        self.assertEqual(len(first['recurrence']['threshold_sweep']), 5)
        self.assertGreater(first['comparison']['same_room_pairs']['n'], 0)
