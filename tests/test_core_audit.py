"""Regressions for core audit findings CORE-01 through CORE-03."""
import hashlib
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from audio_enviro_fingerprint.audio_io import _parse_riff, load_wav
from audio_enviro_fingerprint.integrity import sha256_file
from audio_enviro_fingerprint.pipeline import analyze_file
from test_extended import write_wav


def rf64_with_table(entries, chunks):
    fmt = b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, 8000, 16000, 2, 16)
    data = b'data' + struct.pack('<I', 0xffffffff) + bytes(8)
    table = b''.join(struct.pack('<4sQ', cid, size) for cid, size in entries)
    ancillary = b''.join(cid + struct.pack('<I', 0xffffffff) + payload + bytes(len(payload) % 2)
                         for cid, payload in chunks)
    body_size = 4 + 36 + len(table) + len(fmt) + len(ancillary) + len(data)
    ds64 = b'ds64' + struct.pack('<IQQQI', 28 + len(table), body_size, 8, 4, len(entries)) + table
    return b'RF64' + struct.pack('<I', 0xffffffff) + b'WAVE' + ds64 + fmt + ancillary + data


class CoreAuditTests(unittest.TestCase):
    def test_invalid_hash_chunks_rejected_before_open(self):
        for chunk_size in (0, -1, True, False, 1.5, None):
            with self.subTest(chunk_size=chunk_size), patch.object(Path, 'open', side_effect=AssertionError('opened')):
                with self.assertRaises(ValueError):
                    sha256_file('not-opened', chunk_size)

    def test_positive_hash_chunks_preserve_exact_evidence_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence'
            data = bytes(range(256)) * 17
            path.write_bytes(data)
            for chunk_size in (1, 7, 1024 * 1024):
                self.assertEqual(sha256_file(path, chunk_size), hashlib.sha256(data).hexdigest())

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX named pipe regression')
    def test_nonregular_input_fails_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pipe.wav'
            os.mkfifo(path)
            code = '''
import sys
from audio_enviro_fingerprint.integrity import sha256_file
from audio_enviro_fingerprint.pipeline import analyze_file
from audio_enviro_fingerprint.audio_io import load_audio, load_wav
for operation in (sha256_file, analyze_file, load_audio, load_wav):
    try:
        operation(sys.argv[1])
    except ValueError:
        pass
    else:
        raise AssertionError('nonregular input accepted')
'''
            try:
                result = subprocess.run([sys.executable, '-c', code, str(path)],
                                        capture_output=True, text=True, timeout=3)
            except subprocess.TimeoutExpired:
                self.fail('nonregular source blocked before rejection')
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_regular_input_pipeline_still_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, np.zeros(24000), sr=8000)
            self.assertEqual(analyze_file(path, musical=False)['sha256'], sha256_file(path))

    def test_rf64_ancillary_table_and_repeated_ids(self):
        raw = rf64_with_table([(b'JUNK', 3), (b'JUNK', 6)],
                              [(b'JUNK', b'abc'), (b'JUNK', b'123456')])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'table.wav'
            path.write_bytes(raw)
            audio = load_wav(path)
            self.assertEqual(len(audio.samples), 4)
            np.testing.assert_array_equal(audio.samples, np.zeros(4))

    def test_rf64_missing_or_mismatched_size_entry_rejected(self):
        for entries in ([], [(b'LIST', 4)], [(b'JUNK', 10000)]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                _parse_riff(io.BytesIO(rf64_with_table(entries, [(b'JUNK', b'abcd')])), 1024)

    def test_rf64_table_reads_are_bounded(self):
        entries = [(b'JUNK', 2)] * 100
        raw = rf64_with_table(entries, [(b'JUNK', b'00')] * len(entries))

        class BoundedReads(io.BytesIO):
            def read(self, size=-1):
                if not 0 <= size <= 40:
                    raise AssertionError('unbounded metadata read')
                return super().read(size)

        _, payload, declared = _parse_riff(BoundedReads(raw), 1024)
        self.assertEqual((payload, declared), (bytes(8), 8))

    def test_pipeline_returns_verified_source_stat(self):
        from audio_enviro_fingerprint import integrity
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, np.zeros(24000), sr=8000)
            result = analyze_file(path, musical=False)
            self.assertEqual(result['source_stat'], integrity.evidence_stat(path))
            self.assertEqual(len(result['source_stat']), 5)

    def test_pipeline_rejects_same_bytes_replaced_during_final_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, np.zeros(24000), sr=8000)
            original = path.read_bytes()
            calls = 0

            def replace_after_hash(source, **kwargs):
                nonlocal calls
                digest = sha256_file(source, **kwargs)
                calls += 1
                if calls == 2:
                    replacement = path.with_suffix('.replacement')
                    replacement.write_bytes(original)
                    replacement.replace(path)
                return digest

            with patch('audio_enviro_fingerprint.pipeline.sha256_file', side_effect=replace_after_hash):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    analyze_file(path, musical=False)
