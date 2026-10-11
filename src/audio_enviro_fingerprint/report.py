"""Self-describing analysis reports with a hash manifest for integrity checking.

The manifest's SHA-256 values detect accidental or casual modification of a
report and bind it to the evidence hash recorded at import. They are not a
digital signature: anyone able to edit the report can also recompute them, so
custody of the report file still has to be documented separately.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from .integrity import sha256_file

SCHEMA_VERSION = "aefp-report-2"
CANONICALIZATION = "json sort_keys, separators (',', ':'), allow_nan=False, UTF-8"
LIMITATIONS = (
    "Transition scores are candidates requiring human review",
    "Fingerprint similarity is a descriptive screening score, not a location probability or identification",
    "Thresholds are unvalidated beta defaults; see docs/BENCHMARK_PROTOCOL.md",
    "Recurrence candidates may be caused by gain/AGC, foreground sources, codecs or similar rooms",
    "RT60 requires a separate measured impulse response",
    "Manifest hashes detect modification but are not a digital signature",
)
MANIFEST_KEYS = {"algorithm", "canonicalization", "report_sha256", "fingerprint_sha256", "evidence_sha256"}


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_plain(value):
    """Convert dataclasses, numpy values, paths and tuples into JSON-native data."""
    if is_dataclass(value) and not isinstance(value, type):
        return to_plain(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Report values must be finite numbers")
        return float(value)
    if hasattr(value, "tolist"):  # numpy scalars and arrays
        return to_plain(value.tolist())
    raise ValueError(f"Unsupported report value of type {type(value).__name__}")


def _fingerprint_payload(fingerprint) -> dict:
    if isinstance(fingerprint, dict):
        payload = {"version": fingerprint.get("version", "aefp-1"), "features": fingerprint.get("features", {})}
    else:
        payload = {"version": fingerprint.version, "features": fingerprint.features}
    payload = to_plain(payload)
    expected = getattr(fingerprint, "fingerprint_hash", None)
    if expected and _sha256_text(canonical_json(payload)) != expected:
        raise ValueError("Fingerprint hash does not match its features")
    return payload


def _audio_summary(audio) -> dict:
    if audio is None:
        return {}
    if isinstance(audio, dict):
        return to_plain(audio)
    summary = {"sample_rate_hz": int(audio.sample_rate), "channels": int(audio.channels),
               "source_width_bytes": int(audio.source_width_bytes),
               "duration_seconds": float(audio.duration_seconds),
               "selected_channel": int(getattr(audio, "selected_channel", 0))}
    decoder = getattr(audio, "decoder", None)
    summary["decoder"] = to_plain(decoder) if decoder else {"backend": "stdlib-wave", "notes": []}
    return summary


def _analysis_dict(analysis) -> dict:
    if isinstance(analysis, dict):
        return to_plain(analysis)
    if hasattr(analysis, "to_dict"):
        return to_plain(analysis.to_dict())
    return to_plain(analysis)


def report_digest(report: dict) -> str:
    """SHA-256 of the canonical JSON of the report without its manifest."""
    body = {key: value for key, value in report.items() if key != "manifest"}
    return _sha256_text(canonical_json(body))


def build_report(*, evidence_path, evidence_sha256: str, audio, analysis, fingerprint, transitions,
                 notes, markers=None, channel_summary=None, recurrences=None, application_version: str,
                 settings: dict | None = None, created_at_utc: str | None = None) -> dict:
    if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64:
        raise ValueError("evidence_sha256 must be a 64-character hexadecimal SHA-256 digest")
    evidence_sha256 = evidence_sha256.lower()
    int(evidence_sha256, 16)
    fingerprint_payload = _fingerprint_payload(fingerprint)
    report = {
        "schema_version": SCHEMA_VERSION,
        "application_version": str(application_version),
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evidence": {"source_path": str(evidence_path), "sha256": evidence_sha256},
        "audio": _audio_summary(audio),
        "analysis_settings": to_plain(settings or {}),
        "analysis": _analysis_dict(analysis),
        "fingerprint": fingerprint_payload,
        "transitions": to_plain(list(transitions or [])),
        "notes": to_plain(list(notes or [])),
        "markers": to_plain(list(markers or [])),
        "channel_summary": to_plain(channel_summary) if channel_summary is not None else None,
        "recurrences": to_plain(list(recurrences or [])),
        "limitations": list(LIMITATIONS),
    }
    # Round-trip so the hashed structure is exactly what a reader will parse.
    report = json.loads(canonical_json(report))
    report["manifest"] = {"algorithm": "sha256", "canonicalization": CANONICALIZATION,
                          "report_sha256": report_digest(report),
                          "fingerprint_sha256": _sha256_text(canonical_json(fingerprint_payload)),
                          "evidence_sha256": evidence_sha256}
    return report


def write_report(report: dict, path) -> Path:
    target = Path(path)
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    target.write_text(text, encoding="utf-8")
    return target


def _check(ok: bool, detail: str) -> dict:
    return {"ok": bool(ok), "detail": detail}


def verify_report(path_or_dict, evidence_path=None) -> dict:
    """Recompute manifest hashes (and the evidence hash if a file is given)."""
    checks: dict[str, dict] = {}
    try:
        if isinstance(path_or_dict, dict):
            report = json.loads(canonical_json(path_or_dict))
        else:
            report = json.loads(Path(path_or_dict).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        return {"ok": False, "checks": {"readable": _check(False, f"Unable to read report: {exc}")}}
    if not isinstance(report, dict):
        return {"ok": False, "checks": {"readable": _check(False, "Report is not a JSON object")}}
    checks["readable"] = _check(True, "Report parsed as JSON")
    schema = report.get("schema_version")
    checks["schema_version"] = _check(schema == SCHEMA_VERSION, f"schema_version={schema!r}, expected {SCHEMA_VERSION!r}")
    manifest = report.get("manifest")
    if not isinstance(manifest, dict):
        checks["manifest"] = _check(False, "Manifest missing")
        return {"ok": False, "checks": checks}
    well_formed = set(manifest) == MANIFEST_KEYS and manifest.get("algorithm") == "sha256" \
        and manifest.get("canonicalization") == CANONICALIZATION
    checks["manifest"] = _check(well_formed, "Manifest fields present and recognized" if well_formed
                                else f"Unexpected manifest content: {sorted(manifest)}")
    actual = report_digest(report)
    checks["report_sha256"] = _check(actual == manifest.get("report_sha256"),
                                     f"recomputed {actual}, manifest {manifest.get('report_sha256')}")
    try:
        fingerprint = report.get("fingerprint")
        fp_actual = _sha256_text(canonical_json({"version": fingerprint["version"], "features": fingerprint["features"]}))
        extra = set(fingerprint) - {"version", "features"}
        ok = fp_actual == manifest.get("fingerprint_sha256") and not extra
        detail = f"recomputed {fp_actual}, manifest {manifest.get('fingerprint_sha256')}"
        if extra:
            detail += f"; unexpected fingerprint fields {sorted(extra)}"
        checks["fingerprint_sha256"] = _check(ok, detail)
    except (KeyError, TypeError, ValueError) as exc:
        checks["fingerprint_sha256"] = _check(False, f"Fingerprint missing or malformed: {exc}")
    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    recorded = evidence.get("sha256")
    checks["evidence_sha256_consistent"] = _check(
        recorded is not None and recorded == manifest.get("evidence_sha256"),
        f"evidence.sha256 {recorded}, manifest {manifest.get('evidence_sha256')}")
    if evidence_path is not None:
        try:
            file_digest = sha256_file(evidence_path)
            checks["evidence_file"] = _check(file_digest == manifest.get("evidence_sha256"),
                                             f"file {file_digest}, manifest {manifest.get('evidence_sha256')}")
        except OSError as exc:
            checks["evidence_file"] = _check(False, f"Unable to hash evidence file: {exc}")
    return {"ok": all(item["ok"] for item in checks.values()), "checks": checks}
