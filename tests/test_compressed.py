import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from audio_enviro_fingerprint.audio_io import load_audio
from audio_enviro_fingerprint.pipeline import analyze_file, full_report
from test_extended import tone, write_wav


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg tools not installed')
class CompressedAudioTests(unittest.TestCase):
    def test_lossless_stereo_decode_and_source_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, encoded = Path(tmp) / 'source.wav', Path(tmp) / 'audio.flac'
            write_wav(source, np.stack([tone(440, 3), -tone(440, 3)], axis=1), channels=2)
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), str(encoded)], check=True)
            before = encoded.read_bytes()
            audio = load_audio(encoded)
            self.assertEqual((audio.sample_rate, audio.channels), (16000, 2))
            self.assertTrue(np.allclose(audio.channel(0), -audio.channel(1)))
            self.assertEqual(audio.decoder['codec'], 'flac')
            self.assertIn('ffmpeg version', audio.decoder['version'])
            report = full_report(analyze_file(encoded, musical=False))
            self.assertEqual(report['evidence']['sha256'], hashlib.sha256(before).hexdigest())
            self.assertEqual(report['sections']['audio']['decoder']['codec'], 'flac')
            self.assertEqual(encoded.read_bytes(), before)

    def test_decode_limit_fails_instead_of_returning_truncated_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, encoded = Path(tmp) / 'source.wav', Path(tmp) / 'audio.flac'
            write_wav(source, tone(440, 3))
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), str(encoded)], check=True)
            with self.assertRaisesRegex(ValueError, 'limit'):
                load_audio(encoded, max_decoded_bytes=1024)

    def test_mp3_decode_keeps_channels_and_records_codec(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, encoded = Path(tmp) / 'source.wav', Path(tmp) / 'audio.mp3'
            write_wav(source, tone(440, 3))
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), str(encoded)], check=True)
            audio = load_audio(encoded)
            self.assertEqual(audio.decoder['codec'], 'mp3')
            self.assertEqual(audio.channels, 1)
            self.assertAlmostEqual(audio.duration_seconds, 3, delta=0.1)
