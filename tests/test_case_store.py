import hashlib
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from audio_enviro_fingerprint.case_store import SCHEMA_VERSION, CaseStore
from audio_enviro_fingerprint.reference import ReferenceMetadata

ORIGINAL_SCHEMA = """
    CREATE TABLE evidence (id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, sha256 TEXT NOT NULL,
        first_seen_utc TEXT NOT NULL, UNIQUE(source_path, sha256));
    CREATE TABLE notes (id INTEGER PRIMARY KEY, evidence_id INTEGER NOT NULL REFERENCES evidence(id),
        timestamp_seconds REAL NOT NULL CHECK(timestamp_seconds >= 0), title TEXT NOT NULL,
        body TEXT NOT NULL, created_utc TEXT NOT NULL);
"""


def _metadata(**changes):
    values = dict(location_id="LAB-1", captured_at_utc="2026-10-01T12:00:00Z", operator="Examiner A",
                  recorder_make_model="Recorder X", microphone_make_model="Mic Y", sample_rate_hz=8000,
                  placement="table centre", consent_authority="Site permit 42", source_signal="ambient")
    values.update(changes)
    return ReferenceMetadata(**values)


class CaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.evidence = self.dir / "rec.wav"
        self.evidence.write_bytes(b"evidence")

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrates_database_created_with_original_schema(self):
        db = self.dir / "old.sqlite"
        con = sqlite3.connect(db)
        con.executescript(ORIGINAL_SCHEMA)
        con.execute("INSERT INTO evidence(source_path,sha256,first_seen_utc) VALUES('x','abc','t')")
        con.execute("INSERT INTO notes(evidence_id,timestamp_seconds,title,body,created_utc) VALUES(1,2,'a','b','t')")
        con.commit()
        con.close()
        with CaseStore(db) as store:
            self.assertEqual(store.schema_version(), SCHEMA_VERSION)
            self.assertEqual(store.notes_for(1)[0]["title"], "a")
            self.assertEqual(store.markers_for(1), [])
        with CaseStore(db) as store:  # reopening is idempotent
            self.assertEqual(store.schema_version(), SCHEMA_VERSION)

    def test_marker_revisions_and_soft_delete_keep_history(self):
        with CaseStore(self.dir / "c.sqlite") as store:
            evidence_id = store.register_evidence(self.evidence)
            marker = store.add_marker(evidence_id, 4.0, "Door closes")
            store.update_marker(marker, 4.5, "Door closes (refined)", "aligned to waveform onset")
            with self.assertRaises(ValueError):
                store.update_marker(marker, 5.0, "x", " ")
            with self.assertRaises(ValueError):
                store.add_marker(evidence_id, math.nan, "bad")
            with self.assertRaises(ValueError):
                store.add_marker(evidence_id, -1, "bad")
            store.delete_marker(marker, "duplicate of note 3")
            self.assertEqual(store.markers_for(evidence_id), [])
            kept = store.markers_for(evidence_id, include_deleted=True)
            self.assertEqual(kept[0]["deleted_reason"], "duplicate of note 3")
            history = store.marker_history(marker)
            self.assertEqual([h["action"] for h in history], ["create", "update", "delete"])
            self.assertEqual(history[1]["timestamp_seconds"], 4.5)
            with self.assertRaises(ValueError):
                store.update_marker(marker, 1.0, "again", "reason")

    def test_fingerprint_and_reference_round_trip(self):
        with CaseStore(self.dir / "c.sqlite") as store:
            evidence_id = store.register_evidence(self.evidence)
            canonical = '{"features":{"x":1.0},"version":"aefp-1"}'
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            with self.assertRaises(ValueError):
                store.store_fingerprint(evidence_id, 0, "aefp-1", canonical, "0" * 64)
            fp_id = store.store_fingerprint(evidence_id, 0, "aefp-1", canonical, digest)
            self.assertEqual(store.store_fingerprint(evidence_id, 0, "aefp-1", canonical, digest), fp_id)
            ref_id = store.add_reference(evidence_id, _metadata())
            with self.assertRaises(ValueError):
                store.add_reference(evidence_id, _metadata(location_id=""))
            refs = store.references()
            self.assertEqual(refs[0]["reference_id"], ref_id)
            self.assertEqual(refs[0]["metadata"]["location_id"], "LAB-1")
            self.assertEqual(refs[0]["fingerprint"]["features"], {"x": 1.0})
            self.assertEqual(store.evidence_list()[0]["reference_count"], 1)

    def test_recurrence_runs_reject_non_finite_values(self):
        with CaseStore(self.dir / "c.sqlite") as store:
            run = store.save_recurrence_run({"max_distance": 0.25}, [{"distance": 0.1}])
            self.assertEqual(store.recurrence_runs()[0]["run_id"], run)
            with self.assertRaises(ValueError):
                store.save_recurrence_run({"max_distance": math.inf}, [])


if __name__ == "__main__":
    unittest.main()
