import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from audio_enviro_fingerprint.audio_io import _parse_riff, load_audio, load_wav
from test_extended import write_wav


class WavLimitTests(unittest.TestCase):
    def test_limit_counts_float64_samples_across_all_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            for floating in (False, True):
                for channels in (1, 2):
                    with self.subTest(floating=floating, channels=channels):
                        write_wav(path, np.zeros(20 * channels), channels=channels,
                                  float_format=floating)
                        required = 20 * channels * 8
                        self.assertEqual(load_audio(path, required).all_channels.nbytes, required)
                        with self.assertRaisesRegex(ValueError, 'memory limit'):
                            load_audio(path, required - 1)

    def test_oversized_input_rejected_before_payload_read_or_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, np.zeros(100))
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('unbounded read')):
                with patch('audio_enviro_fingerprint.audio_io._decode_pcm',
                           side_effect=AssertionError('allocated audio')):
                    with self.assertRaisesRegex(ValueError, 'memory limit'):
                        load_audio(path, 8)

    def test_native_loader_limit_and_skipped_ancillary_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, np.zeros(10))
            raw = path.read_bytes()
            junk = b'JUNK' + struct.pack('<I', 4096) + bytes(4096)
            body = raw[8:12] + junk + raw[12:]
            path.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('unbounded read')):
                self.assertEqual(load_wav(path, 80).all_channels.nbytes, 80)
                with self.assertRaisesRegex(ValueError, 'memory limit'):
                    load_wav(path, 79)

    def test_invalid_native_limits(self):
        for value in (0, -1, 1.5, None, True, False):
            for loader in (load_wav, load_audio):
                with self.subTest(value=value, loader=loader), self.assertRaises(ValueError):
                    loader('unused.wav', value)

    def test_oversized_payload_is_never_read(self):
        import io
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, np.zeros(100))

            class BoundedReads(io.BytesIO):
                def read(self, size=-1):
                    if not 0 <= size <= 40:
                        raise AssertionError('attempted payload or unbounded read')
                    return super().read(size)

            with self.assertRaisesRegex(ValueError, 'memory limit'):
                _parse_riff(BoundedReads(path.read_bytes()), 8)

    def test_rf64_declared_payload_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, np.zeros(10))
            raw = path.read_bytes()
            fmt_chunk = raw[12:36]
            data = b'data' + struct.pack('<I', 0xffffffff) + raw[44:]
            body_size = 4 + 36 + len(fmt_chunk) + len(data)
            ds64 = b'ds64' + struct.pack('<IQQQI', 28, body_size, 20, 10, 0)
            path.write_bytes(b'RF64' + struct.pack('<I', 0xffffffff) + b'WAVE' + ds64 + fmt_chunk + data)
            self.assertEqual(load_audio(path, 80).all_channels.nbytes, 80)
            with self.assertRaisesRegex(ValueError, 'memory limit'):
                load_audio(path, 79)
