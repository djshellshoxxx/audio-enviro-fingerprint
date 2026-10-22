"""Analysis report assembly with a self-verifying manifest (integrity, not authenticity)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__
from .integrity import sha256_file

SCHEMA = "aefp-report-2"
LIMITATIONS = ("Candidate transitions and recurrences are review aids, not findings.",
               "Fingerprint score is neither a probability nor a likelihood ratio.",
               "Musical, hum and spatial descriptors are heuristic and unvalidated forensically.",
               "RT60 requires a separate measured impulse response.",
               "The manifest detects accidental or casual modification only; it is not a digital signature.")


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def build_report(source_path: str | Path, evidence_sha256: str, sections: dict) -> dict:
    """Wrap analysis ``sections`` with provenance and a SHA-256 manifest over the body."""
    body = {"schema_version": SCHEMA, "application_version": __version__,
            "evidence": {"source_path": str(source_path), "sha256": evidence_sha256},
            "sections": sections, "limitations": list(LIMITATIONS)}
    return {**body, "manifest": {"algorithm": "sha256-canonical-json",
                                 "body_sha256": hashlib.sha256(_canonical(body)).hexdigest()}}


def write_report(path: str | Path, report: dict) -> None:
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def verify_report(path: str | Path, check_evidence: bool = True) -> dict:
    """Recompute the manifest and (optionally) the evidence file hash."""
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported or malformed report schema")
    manifest = report.get("manifest")
    evidence = report.get("evidence")
    if not isinstance(manifest, dict) or not isinstance(evidence, dict):
        raise ValueError("Report requires manifest and evidence objects")
    if not isinstance(evidence.get("source_path"), str) or not isinstance(evidence.get("sha256"), str):
        raise ValueError("Report evidence requires a source path and SHA-256")
    body = {k: v for k, v in report.items() if k != "manifest"}
    actual = hashlib.sha256(_canonical(body)).hexdigest()
    result = {"manifest_ok": (manifest.get("algorithm") == "sha256-canonical-json"
                              and actual == manifest.get("body_sha256")), "evidence_checked": False,
              "evidence_ok": None}
    source = Path(report.get("evidence", {}).get("source_path", ""))
    if check_evidence and source.is_file():
        result["evidence_checked"] = True
        result["evidence_ok"] = sha256_file(source) == report["evidence"]["sha256"]
    return result
