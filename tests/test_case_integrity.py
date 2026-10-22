import tempfile
import unittest
from pathlib import Path

from audio_enviro_fingerprint.case_store import CaseStore


class CaseIntegrityTests(unittest.TestCase):
    def test_marker_revision_cannot_move_to_another_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.wav', Path(tmp) / 'b.wav'
            a.write_bytes(b'a')
            b.write_bytes(b'b')
            with CaseStore(Path(tmp) / 'case.db') as store:
                first, second = store.register_evidence(a), store.register_evidence(b)
                key = store.save_marker(first, 1.0, 'first')
                with self.assertRaises(ValueError):
                    store.save_marker(second, 2.0, 'moved', key)
                self.assertEqual(store.markers_for(second, True), [])

    def test_notes_and_markers_reject_nonfinite_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'a.wav'
            source.write_bytes(b'a')
            with CaseStore(Path(tmp) / 'case.db') as store:
                eid = store.register_evidence(source)
                for time in (float('nan'), float('inf'), -float('inf')):
                    with self.subTest(time=time):
                        with self.assertRaises(ValueError):
                            store.add_note(eid, time, 'title', 'body')
                        with self.assertRaises(ValueError):
                            store.save_marker(eid, time, 'marker')

    def test_failed_import_preserves_previous_evidence_binding(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from audio_enviro_fingerprint.app import FingerprinterApp
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'a.wav'
            source.write_bytes(b'previous')
            with CaseStore(Path(tmp) / 'case.db') as store:
                original = store.register_evidence(source)
                source.write_bytes(b'changed')
                app = SimpleNamespace(store=store, evidence_id=original, result={'previous': True})
                with patch('audio_enviro_fingerprint.app.messagebox.showerror'):
                    FingerprinterApp.apply_result(app, {'path': source, 'sha256': '0' * 64})
                self.assertEqual(app.evidence_id, original)
                self.assertEqual(app.result, {'previous': True})
