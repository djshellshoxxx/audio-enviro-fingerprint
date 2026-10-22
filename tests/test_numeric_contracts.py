"""Finite-result invariants across valid recordings and direct numerical APIs."""
from dataclasses import replace
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from audio_enviro_fingerprint.audio_io import load_wav
from audio_enviro_fingerprint.comparison import compare_fingerprints
from audio_enviro_fingerprint.features import analyze_audio
from audio_enviro_fingerprint.methods.hum import detect_mains_hum
from audio_enviro_fingerprint.methods.musical import (chromagram, dominant_tones, estimate_key,
    estimate_tempo, hz_to_note, note_to_hz, pitch_track)
from audio_enviro_fingerprint.methods.noise import frame_level_summary, rms_dbfs
from audio_enviro_fingerprint.methods.reverberation import estimate_t20
from audio_enviro_fingerprint.methods.spectral import describe_spectrum
from audio_enviro_fingerprint.multichannel import channel_pair_metrics
from audio_enviro_fingerprint.pipeline import analyze_file, full_report
from audio_enviro_fingerprint.recurrence import find_recurrences
from audio_enviro_fingerprint.report import verify_report, write_report
from audio_enviro_fingerprint.spectrogram import colorize, compute_spectrogram, encode_png
from audio_enviro_fingerprint.transitions import detect_transitions
from test_extended import tone, write_wav


class ContainerBoundsTests(unittest.TestCase):
    def rf64(self, riff):
        data_offset = riff.index(b'data')
        size = struct.unpack_from('<I', riff, data_offset + 4)[0]
        body = bytearray(b'WAVEds64' + struct.pack('<I', 28)
                         + struct.pack('<QQQI', len(riff) - 8 + 36, size, size // 2, 0) + riff[12:])
        struct.pack_into('<I', body, data_offset + 36 - 8 + 4, 0xFFFFFFFF)
        return bytearray(b'RF64' + struct.pack('<I', 0xFFFFFFFF) + body)

    def test_valid_riff_extensible_float_and_rf64_preserve_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'audio.wav'
            for parameters in ({}, {'float_format': True}, {'extensible': True},
                               {'float_format': True, 'extensible': True}):
                write_wav(path, tone(440, 1), **parameters)
                original = load_wav(path).samples.copy()
                if not parameters:
                    path.write_bytes(self.rf64(path.read_bytes()))
                    np.testing.assert_array_equal(load_wav(path).samples, original)
            # Non-container trailing bytes remain evidence bytes, never audio.
            write_wav(path, tone(440, 1))
            original = load_wav(path).samples.copy()
            path.write_bytes(path.read_bytes() + b'outside container')
            np.testing.assert_array_equal(load_wav(path).samples, original)

    def test_rejects_oversized_undersized_and_cross_boundary_containers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'audio.wav'
            write_wav(path, tone(440, 1))
            riff = path.read_bytes()
            for size in (3, 4, len(riff) - 9, len(riff) + 100):
                raw = bytearray(riff)
                struct.pack_into('<I', raw, 4, size)
                path.write_bytes(raw)
                with self.subTest(format='RIFF', size=size), self.assertRaises(ValueError):
                    load_wav(path)
            valid_rf64 = self.rf64(riff)
            for size in (4, len(valid_rf64) - 9, len(valid_rf64) + 100):
                raw = bytearray(valid_rf64)
                struct.pack_into('<Q', raw, 20, size)
                path.write_bytes(raw)
                with self.subTest(format='RF64', size=size), self.assertRaises(ValueError):
                    load_wav(path)

    def test_rejects_incomplete_rf64_tables_and_extensible_extensions(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'audio.wav'
            write_wav(path, tone(440, 1))
            raw = self.rf64(path.read_bytes())
            struct.pack_into('<I', raw, 44, 1)  # Size table claims an absent entry.
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_wav(path)
            write_wav(path, tone(440, 1), extensible=True)
            raw = bytearray(path.read_bytes())
            struct.pack_into('<H', raw, 36, 100)  # Extension exceeds the fmt chunk.
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_wav(path)


class FiniteAnalysisTests(unittest.TestCase):
    def test_every_report_section_is_finite_for_silence_and_tones_across_rates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for rate in (8000, 16000, 44100, 48000, 96000, 192000):
                t = np.arange(int(rate * 2.1)) / rate
                signal = (0.1 * np.sin(2 * np.pi * 50 * t)
                          + 0.05 * np.sin(2 * np.pi * 100 * t)
                          + 0.03 * np.sin(2 * np.pi * 150 * t)
                          + 0.1 * np.sin(2 * np.pi * 440 * t))
                for name, samples in [('silence', np.zeros_like(t)), ('tones', signal)]:
                    with self.subTest(rate=rate, signal=name):
                        source = root / f'{rate}-{name}.wav'
                        stereo = np.stack((samples, 0.5 * samples), axis=1)
                        write_wav(source, stereo.reshape(-1), sr=rate, channels=2, float_format=True)
                        report = full_report(analyze_file(source))
                        json.dumps(report, allow_nan=False)
                        self.assertEqual(report['sections']['audio']['sample_rate'], rate)
                        self.assertEqual(report['sections']['channels']['channel_count'], 2)
                        hum = report['sections']['mains_hum']
                        self.assertLessEqual(hum['frequency_resolution_hz'], 1)
                        if name == 'silence':
                            self.assertFalse(hum['detected'])
                        target = root / 'report.json'
                        write_report(target, report)
                        self.assertTrue(verify_report(target)['evidence_ok'])

    def test_direct_methods_reject_nonfinite_or_nonmono_audio(self):
        methods = [analyze_audio, describe_spectrum, detect_mains_hum, chromagram,
                   dominant_tones, pitch_track, estimate_tempo, compute_spectrogram, estimate_t20]
        for method in methods:
            for samples in (np.array([0, float('nan')]), np.array([0, float('inf')]),
                            np.zeros((2, 2)), np.array([1 + 2j])):
                with self.subTest(method=method.__name__, samples=samples), self.assertRaises(ValueError):
                    method(samples, 8000)
            for rate in (0, -1, float('nan'), 8000.5, True):
                with self.subTest(method=method.__name__, rate=rate), self.assertRaises(ValueError):
                    method(np.zeros(16), rate)
        for method in (rms_dbfs, frame_level_summary):
            with self.assertRaises(ValueError):
                method([float('nan')])
        with self.assertRaises(ValueError):
            channel_pair_metrics(np.array([]), np.array([]), 8000)
        with self.assertRaises(ValueError):
            estimate_key(np.full((2, 12), float('nan')))

    def test_comparisons_reject_nonfinite_and_unknown_versions(self):
        first = {'version': 'aefp-2', 'features': {'spectral_centroid_hz': 500}}
        for value in (float('nan'), float('inf'), -float('inf')):
            for features in ({'spectral_centroid_hz': value}, {'band_power_db': {'0-125 Hz': value}}):
                with self.subTest(features=features), self.assertRaises(ValueError):
                    compare_fingerprints(first, {'version': 'aefp-2', 'features': features})
        with self.assertRaises(ValueError):
            compare_fingerprints({'version': 'unknown'}, {'version': 'unknown'})
        for version in ('aefp-1', 'aefp-2'):
            fingerprint = {'version': version, 'features': {'spectral_centroid_hz': 500}}
            self.assertEqual(compare_fingerprints(fingerprint, fingerprint).score, 1)

    def test_invalid_frame_vectors_fail_before_transition_or_recurrence_results(self):
        analysis = analyze_audio(np.zeros(24000), 8000, frame_seconds=1, hop_seconds=1)
        for field in ('rms_dbfs', 'spectral_centroid_hz', 'start_seconds'):
            invalid = replace(analysis, frames=[replace(analysis.frames[0], **{field: float('nan')}),
                                                *analysis.frames[1:]])
            for method in (find_recurrences, detect_transitions):
                with self.subTest(field=field, method=method.__name__), self.assertRaises(ValueError):
                    method(invalid)

    def test_small_windows_and_invalid_image_note_parameters(self):
        json.dumps(describe_spectrum(np.array([0, 1]), 8000), allow_nan=False)
        for method in (lambda: hz_to_note(440, 0), lambda: note_to_hz(69, float('nan')),
                       lambda: colorize(np.full((2, 2), float('nan'))),
                       lambda: encode_png(np.zeros((2, 2, 4), dtype=np.uint8))):
            with self.assertRaises(ValueError):
                method()
        self.assertEqual(compute_spectrogram(np.zeros(4096), 8000, max_columns=1)["db"].shape[1], 1)
        short = detect_mains_hum(np.zeros(32768), 192000)
        self.assertFalse(short['detected'])
        self.assertIn('reason', short)
