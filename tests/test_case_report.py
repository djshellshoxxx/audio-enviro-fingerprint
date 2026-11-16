import tempfile
import unittest
from pathlib import Path

from audio_enviro_fingerprint.pipeline import analyze_file, full_report
from test_extended import tone, write_wav


class CaseReportTests(unittest.TestCase):
    def test_report_preserves_references_and_marker_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            write_wav(path, tone(440, 3))
            result = analyze_file(path, musical=False)
            history = [{'marker_key': 1, 'revision': 1, 'timestamp_seconds': 1.0},
                       {'marker_key': 1, 'revision': 2, 'timestamp_seconds': 2.0}]
            references = [{'evidence_sha256': result['sha256'], 'metadata': {'location_id': 'Room A'}}]
            report = full_report(result, markers=[history[-1]], marker_history=history, references=references)
            self.assertEqual(report['sections']['marker_history'], history)
            self.assertEqual(report['sections']['references'], references)
            self.assertEqual(report['sections']['markers'], [history[-1]])
