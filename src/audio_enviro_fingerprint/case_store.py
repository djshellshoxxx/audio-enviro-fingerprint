"""Small SQLite store for evidence references and timestamped analyst notes."""
from __future__ import annotations

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

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
