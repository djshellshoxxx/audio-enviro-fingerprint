"""Small SQLite store for evidence references and timestamped analyst notes."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

from .integrity import sha256_file


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
            CREATE TABLE IF NOT EXISTS reference_records (
                id INTEGER PRIMARY KEY,
                evidence_id INTEGER NOT NULL REFERENCES evidence(id),
                metadata_json TEXT NOT NULL,
                review_json TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS markers (
                id INTEGER PRIMARY KEY,
                evidence_id INTEGER NOT NULL REFERENCES evidence(id),
                marker_key INTEGER NOT NULL,
                revision INTEGER NOT NULL,
                timestamp_seconds REAL CHECK(timestamp_seconds IS NULL OR timestamp_seconds >= 0),
                label TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0,
                created_utc TEXT NOT NULL,
                UNIQUE(marker_key, revision)
            );
        """)
        self.connection.commit()

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
        if not math.isfinite(timestamp_seconds) or timestamp_seconds < 0:
            raise ValueError("Note timestamp must be finite and nonnegative")
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

    def add_reference(self, evidence_id: int, metadata: dict, review: dict) -> int:
        """Append-only: reference documentation is never updated in place."""
        self.evidence_record(evidence_id)
        cursor = self.connection.execute(
            "INSERT INTO reference_records(evidence_id,metadata_json,review_json,created_utc) VALUES(?,?,?,?)",
            (evidence_id, json.dumps(metadata, sort_keys=True, allow_nan=False), json.dumps(review, sort_keys=True, allow_nan=False),
             datetime.now(timezone.utc).isoformat()))
        self.connection.commit()
        return int(cursor.lastrowid)

    def references(self) -> list[dict]:
        rows = self.connection.execute("""
            SELECT r.id, r.evidence_id, r.metadata_json, r.review_json, r.created_utc,
                   e.sha256 AS evidence_sha256, e.source_path FROM reference_records r
            JOIN evidence e ON e.id=r.evidence_id ORDER BY r.id""").fetchall()
        return [{**dict(r), "metadata": json.loads(r["metadata_json"]),
                 "review": json.loads(r["review_json"])} for r in rows]

    def save_marker(self, evidence_id: int, timestamp_seconds: float | None, label: str,
                    marker_key: int | None = None, deleted: bool = False) -> int:
        """Create a manual segmentation marker or append a new revision; history is kept."""
        if timestamp_seconds is not None and (not math.isfinite(timestamp_seconds) or timestamp_seconds < 0):
            raise ValueError("Marker timestamp must be finite and nonnegative")
        self.evidence_record(evidence_id)
        if not label.strip():
            raise ValueError("Marker label is required")
        if marker_key is None:
            row = self.connection.execute("SELECT COALESCE(MAX(marker_key),0)+1 FROM markers").fetchone()
            marker_key, revision = int(row[0]), 1
        else:
            row = self.connection.execute("SELECT MAX(revision) FROM markers WHERE marker_key=? AND evidence_id=?",
                                          (marker_key, evidence_id)).fetchone()
            if row[0] is None:
                raise ValueError("Marker does not exist")
            revision = int(row[0]) + 1
        self.connection.execute(
            "INSERT INTO markers(evidence_id,marker_key,revision,timestamp_seconds,label,deleted,created_utc)"
            " VALUES(?,?,?,?,?,?,?)",
            (evidence_id, marker_key, revision, timestamp_seconds, label.strip(), int(deleted),
             datetime.now(timezone.utc).isoformat()))
        self.connection.commit()
        return marker_key

    def markers_for(self, evidence_id: int, include_history: bool = False) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM markers WHERE evidence_id=? ORDER BY marker_key, revision", (evidence_id,)).fetchall()
        rows = [dict(r) for r in rows]
        if include_history:
            return rows
        latest = {r["marker_key"]: r for r in rows}
        return sorted((r for r in latest.values() if not r["deleted"]),
                      key=lambda r: (r["timestamp_seconds"] is None, r["timestamp_seconds"] or 0))

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
