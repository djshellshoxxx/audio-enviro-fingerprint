"""Readable reports preserve evidence and escape analyst supplied markup."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from audio_enviro_fingerprint.cli import run
from audio_enviro_fingerprint.control import AnalysisCancelled
from audio_enviro_fingerprint.html_report import render_html_report, write_html_report
from audio_enviro_fingerprint.integrity import sha256_file
from audio_enviro_fingerprint.pipeline import analyze_file, full_report
from audio_enviro_fingerprint.report import build_report
from test_extended import tone, write_wav


class HtmlReportTests(unittest.TestCase):
    def test_readable_summary_contains_hashes_and_escapes_notes(self):
        report = build_report('evidence<script>.wav', 'a' * 64, {
            'audio': {'duration_seconds': 62.5, 'sample_rate': 16000, 'channels': 2},
            'fingerprint_sha256': 'b' * 64,
            'notes': [{'title': '<img src=x onerror=alert(1)>', 'body': 'A & B'}],
            'transitions': [{'timestamp_seconds': 2.5, 'strength': 0.4}],
        })
        html = render_html_report(report)
        self.assertIn('<!doctype html>', html.lower())
        self.assertIn('Evidence', html)
        self.assertIn('a' * 64, html)
        self.assertIn('b' * 64, html)
        self.assertIn('16000', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertIn('A &amp; B', html)
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('<script', html.lower())
        self.assertIn('not a digital signature', html)
        self.assertIn('print', html)

    def test_invalid_manifest_or_nonfinite_report_is_rejected(self):
        report = build_report('source.wav', 'a' * 64, {})
        report['sections']['tampered'] = True
        with self.assertRaises(ValueError):
            render_html_report(report)
        report['sections']['value'] = float('nan')
        with self.assertRaises(ValueError):
            render_html_report(report)

    def test_malformed_nested_report_fields_raise_clear_input_error(self):
        for sections in ({'audio': 'invalid'}, {'analysis': 3}, {'analysis': {'frames': None}}):
            with self.subTest(sections=sections), self.assertRaises(ValueError):
                render_html_report(build_report('source.wav', 'a' * 64, sections))

    def test_export_rechecks_evidence_and_protects_evidence_database_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, database, target = root / 'a.wav', root / 'case.db', root / 'report.html'
            source.write_bytes(b'original')
            database.write_bytes(b'case')
            alias = root / 'alias.html'
            alias.symlink_to(database)
            report = build_report(source, sha256_file(source), {})
            for forbidden in (source, database, alias):
                with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                    write_html_report(forbidden, report, protected_paths=(database,))
            write_html_report(target, report)
            previous = target.read_bytes()
            self.assertTrue(previous.startswith(b'<!doctype html>'))
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                write_html_report(target, report)
            self.assertEqual(target.read_bytes(), previous)
            self.assertEqual(database.read_bytes(), b'case')

    def test_cancelled_export_leaves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'source', Path(tmp) / 'report.html'
            source.write_bytes(b'original')
            target.write_text('previous')
            report = build_report(source, sha256_file(source), {})
            with self.assertRaises(AnalysisCancelled):
                write_html_report(target, report, should_cancel=lambda: True)
            self.assertEqual(target.read_text(), 'previous')

    def test_cli_html_file_and_stdout_share_analysis_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'a.wav', Path(tmp) / 'report.html'
            write_wav(source, tone(440, 3))
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(run(['analyze', str(source), '--no-musical', '--format', 'html', '-o', str(target)]), 0)
            self.assertIn('Report written', stdout.getvalue())
            html = target.read_text()
            self.assertIn(sha256_file(source), html)
            self.assertIn(full_report(analyze_file(source, musical=False))['manifest']['body_sha256'], html)
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(run(['analyze', str(source), '--no-musical', '--format', 'html']), 0)
            self.assertTrue(stdout.getvalue().startswith('<!doctype html>'))
