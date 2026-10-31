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
            self.assertEqual(result['recurrence_parameters'], {
                'method': 'recurrence-v1', 'threshold': 0.25,
                'departure': 0.6, 'min_gap_seconds': 6.0})
            history = [{'marker_key': 1, 'revision': 1, 'timestamp_seconds': 1.0},
                       {'marker_key': 1, 'revision': 2, 'timestamp_seconds': 2.0}]
            references = [{'evidence_sha256': result['sha256'], 'metadata': {'location_id': 'Room A'}}]
            recurrence_history = [{'evidence_id': 1, 'parameters': {'threshold': 0.25},
                                   'findings': [item.to_dict() for item in result['recurrences']]}]
            report = full_report(result, markers=[history[-1]], marker_history=history, references=references,
                                 recurrence_history=recurrence_history)
            self.assertEqual(report['sections']['recurrence_history'], recurrence_history)
            self.assertEqual(report['sections']['recurrences']['parameters'], result['recurrence_parameters'])
            self.assertEqual(report['sections']['marker_history'], history)
            self.assertEqual(report['sections']['references'], references)
            self.assertEqual(report['sections']['markers'], [history[-1]])
