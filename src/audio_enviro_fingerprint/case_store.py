"""Small SQLite store for evidence, notes, fingerprints, references, markers and runs.

The schema is versioned in a ``schema_version`` table. Databases created by
earlier releases (evidence + notes only, no version table) are detected as
schema 1 and upgraded in place by forward-only migrations.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone

from .integrity import sha256_file
from .reference import ReferenceMetadata, validate_reference

SCHEMA_VERSION = 2

_MIGRATIONS = {
    1: """
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
    """,
    2: """
        CREATE TABLE fingerprints (
            id INTEGER PRIMARY KEY,
            evidence_id INTEGER NOT NULL REFERENCES evidence(id),
            channel INTEGER NOT NULL CHECK(channel >= 0),
            version TEXT NOT NULL,
            canonical_json TEXT NOT NULL,
            fingerprint_hash TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            UNIQUE(evidence_id, channel, fingerprint_hash)
        );
        CREATE TABLE reference_recordings (
            id INTEGER PRIMARY KEY,
            evidence_id INTEGER NOT NULL REFERENCES evidence(id),
            evidence_sha256 TEXT NOT NULL,
            channel INTEGER NOT NULL CHECK(channel >= 0),
            metadata_json TEXT NOT NULL,
            created_utc TEXT NOT NULL
        );
        CREATE TABLE markers (
            id INTEGER PRIMARY KEY,
            evidence_id INTEGER NOT NULL REFERENCES evidence(id),
            timestamp_seconds REAL NOT NULL CHECK(timestamp_seconds >= 0),
            label TEXT NOT NULL,
            kind TEXT NOT NULL,
            revision INTEGER NOT NULL,
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            deleted_utc TEXT,
            deleted_reason TEXT
        );
        CREATE TABLE marker_revisions (
            id INTEGER PRIMARY KEY,
            marker_id INTEGER NOT NULL REFERENCES markers(id),
            revision INTEGER NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('create','update','delete')),
            timestamp_seconds REAL NOT NULL,
            label TEXT NOT NULL,
            kind TEXT NOT NULL,
            reason TEXT,
            recorded_utc TEXT NOT NULL,
            UNIQUE(marker_id, revision)
        );
        CREATE TABLE recurrence_runs (
            id INTEGER PRIMARY KEY,
            parameters_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_utc TEXT NOT NULL
        );
        CREATE INDEX idx_fingerprints_evidence ON fingerprints(evidence_id, channel);
        CREATE INDEX idx_markers_evidence ON markers(evidence_id);
    """,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp(value) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError("Marker timestamp must be a number") from None
    if not math.isfinite(value) or value < 0:
        raise ValueError("Marker timestamp must be finite and non-negative")
    return value


def _required(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _dumps(value) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except ValueError:
        raise ValueError("Values must be finite (NaN/Infinity cannot be stored)") from None


class CaseStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    # -- schema -----------------------------------------------------------
    def _migrate(self) -> None:
        con = self.connection
        con.execute("CREATE TABLE IF NOT EXISTS schema_version ("
                    "version INTEGER PRIMARY KEY, applied_utc TEXT NOT NULL)")
        con.commit()
        current = self.schema_version()
        if current > SCHEMA_VERSION:
            raise ValueError(f"Case database schema {current} is newer than supported {SCHEMA_VERSION}")
        for version in range(current + 1, SCHEMA_VERSION + 1):
            try:
                con.execute("BEGIN")
                for statement in _MIGRATIONS[version].split(";"):
                    if statement.strip():
                        con.execute(statement)
                con.execute("INSERT INTO schema_version(version, applied_utc) VALUES(?,?)", (version, _now()))
                con.commit()
            except Exception:
                con.rollback()
                raise

    def schema_version(self) -> int:
        row = self.connection.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        return int(row["v"] or 0)

    # -- evidence and notes (original behavior) ---------------------------
    def register_evidence(self, source_path: str | Path) -> int:
        source = Path(source_path).expanduser().resolve()
        digest = sha256_file(source)
        created = _now()
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
        created = _now()
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

    def evidence_list(self) -> list[dict]:
        rows = self.connection.execute("""
            SELECT e.*,
              (SELECT COUNT(*) FROM notes n WHERE n.evidence_id=e.id) AS note_count,
              (SELECT COUNT(*) FROM markers m WHERE m.evidence_id=e.id AND m.deleted_utc IS NULL) AS marker_count,
              (SELECT COUNT(*) FROM fingerprints f WHERE f.evidence_id=e.id) AS fingerprint_count,
              (SELECT COUNT(*) FROM reference_recordings r WHERE r.evidence_id=e.id) AS reference_count
            FROM evidence e ORDER BY e.id
        """).fetchall()
        return [dict(row) for row in rows]

    # -- fingerprints -----------------------------------------------------
    def store_fingerprint(self, evidence_id: int, channel: int, version: str,
                          canonical_json: str, fingerprint_hash: str) -> int:
        self.evidence_record(evidence_id)
        if isinstance(channel, bool) or not isinstance(channel, int) or channel < 0:
            raise ValueError("Channel must be a non-negative integer")
        try:
            payload = json.loads(canonical_json)
        except (TypeError, ValueError):
            raise ValueError("Fingerprint canonical JSON is not valid JSON") from None
        if not isinstance(payload, dict) or payload.get("version") != version:
            raise ValueError("Fingerprint canonical JSON version does not match the stated version")
        if hashlib.sha256(canonical_json.encode("utf-8")).hexdigest() != fingerprint_hash:
            raise ValueError("Fingerprint hash does not match SHA-256 of the canonical JSON")
        self.connection.execute(
            "INSERT OR IGNORE INTO fingerprints(evidence_id,channel,version,canonical_json,fingerprint_hash,"
            "created_utc) VALUES(?,?,?,?,?,?)",
            (evidence_id, channel, version, canonical_json, fingerprint_hash, _now()))
        self.connection.commit()
        row = self.connection.execute(
            "SELECT id FROM fingerprints WHERE evidence_id=? AND channel=? AND fingerprint_hash=?",
            (evidence_id, channel, fingerprint_hash)).fetchone()
        return int(row["id"])

    @staticmethod
    def _fingerprint_dict(row) -> dict:
        payload = json.loads(row["canonical_json"])
        return {"fingerprint_id": row["id"], "evidence_id": row["evidence_id"], "channel": row["channel"],
                "version": row["version"], "features": payload.get("features", {}),
                "fingerprint_hash": row["fingerprint_hash"], "canonical_json": row["canonical_json"],
                "created_utc": row["created_utc"]}

    def fingerprints_for(self, evidence_id: int) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM fingerprints WHERE evidence_id=? ORDER BY id",
                                       (evidence_id,)).fetchall()
        return [self._fingerprint_dict(row) for row in rows]

    # -- references -------------------------------------------------------
    def add_reference(self, evidence_id: int, metadata: ReferenceMetadata, channel: int = 0) -> int:
        if isinstance(metadata, dict):
            metadata = ReferenceMetadata.from_dict(metadata)
        problems = validate_reference(metadata)
        if problems:
            raise ValueError("Invalid reference metadata: " + "; ".join(problems))
        if isinstance(channel, bool) or not isinstance(channel, int) or channel < 0:
            raise ValueError("Channel must be a non-negative integer")
        evidence = self.evidence_record(evidence_id)
        cursor = self.connection.execute(
            "INSERT INTO reference_recordings(evidence_id,evidence_sha256,channel,metadata_json,created_utc) "
            "VALUES(?,?,?,?,?)",
            (evidence_id, evidence["sha256"], channel, _dumps(metadata.to_dict()), _now()))
        self.connection.commit()
        return int(cursor.lastrowid)

    def references(self) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM reference_recordings ORDER BY id").fetchall()
        result = []
        for row in rows:
            latest = self.connection.execute(
                "SELECT * FROM fingerprints WHERE evidence_id=? AND channel=? ORDER BY id DESC LIMIT 1",
                (row["evidence_id"], row["channel"])).fetchone()
            result.append({"reference_id": row["id"], "evidence_id": row["evidence_id"],
                           "evidence_sha256": row["evidence_sha256"], "channel": row["channel"],
                           "metadata": json.loads(row["metadata_json"]), "created_utc": row["created_utc"],
                           "fingerprint": self._fingerprint_dict(latest) if latest is not None else None})
        return result

    # -- markers ----------------------------------------------------------
    def _marker_row(self, marker_id: int):
        row = self.connection.execute("SELECT * FROM markers WHERE id=?", (marker_id,)).fetchone()
        if row is None:
            raise ValueError("Marker does not exist")
        return row

    def _record_revision(self, marker_id, revision, action, timestamp, label, kind, reason, when) -> None:
        self.connection.execute(
            "INSERT INTO marker_revisions(marker_id,revision,action,timestamp_seconds,label,kind,reason,"
            "recorded_utc) VALUES(?,?,?,?,?,?,?,?)",
            (marker_id, revision, action, timestamp, label, kind, reason, when))

    def add_marker(self, evidence_id: int, timestamp_seconds: float, label: str, kind: str = "manual") -> int:
        timestamp = _timestamp(timestamp_seconds)
        label = _required(label, "Marker label")
        kind = _required(kind, "Marker kind")
        self.evidence_record(evidence_id)
        when = _now()
        try:
            cursor = self.connection.execute(
                "INSERT INTO markers(evidence_id,timestamp_seconds,label,kind,revision,created_utc,updated_utc) "
                "VALUES(?,?,?,?,1,?,?)", (evidence_id, timestamp, label, kind, when, when))
            marker_id = int(cursor.lastrowid)
            self._record_revision(marker_id, 1, "create", timestamp, label, kind, None, when)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return marker_id

    def update_marker(self, marker_id: int, timestamp_seconds: float, label: str, reason: str) -> None:
        timestamp = _timestamp(timestamp_seconds)
        label = _required(label, "Marker label")
        reason = _required(reason, "Reason for marker change")
        row = self._marker_row(marker_id)
        if row["deleted_utc"] is not None:
            raise ValueError("Deleted markers cannot be edited")
        revision = int(row["revision"]) + 1
        when = _now()
        try:
            self.connection.execute(
                "UPDATE markers SET timestamp_seconds=?, label=?, revision=?, updated_utc=? WHERE id=?",
                (timestamp, label, revision, when, marker_id))
            self._record_revision(marker_id, revision, "update", timestamp, label, row["kind"], reason, when)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def delete_marker(self, marker_id: int, reason: str) -> None:
        reason = _required(reason, "Reason for marker deletion")
        row = self._marker_row(marker_id)
        if row["deleted_utc"] is not None:
            raise ValueError("Marker is already deleted")
        revision = int(row["revision"]) + 1
        when = _now()
        try:
            self.connection.execute(
                "UPDATE markers SET revision=?, updated_utc=?, deleted_utc=?, deleted_reason=? WHERE id=?",
                (revision, when, when, reason, marker_id))
            self._record_revision(marker_id, revision, "delete", row["timestamp_seconds"], row["label"],
                                  row["kind"], reason, when)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def markers_for(self, evidence_id: int, include_deleted: bool = False) -> list[dict]:
        sql = ("SELECT m.*, e.sha256 AS evidence_sha256 FROM markers m JOIN evidence e ON e.id=m.evidence_id "
               "WHERE m.evidence_id=?")
        if not include_deleted:
            sql += " AND m.deleted_utc IS NULL"
        rows = self.connection.execute(sql + " ORDER BY m.timestamp_seconds, m.id", (evidence_id,)).fetchall()
        return [dict(row) for row in rows]

    def marker_history(self, marker_id: int) -> list[dict]:
        self._marker_row(marker_id)
        rows = self.connection.execute(
            "SELECT * FROM marker_revisions WHERE marker_id=? ORDER BY revision", (marker_id,)).fetchall()
        return [dict(row) for row in rows]

    # -- recurrence runs --------------------------------------------------
    def save_recurrence_run(self, parameters: dict, results: list[dict]) -> int:
        if not isinstance(parameters, dict) or not isinstance(results, list):
            raise ValueError("Recurrence run needs a parameter mapping and a result list")
        cursor = self.connection.execute(
            "INSERT INTO recurrence_runs(parameters_json,results_json,created_utc) VALUES(?,?,?)",
            (_dumps(parameters), _dumps(results), _now()))
        self.connection.commit()
        return int(cursor.lastrowid)

    def recurrence_runs(self) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM recurrence_runs ORDER BY id").fetchall()
        return [{"run_id": row["id"], "created_utc": row["created_utc"],
                 "parameters": json.loads(row["parameters_json"]),
                 "results": json.loads(row["results_json"])} for row in rows]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
