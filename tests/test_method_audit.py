"""Regression checks for numerical software contracts found by AEF-101."""
from dataclasses import replace
import unittest

import numpy as np

from audio_enviro_fingerprint.features import AnalysisResult, FrameFeature, analyze_audio
from audio_enviro_fingerprint.fingerprint import make_fingerprint
from audio_enviro_fingerprint.methods.musical import estimate_tempo, pitch_track
from audio_enviro_fingerprint.multichannel import channel_pair_metrics
from audio_enviro_fingerprint.recurrence import find_recurrences
from audio_enviro_fingerprint.transitions import detect_transitions


class MethodAuditTests(unittest.TestCase):
    def test_tempo_respects_fractional_lag_bpm_bounds(self):
        samples = np.zeros(8000 * 8)
        samples[::2048] = 1
        result = estimate_tempo(samples, 8000, bpm_min=150, bpm_max=220)
        if result['bpm'] is not None:
            self.assertGreaterEqual(result['bpm'], 150)
            self.assertLessEqual(result['bpm'], 220)
        self.assertIsNone(estimate_tempo(samples, 8000, bpm_min=211, bpm_max=212)['bpm'])
        self.assertEqual(estimate_tempo(samples, 8000, bpm_min=233, bpm_max=235)['bpm'], 234.375)

    def test_pitch_respects_frequency_limits_at_interpolated_boundaries(self):
        for hz in (60, 61, 440, 999, 1000):
            with self.subTest(hz=hz):
                samples = .1 * np.sin(2 * np.pi * hz * np.arange(8000) / 8000)
                track = pitch_track(samples, 8000)
                self.assertTrue(track)
                for item in track:
                    if item['f0_hz'] is not None:
                        self.assertGreaterEqual(item['f0_hz'], 60)
                        self.assertLessEqual(item['f0_hz'], 1000)
                if hz == 440:
                    voiced = [item['f0_hz'] for item in track if item['f0_hz'] is not None]
                    self.assertTrue(voiced)
                    self.assertAlmostEqual(float(np.median(voiced)), 440, delta=2)

    def test_no_lag_measurement_for_silent_or_dc_channels(self):
        tone = np.sin(2 * np.pi * 440 * np.arange(8000) / 8000)
        for first, second in ((np.zeros(8000), np.zeros(8000)),
                              (np.zeros(8000), tone), (np.ones(8000), tone)):
            with self.subTest(first_peak=float(first.max()), second_peak=float(second.max())):
                metrics = channel_pair_metrics(first, second, 8000)
                self.assertIsNone(metrics['peak_lag_samples'])
                self.assertIsNone(metrics['peak_lag_ms'])
                self.assertFalse(metrics['lag_available'])
        rng = np.random.default_rng(4)
        first = rng.normal(size=8000)
        metrics = channel_pair_metrics(first, np.roll(first, 8), 8000)
        self.assertTrue(metrics['lag_available'])
        self.assertEqual(metrics['peak_lag_samples'], -8)

    def test_valid_fingerprint_canonical_bytes_stay_at_existing_version(self):
        fingerprint = make_fingerprint(analyze_audio(np.zeros(24000), 8000))
        self.assertEqual(fingerprint.version, 'aefp-2')
        self.assertEqual(fingerprint.fingerprint_hash,
                         '9eda720dcdce44a12a5e576842d771ca37919a2a5cb8edb570c05fb1ffb12a2d')

    def test_fingerprints_reject_invalid_direct_analysis_records(self):
        analysis = analyze_audio(np.zeros(24000), 8000)
        invalid = [replace(analysis, sample_rate=-1), replace(analysis, sample_rate=1.5),
                   replace(analysis, duration_seconds=-1), replace(analysis, frame_seconds=0),
                   replace(analysis, hop_seconds=float('nan')),
                   replace(analysis, noise={}),
                   replace(analysis, noise={'frame_rms_dbfs_p10': float('nan')}),
                   replace(analysis, frames=[replace(analysis.frames[0], start_seconds=4)]),
                   replace(analysis, frames=[analysis.frames[0],
                                            replace(analysis.frames[1], band_power_db={})])]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                make_fingerprint(item)

    def test_recurrence_chooses_reference_satisfying_departure(self):
        frames = [FrameFeature(t, level, 100, .1, {})
                  for t, level in enumerate([-20, -100, -21, -21])]
        analysis = AnalysisResult(10, 4, .2, 1, frames, {})
        matches = find_recurrences(analysis, min_gap_seconds=0)
        self.assertEqual(len(matches), 1)
        self.assertAlmostEqual(matches[0].later_start_s, 2)
        self.assertAlmostEqual(matches[0].later_end_s, 3.2)
        self.assertGreater(matches[0].departure_peak, .6)
        # Without departure the same near references cannot produce a return.
        flat = replace(analysis, frames=[replace(frame, rms_dbfs=-20) for frame in frames])
        self.assertEqual(find_recurrences(flat, min_gap_seconds=0), [])
        # Cross-recording matching still has no departure condition.
        self.assertTrue(find_recurrences(flat, flat))

    def test_frame_consumers_reject_invalid_sample_clocks_and_outside_frames(self):
        analysis = analyze_audio(np.zeros(24000), 8000)
        for invalid in (replace(analysis, sample_rate=0),
                        replace(analysis, sample_rate=8000.5),
                        replace(analysis, duration_seconds=.5)):
            for method in (make_fingerprint, find_recurrences, detect_transitions):
                with self.subTest(method=method.__name__, invalid=invalid), self.assertRaises(ValueError):
                    method(invalid)
