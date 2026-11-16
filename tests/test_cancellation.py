import tempfile
import threading
import unittest
from pathlib import Path

from audio_enviro_fingerprint.control import AnalysisCancelled
from audio_enviro_fingerprint.features import analyze_audio
from audio_enviro_fingerprint.pipeline import analyze_file
from test_extended import tone, write_wav


class CancellationTests(unittest.TestCase):
    def test_cancel_before_start_does_not_open_file(self):
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(AnalysisCancelled):
            analyze_file('nonexistent.wav', cancel_event=cancelled)

    def test_cancel_between_stages_publishes_no_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.wav'
            write_wav(path, tone(440, 3))
            cancelled = threading.Event()

            def progress(message, fraction):
                if fraction >= 0.35:
                    cancelled.set()

            with self.assertRaises(AnalysisCancelled):
                analyze_file(path, progress=progress, cancel_event=cancelled)
            self.assertTrue(path.is_file())

    def test_frame_loop_checks_cancellation(self):
        with self.assertRaises(AnalysisCancelled):
            analyze_audio(tone(440, 3), 16000, should_cancel=lambda: True)
