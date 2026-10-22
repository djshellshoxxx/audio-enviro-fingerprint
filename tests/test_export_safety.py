"""Exports must preserve the original recording and the active case database."""
import os
from pathlib import Path
import tempfile
import unittest

from audio_enviro_fingerprint.integrity import sha256_file, write_export
from audio_enviro_fingerprint.report import build_report, write_report


class ExportSafetyTests(unittest.TestCase):
    def test_protects_case_database_and_aliases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, database = root / 'source.wav', root / 'cases.sqlite'
            source.write_bytes(b'source bytes')
            database.write_bytes(b'database bytes')
            hardlink, symlink = root / 'alias.json', root / 'link.json'
            os.link(database, hardlink)
            symlink.symlink_to(database)
            for destination in (source, database, hardlink, symlink):
                with self.subTest(destination=destination), self.assertRaises(ValueError):
                    write_export(destination, b'export', source, protected_paths=(database,))
            self.assertEqual(database.read_bytes(), b'database bytes')
            self.assertEqual(source.read_bytes(), b'source bytes')

    def test_report_export_rejects_changed_source_and_preserves_previous_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'source.wav', root / 'report.json'
            source.write_bytes(b'original')
            report = build_report(source, sha256_file(source), {})
            write_report(target, report)
            previous = target.read_bytes()
            source.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                write_report(target, report)
            self.assertEqual(target.read_bytes(), previous)

    def test_cancelled_export_leaves_existing_target_untouched(self):
        from audio_enviro_fingerprint.control import AnalysisCancelled
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'source.wav', root / 'report.json'
            source.write_bytes(b'original')
            target.write_bytes(b'previous export')
            report = build_report(source, sha256_file(source), {})
            with self.assertRaises(AnalysisCancelled):
                write_report(target, report, should_cancel=lambda: True)
            self.assertEqual(target.read_bytes(), b'previous export')
