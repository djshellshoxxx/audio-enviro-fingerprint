"""Small SQLite store for evidence references and timestamped analyst notes."""
from __future__ import annotations

from pathlib import Path
import sqlite3
from datetime import datetime, timezone
import hashlib
import json

from .integrity import sha256_file
from .reference import canonical_metadata, metadata_hash, validate_reference_metadata


class CaseStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY,
                source_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                first_seen_utc TEXT NOT NULL,
                UNIQUE(source_path, sha256)
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                evidence_id INTEGER NOT NULL REFERENCES evidence(id),
                timestamp_seconds REAL NOT NULL CHECK(timestamp_seconds >= 0),
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reference_exemplars (
                id INTEGER PRIMARY KEY,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                metadata_sha256 TEXT NOT NULL,
                quality_json TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                prev_row_hash TEXT NOT NULL DEFAULT '',
                row_hash TEXT NOT NULL DEFAULT ''
            );
            CREATE TRIGGER IF NOT EXISTS reference_no_replace BEFORE INSERT ON reference_exemplars
            WHEN EXISTS (SELECT 1 FROM reference_exemplars WHERE id = NEW.id)
            BEGIN SELECT RAISE(ABORT, 'reference id already in use'); END;
            CREATE TRIGGER IF NOT EXISTS reference_no_update BEFORE UPDATE ON reference_exemplars
            BEGIN SELECT RAISE(ABORT, 'reference exemplars are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS reference_no_delete BEFORE DELETE ON reference_exemplars
            BEGIN SELECT RAISE(ABORT, 'reference exemplars are immutable'); END;
        """)
        self.connection.commit()
        self._migrate_reference_columns()

    def _migrate_reference_columns(self) -> None:
        cols = {r["name"] for r in self.connection.execute("PRAGMA table_info(reference_exemplars)")}
        for col in ("prev_row_hash", "row_hash"):
            if col not in cols:
                self.connection.execute(f"ALTER TABLE reference_exemplars ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    @staticmethod
    def _row_hash(prev: str, source_path, source_sha, meta_sha, quality_json, created) -> str:
        payload = "\x1f".join((prev, str(source_path), source_sha, meta_sha, quality_json, created))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def register_evidence(self, source_path: str | Path) -> int:
        source = Path(source_path).expanduser().resolve()
        digest = sha256_file(source)
        created = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            "INSERT OR IGNORE INTO evidence(source_path,sha256,first_seen_utc) VALUES(?,?,?)",
            (str(source), digest, created))
        self.connection.commit()
        row = self.connection.execute("SELECT id FROM evidence WHERE source_path=? AND sha256=?",
                                      (str(source), digest)).fetchone()
        return int(row["id"])

    def add_note(self, evidence_id: int, timestamp_seconds: float, title: str, body: str) -> int:
        if timestamp_seconds < 0:
            raise ValueError("Note timestamp cannot be negative")
        if not title.strip() or not body.strip():
            raise ValueError("Note title and body are required")
        created = datetime.now(timezone.utc).isoformat()
        cursor = self.connection.execute(
            "INSERT INTO notes(evidence_id,timestamp_seconds,title,body,created_utc) VALUES(?,?,?,?,?)",
            (evidence_id, float(timestamp_seconds), title.strip(), body.strip(), created))
        self.connection.commit()
        return int(cursor.lastrowid)

    def evidence_record(self, evidence_id: int) -> dict:
        row = self.connection.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
        if row is None:
            raise ValueError("Evidence record does not exist")
        return dict(row)

    def notes_for(self, evidence_id: int) -> list[dict]:
        rows = self.connection.execute("""
            SELECT n.*, e.sha256 AS evidence_sha256 FROM notes n
            JOIN evidence e ON e.id=n.evidence_id WHERE n.evidence_id=?
            ORDER BY n.timestamp_seconds,n.id
        """, (evidence_id,)).fetchall()
        return [dict(row) for row in rows]

    def add_reference(self, source_path: str | Path, metadata: dict, quality: dict) -> int:
        """Store an immutable reference record bound to the source file's SHA-256."""
        problems = validate_reference_metadata(metadata)
        if problems:
            raise ValueError("; ".join(problems))
        source = Path(source_path).expanduser().resolve()
        created = datetime.now(timezone.utc).isoformat()
        source_sha = sha256_file(source)
        quality_json = json.dumps(quality, sort_keys=True, allow_nan=False)
        previous = self.connection.execute(
            "SELECT row_hash FROM reference_exemplars ORDER BY id DESC LIMIT 1").fetchone()
        prev = previous["row_hash"] if previous else ""
        meta_sha = metadata_hash(metadata)
        row_hash = self._row_hash(prev, source, source_sha, meta_sha, quality_json, created)
        cursor = self.connection.execute(
            "INSERT INTO reference_exemplars(source_path,source_sha256,metadata_json,metadata_sha256,"
            "quality_json,created_utc,prev_row_hash,row_hash) VALUES(?,?,?,?,?,?,?,?)",
            (str(source), source_sha, canonical_metadata(metadata), meta_sha, quality_json, created,
             prev, row_hash))
        self.connection.commit()
        return int(cursor.lastrowid)

    def reference_record(self, reference_id: int) -> dict:
        row = self.connection.execute("SELECT * FROM reference_exemplars WHERE id=?", (reference_id,)).fetchone()
        if row is None:
            raise ValueError("Reference record does not exist")
        record = dict(row)
        record["metadata"] = json.loads(record["metadata_json"])["metadata"]
        record["quality"] = json.loads(record["quality_json"])
        return record

    def list_references(self) -> list[dict]:
        ids = [r["id"] for r in self.connection.execute("SELECT id FROM reference_exemplars ORDER BY id")]
        return [self.reference_record(i) for i in ids]

    def verify_reference(self, reference_id: int) -> dict:
        """Re-hash the source file and metadata and report whether they still match the record."""
        record = self.reference_record(reference_id)
        source = Path(record["source_path"])
        file_ok = source.is_file() and sha256_file(source) == record["source_sha256"]
        meta_ok = metadata_hash(record["metadata"]) == record["metadata_sha256"]
        return {"reference_id": reference_id, "source_hash_matches": file_ok, "metadata_hash_matches": meta_ok}

    def reference_chain_head(self) -> str:
        """Hash of the newest reference row; record it in reports/case notes to detect later edits."""
        row = self.connection.execute("SELECT row_hash FROM reference_exemplars ORDER BY id DESC LIMIT 1").fetchone()
        return row["row_hash"] if row else ""

    def verify_reference_chain(self) -> dict:
        """Walk every reference row recomputing its chained hash. Detects edits, removals and re-ordering
        of rows, but cannot detect truncation of the newest rows unless the head was recorded elsewhere."""
        prev, bad = "", []
        for row in self.connection.execute("SELECT * FROM reference_exemplars ORDER BY id"):
            expected = self._row_hash(prev, row["source_path"], row["source_sha256"], row["metadata_sha256"],
                                      row["quality_json"], row["created_utc"])
            meta_ok = metadata_hash(json.loads(row["metadata_json"])["metadata"]) == row["metadata_sha256"]
            if row["prev_row_hash"] != prev or row["row_hash"] != expected or not meta_ok:
                bad.append(row["id"])
            prev = row["row_hash"]
        return {"intact": not bad, "bad_row_ids": bad, "head": prev}

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
