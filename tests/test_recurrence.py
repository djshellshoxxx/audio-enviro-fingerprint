import math
import unittest

import numpy as np

from audio_enviro_fingerprint.features import analyze_audio
from audio_enviro_fingerprint.recurrence import find_recurrences, segment_analysis


def _tone(freq, seconds, rate=8000):
    t = np.arange(rate * seconds) / rate
    return 0.15 * np.sin(2 * math.pi * freq * t)


class RecurrenceTests(unittest.TestCase):
    def _segments(self, freqs, recording_id="rec"):
        samples = np.concatenate([_tone(f, 5) for f in freqs])
        analysis = analyze_audio(samples, 8000, frame_seconds=1, hop_seconds=1)
        return segment_analysis(analysis, recording_id, transition_threshold=0.25,
                                minimum_separation_seconds=1)

    def test_detects_environment_that_leaves_and_returns(self):
        segments = self._segments([220, 1800, 220])
        self.assertEqual(len(segments), 3)
        matches = find_recurrences(segments)
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual((match.first.segment_id, match.second.segment_id), ("rec#1", "rec#3"))
        self.assertLess(match.distance, 0.05)
        self.assertIn("rms_dbfs", match.differences)
        self.assertIn("not an identification conclusion", match.explanation)

    def test_negative_control_has_no_recurrence(self):
        self.assertEqual(find_recurrences(self._segments([220, 1800, 3200])), [])

    def test_matches_across_recordings(self):
        segments = self._segments([220, 1800], "a") + self._segments([3200, 1800], "b")
        pairs = {(m.first.segment_id, m.second.segment_id) for m in find_recurrences(segments)}
        self.assertEqual(pairs, {("a#2", "b#2")})

    def test_rejects_invalid_threshold(self):
        with self.assertRaises(ValueError):
            find_recurrences([], max_distance=float("nan"))


if __name__ == "__main__":
    unittest.main()
