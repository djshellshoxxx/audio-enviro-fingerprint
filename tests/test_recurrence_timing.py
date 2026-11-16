"""Recurrence ranges and gap limits follow measured frame timestamps."""
from dataclasses import replace
import unittest

import numpy as np

from audio_enviro_fingerprint.features import AnalysisResult, FrameFeature, analyze_audio
from audio_enviro_fingerprint.recurrence import find_recurrences


class RecurrenceTimingTests(unittest.TestCase):
    def test_cross_recording_uses_each_recordings_frame_timestamps(self):
        frame = FrameFeature(0.0, -20.0, 100.0, 0.1, {})
        query = AnalysisResult(10, 3.0, 0.2, 0.14,
                               [replace(frame, start_seconds=1.0),
                                replace(frame, start_seconds=1.1)], {})
        reference = replace(query, frames=[replace(frame, start_seconds=2.0)])
        match, = find_recurrences(query, reference)
        self.assertAlmostEqual(match.later_start_s, 1.0)
        self.assertAlmostEqual(match.later_end_s, 1.3)
        self.assertAlmostEqual(match.earlier_start_s, 2.0)
        self.assertAlmostEqual(match.earlier_end_s, 2.2)

    def test_cross_recording_range_uses_sample_quantized_frame_duration(self):
        analysis = analyze_audio(np.zeros(10), 10, frame_seconds=0.24, hop_seconds=0.14)
        match, = find_recurrences(analysis, analysis)
        self.assertAlmostEqual(match.later_end_s, analysis.duration_seconds)
        self.assertAlmostEqual(match.earlier_end_s, 0.2)

    def test_minimum_gap_uses_elapsed_time_rather_than_requested_hop(self):
        first = FrameFeature(0.0, -20.0, 100.0, 0.1, {})
        for actual_hop, requested_hop, gap, expected in (
                (0.1, 0.14, 0.25, False), (0.2, 0.15, 0.35, True)):
            analysis = AnalysisResult(10, 1.0, 0.2, requested_hop,
                                      [first, replace(first, start_seconds=actual_hop, rms_dbfs=-100.0),
                                       replace(first, start_seconds=2 * actual_hop)], {})
            with self.subTest(actual_hop=actual_hop):
                self.assertEqual(bool(find_recurrences(analysis, min_gap_seconds=gap)), expected)

    def test_exact_gap_boundary_survives_floating_point_subtraction(self):
        first = FrameFeature(0.1, -20.0, 100.0, 0.1, {})
        analysis = AnalysisResult(10, 1.0, 0.2, 0.1,
                                  [first, replace(first, start_seconds=0.2, rms_dbfs=-100.0),
                                   replace(first, start_seconds=0.3)], {})
        matches = find_recurrences(analysis, min_gap_seconds=0.2)
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertAlmostEqual(match.earlier_start_s, 0.1)
        self.assertAlmostEqual(match.later_start_s, 0.3)
        # A genuinely shorter gap must remain ineligible.
        self.assertEqual(find_recurrences(analysis, min_gap_seconds=0.200001), [])
