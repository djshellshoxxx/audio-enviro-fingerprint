import struct
import tempfile
import unittest
from pathlib import Path

from audio_enviro_fingerprint.audio_io import load_wav
from test_extended import write_wav, tone


class InputHardeningTests(unittest.TestCase):
    def test_rejects_forged_extensible_subtype(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'x.wav'
            write_wav(p, tone(440, 1), extensible=True)
            raw = bytearray(p.read_bytes())
            raw[59] ^= 1  # GUID tail must match the standard audio subtype namespace.
            p.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_wav(p)

    def test_rejects_inconsistent_block_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'x.wav'
            write_wav(p, tone(440, 1))
            raw = bytearray(p.read_bytes())
            struct.pack_into('<H', raw, 32, 7)
            p.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_wav(p)

    def test_truncated_rf64_metadata_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'x.wav'
            p.write_bytes(b'RF64' + struct.pack('<I', 0xffffffff) + b'WAVEds64' + struct.pack('<I', 28) + b'x')
            with self.assertRaises(ValueError):
                load_wav(p)

class VerificationHardeningTests(unittest.TestCase):
    def test_verify_rejects_unsupported_algorithm(self):
        from audio_enviro_fingerprint.report import build_report, verify_report, write_report
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'r.json'
            source = Path(tmp) / 'source.wav'
            source.write_bytes(b'evidence')
            from audio_enviro_fingerprint.integrity import sha256_file
            report = build_report(source, sha256_file(source), {})
            report['manifest']['algorithm'] = 'unsupported'
            write_report(p, report)
            self.assertFalse(verify_report(p)['manifest_ok'])

    def test_malformed_report_returns_cli_input_error(self):
        from audio_enviro_fingerprint.cli import run
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'r.json'
            p.write_text('[]')
            self.assertEqual(run(['verify', str(p)]), 1)

class RecurrenceValidationTests(unittest.TestCase):
    def test_rejects_nonfinite_parameters(self):
        from audio_enviro_fingerprint.features import analyze_audio
        from audio_enviro_fingerprint.recurrence import find_recurrences
        analysis = analyze_audio(tone(440, 1), 16000)
        for kwargs in ({'threshold': float('nan')}, {'departure': float('inf')},
                       {'min_gap_seconds': float('nan')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                find_recurrences(analysis, **kwargs)

class RecurrenceMemoryTests(unittest.TestCase):
    def test_search_never_builds_all_pairs_matrix(self):
        from unittest.mock import patch
        import numpy as np
        from audio_enviro_fingerprint.features import analyze_audio
        from audio_enviro_fingerprint import recurrence
        rng = np.random.default_rng(42)
        room = rng.normal(0, 0.02, 16000 * 10)
        analysis = analyze_audio(np.concatenate([room, tone(1500, 10), room]), 16000)
        original = recurrence._distances

        def bounded(a, b):
            self.assertTrue(len(a) <= 1 or len(b) <= 1,
                            'recurrence allocated a quadratic all-pairs distance matrix')
            return original(a, b)

        with patch.object(recurrence, '_distances', side_effect=bounded):
            matches = recurrence.find_recurrences(analysis)
            cross = recurrence.find_recurrences(analysis, analysis)
        self.assertTrue(matches)
        self.assertTrue(cross)

class EvidenceExportTests(unittest.TestCase):
    def test_report_cannot_overwrite_original_or_hardlink(self):
        import hashlib
        import os
        from audio_enviro_fingerprint.report import build_report, write_report
        with tempfile.TemporaryDirectory() as tmp:
            src, alias = Path(tmp) / 'evidence.wav', Path(tmp) / 'alias.json'
            src.write_bytes(b'original evidence')
            os.link(src, alias)
            report = build_report(src, hashlib.sha256(src.read_bytes()).hexdigest(), {})
            for output in (src, alias):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    write_report(output, report)
            self.assertEqual(src.read_bytes(), b'original evidence')

    def test_spectrogram_cannot_overwrite_original(self):
        from audio_enviro_fingerprint.cli import run
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'evidence.wav'
            write_wav(src, tone(440, 3))
            original = src.read_bytes()
            self.assertEqual(run(['spectrogram', str(src), str(src)]), 1)
            self.assertEqual(src.read_bytes(), original)
