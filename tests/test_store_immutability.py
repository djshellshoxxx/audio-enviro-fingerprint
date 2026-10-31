"""Current-schema preservation of compatible legacy case-audit behavior."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audio_enviro_fingerprint.case_store import CaseStore


def source_stat(path):
    s = Path(path).stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


class StoreImmutabilityTests(unittest.TestCase):
    def test_verified_registration_uses_pinned_digest_without_rehash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            path.write_bytes(b'evidence')
            digest = hashlib.sha256(b'evidence').hexdigest()
            with CaseStore(Path(tmp) / 'case.db') as store:
                with patch('audio_enviro_fingerprint.case_store.sha256_file',
                           side_effect=AssertionError('must not hash on UI thread')):
                    eid = store.register_verified_evidence(path, digest, source_stat(path))
                    self.assertEqual(store.evidence_record(eid)['sha256'], digest)
                    self.assertEqual(store.register_verified_evidence(path, digest, source_stat(path)), eid)

    def test_verified_registration_rejects_changed_missing_and_invalid_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            path.write_bytes(b'evidence')
            token = source_stat(path)
            digest = hashlib.sha256(b'evidence').hexdigest()
            with CaseStore(Path(tmp) / 'case.db') as store:
                for invalid in ('', 'not a hash', 'g' * 64, None):
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        store.register_verified_evidence(path, invalid, token)
                path.write_bytes(b'changed!')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    store.register_verified_evidence(path, digest, token)
                path.unlink()
                with self.assertRaises((ValueError, OSError)):
                    store.register_verified_evidence(path, digest, token)
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM evidence').fetchone()[0], 0)

    def test_case_audit_rows_cannot_be_updated_or_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            path.write_bytes(b'evidence')
            with CaseStore(Path(tmp) / 'case.db') as store:
                eid = store.register_evidence(path)
                store.add_note(eid, 0.1, 'note', 'body')
                store.add_reference(eid, {'location_id': 'A'}, {'overall': 'warn'})
                key = store.save_marker(eid, 0.123456, 'entry')
                store.save_marker(eid, 0.234567, 'entry revised', key)
                for table in ('evidence', 'notes', 'reference_records', 'markers'):
                    with self.subTest(table=table):
                        with self.assertRaises(sqlite3.IntegrityError):
                            store.connection.execute(f'UPDATE {table} SET id=id')
                        with self.assertRaises(sqlite3.IntegrityError):
                            store.connection.execute(f'DELETE FROM {table}')
                        with self.assertRaises(sqlite3.IntegrityError):
                            store.connection.execute(f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}')
                self.assertEqual(len(store.markers_for(eid, True)), 2)

    def test_opening_existing_database_preserves_rows_and_installs_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'case.db'
            with sqlite3.connect(path) as db:
                db.executescript('''
                    CREATE TABLE evidence (
                        id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL,
                        first_seen_utc TEXT NOT NULL, UNIQUE(source_path,sha256));
                    INSERT INTO evidence VALUES(7, 'historical.wav', 'legacy-hash', '2026-10-01T00:00:00Z');
                ''')
            with CaseStore(path) as store:
                self.assertEqual(store.evidence_record(7)['source_path'], 'historical.wav')
                with self.assertRaises(sqlite3.IntegrityError):
                    store.connection.execute("UPDATE evidence SET source_path='changed.wav' WHERE id=7")

    def test_logical_key_replace_cannot_remove_audit_rows_with_new_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'audio.wav'
            source.write_bytes(b'evidence')
            with CaseStore(Path(tmp) / 'case.db') as store:
                eid = store.register_evidence(source)
                record = store.evidence_record(eid)
                # No child row exists: foreign-key restrictions cannot mask
                # SQLite REPLACE's implicit deletion of the original evidence.
                with self.assertRaises(sqlite3.IntegrityError):
                    store.connection.execute(
                        'INSERT OR REPLACE INTO evidence(source_path,sha256,first_seen_utc) VALUES(?,?,?)',
                        (record['source_path'], record['sha256'], 'replacement'))
                self.assertEqual(store.evidence_record(eid), record)
                self.assertEqual(store.register_evidence(source), eid)
                key = store.save_marker(eid, 0.123456, 'original')
                with self.assertRaises(sqlite3.IntegrityError):
                    store.connection.execute(
                        'INSERT OR REPLACE INTO markers(evidence_id,marker_key,revision,timestamp_seconds,'
                        'label,deleted,created_utc) VALUES(?,?,?,?,?,?,?)',
                        (eid, key, 1, 0.5, 'replacement', 0, 'replacement'))
                marker, = store.markers_for(eid, True)
                self.assertEqual((marker['timestamp_seconds'], marker['label']), (0.123456, 'original'))

    def test_recurrence_runs_are_evidence_bound_finite_and_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audio.wav'
            path.write_bytes(b'evidence')
            with CaseStore(Path(tmp) / 'case.db') as store:
                eid = store.register_evidence(path)
                params = {'method': 'recurrence-v1', 'threshold': 0.25}
                findings = [{'segment_id': 'R1', 'mean_distance': 0.1}]
                rid = store.save_recurrence_run(eid, params, findings)
                row, = store.recurrence_runs_for(eid)
                self.assertEqual((row['id'], row['parameters'], row['findings']), (rid, params, findings))
                self.assertEqual(store.recurrence_runs_for(eid + 1), [])
                with self.assertRaises(ValueError):
                    store.save_recurrence_run(eid + 1, params, findings)
                with self.assertRaises(ValueError):
                    store.save_recurrence_run(eid, {'threshold': float('nan')}, findings)
                with self.assertRaises(sqlite3.IntegrityError):
                    store.connection.execute('DELETE FROM recurrence_runs')
                self.assertEqual(len(store.recurrence_runs_for(eid)), 1)


if __name__ == '__main__':
    unittest.main()
