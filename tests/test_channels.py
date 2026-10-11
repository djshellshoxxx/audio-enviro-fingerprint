import math
import unittest

import numpy as np

from audio_enviro_fingerprint.methods.channels import describe_channels


class DescribeChannelsTests(unittest.TestCase):
    def test_stereo_inverted_channel(self):
        t = np.arange(8000) / 8000
        left = 0.5 * np.sin(2 * math.pi * 200 * t)
        result = describe_channels(np.column_stack([left, -0.5 * left]), 8000)
        self.assertEqual(result["channel_count"], 2)
        self.assertAlmostEqual(result["correlation"][0][1], -1.0, places=9)
        self.assertEqual(result["correlation"][0][0], 1.0)
        self.assertAlmostEqual(result["level_difference_db"]["1-2"], 20 * math.log10(2), places=6)
        self.assertAlmostEqual(result["per_channel"][0]["peak_dbfs"], 20 * math.log10(0.5), places=3)
        self.assertAlmostEqual(result["per_channel"][1]["dc_offset"], 0.0, places=9)
        self.assertTrue(any("cancel" in note for note in result["notes"]))
        self.assertTrue(any("do not localize" in note for note in result["notes"]))

    def test_mono_accepts_one_dimensional(self):
        result = describe_channels(np.full(100, 0.25), 8000)
        self.assertEqual(result["channel_count"], 1)
        self.assertEqual(result["level_difference_db"], {})
        self.assertEqual(result["correlation"], [[0.0]])
        self.assertAlmostEqual(result["per_channel"][0]["dc_offset"], 0.25)
        self.assertTrue(any("Mono" in note for note in result["notes"]))

    def test_silent_channel_has_no_nan(self):
        rng = np.random.default_rng(0)
        data = np.column_stack([0.1 * rng.standard_normal(1000), np.zeros(1000), 0.1 * rng.standard_normal(1000)])
        result = describe_channels(data, 8000)
        matrix = np.asarray(result["correlation"])
        self.assertTrue(np.all(np.isfinite(matrix)))
        self.assertTrue(np.all(matrix[1] == 0.0))
        self.assertTrue(np.allclose(matrix, matrix.T))
        self.assertEqual(set(result["level_difference_db"]), {"1-2", "1-3", "2-3"})
        self.assertTrue(all(math.isfinite(v) for v in result["level_difference_db"].values()))
        self.assertEqual(result["per_channel"][1]["rms_dbfs"], -240.0)
        self.assertTrue(any("undefined" in note for note in result["notes"]))

    def test_rejects_bad_input(self):
        for data, rate in ((np.zeros((0, 2)), 8000), (np.zeros((4, 2)), 0),
                           (np.array([[np.nan, 0.0]]), 8000), (np.zeros((2, 2, 2)), 8000)):
            with self.assertRaises(ValueError):
                describe_channels(data, rate)


if __name__ == "__main__":
    unittest.main()
