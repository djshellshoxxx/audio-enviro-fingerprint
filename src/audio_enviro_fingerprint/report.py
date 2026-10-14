"""Assemble the JSON analysis report (schema aefp-report-2)."""
from __future__ import annotations

import json

from . import __version__
from .recurrence import CONFOUNDERS, THRESHOLD_RATIONALE, find_recurrences, segment_recording
from .transitions import detect_transitions

SCHEMA = "aefp-report-2"
LIMITATIONS = ["PCM WAV only", "Only the selected channel is analyzed",
               "Transition scores are candidates requiring review",
               "Fingerprint score is not location probability",
               "Recurrence candidates are heuristic and uncalibrated",
               "Reference location labels are self-reported and unverified",
               "RT60 requires a separate measured impulse response"]


def build_report(*, source_path: str, sha256: str, channel_index: int, channel_count: int, analysis,
                 fingerprint, notes: list[dict], references: list[dict] | None = None,
                 comparisons: list[dict] | None = None, reference_chain_head: str = "") -> dict:
    transitions = detect_transitions(analysis)
    segments = segment_recording(analysis, transitions, "rec1")
    candidates = find_recurrences(segments, analysis.frame_seconds)
    report = {
        "schema_version": SCHEMA, "application_version": __version__,
        "evidence": {"source_path": source_path, "sha256": sha256,
                     "channel_analyzed": channel_index + 1, "channel_count": channel_count},
        "analysis": analysis.to_dict(),
        "fingerprint": json.loads(fingerprint.canonical_json),
        "fingerprint_sha256": fingerprint.fingerprint_hash,
        "transitions": [t.__dict__ for t in transitions],
        "segments": [s.__dict__ for s in segments],
        "recurrence": {"candidates": [c.to_dict() for c in candidates],
                       "rationale": THRESHOLD_RATIONALE, "confounders": list(CONFOUNDERS)},
        "parameters": {"transition_threshold": 0.35, "transition_min_separation_seconds": 3.0,
                       "frame_seconds": analysis.frame_seconds, "hop_seconds": analysis.hop_seconds},
        "comparisons": comparisons or [], "references": references or [],
        "reference_chain_head": reference_chain_head,
        "notes": notes, "limitations": LIMITATIONS,
    }
    json.dumps(report, allow_nan=False)  # fail loudly on non-finite values
    return report
