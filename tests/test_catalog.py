import tempfile
import unittest
from pathlib import Path

from audio_enviro_fingerprint.catalog import cluster_recordings
from test_extended import tone, write_wav


class CatalogTests(unittest.TestCase):
    def test_groups_matching_descriptors_and_exposes_pair_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / name for name in ('a.wav', 'b.wav', 'c.wav')]
            for path, frequency in zip(paths, (440, 440, 1500)):
                write_wav(path, tone(frequency, 3))
            result = cluster_recordings(paths, max_distance=0.05)
            self.assertEqual(result['groups'], [[0, 1], [2]])
            self.assertEqual(len(result['comparisons']), 3)
            self.assertTrue(result['comparisons'][0]['differences'])
            self.assertTrue(all(len(item['sha256']) == 64 for item in result['recordings']))
            shuffled = cluster_recordings(paths[::-1], max_distance=0.05)
            self.assertEqual(result, shuffled)

    def test_rejects_invalid_threshold_and_duplicate_path(self):
        for threshold in (float('nan'), -0.1, 1.1):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                cluster_recordings([], max_distance=threshold)
        with self.assertRaises(ValueError):
            cluster_recordings([])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.wav'
            write_wav(path, tone(440, 3))
            with self.assertRaises(ValueError):
                cluster_recordings([path, path])

class ComparisonSymmetryTests(unittest.TestCase):
    def test_distance_does_not_depend_on_recording_order(self):
        from audio_enviro_fingerprint.comparison import compare_fingerprints
        a = {'spectral_centroid_hz': 200.0, 'median_rms_dbfs': -20.0}
        b = {'spectral_centroid_hz': 2000.0, 'median_rms_dbfs': -20.0}
        self.assertEqual(compare_fingerprints(a, b).score, compare_fingerprints(b, a).score)
