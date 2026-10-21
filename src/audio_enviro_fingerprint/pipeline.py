"""One-call analysis pipeline shared by the CLI and GUI (no UI dependencies)."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .audio_io import load_wav
from .features import analyze_audio
from .fingerprint import make_fingerprint
from .integrity import sha256_file
from .methods.hum import detect_mains_hum
from .methods.musical import musical_summary
from .multichannel import analyze_channels
from .recurrence import CONFOUNDERS, find_recurrences
from .report import build_report
from .transitions import detect_transitions


def analyze_file(path: str | Path, musical: bool = True, progress=None) -> dict:
    """Analyze a WAV and return all sections. The source hash is pinned before and after."""
    step = progress or (lambda *_: None)
    path = Path(path)
    step("Hashing evidence", 0.05)
    initial = sha256_file(path)
    step("Decoding audio", 0.15)
    audio = load_wav(path)
    step("Extracting acoustic features", 0.35)
    analysis = analyze_audio(audio.samples, audio.sample_rate)
    fingerprint = make_fingerprint(analysis)
    step("Detecting transitions and recurrence", 0.6)
    transitions = detect_transitions(analysis)
    recurrences = find_recurrences(analysis)
    step("Hum and channel analysis", 0.75)
    hum = detect_mains_hum(audio.samples, audio.sample_rate)
    channels = analyze_channels(audio) if audio.channels > 1 else None
    music = None
    if musical:
        step("Musical analysis", 0.88)
        music = musical_summary(audio.samples, audio.sample_rate)
    if sha256_file(path) != initial:
        raise ValueError("The source file changed during analysis. Re-open a stable copy of the evidence.")
    step("Done", 1.0)
    return {"audio": audio, "analysis": analysis, "fingerprint": fingerprint, "transitions": transitions,
            "recurrences": recurrences, "hum": hum, "channels": channels, "musical": music,
            "sha256": initial, "path": path}


def report_sections(result: dict, notes: list | None = None, markers: list | None = None) -> dict:
    audio = result["audio"]
    return {"audio": {"sample_rate": audio.sample_rate, "channels": audio.channels,
                      "duration_seconds": audio.duration_seconds, "sample_format": audio.sample_format,
                      "analyzed_channel": 1},
            "analysis": result["analysis"].to_dict(),
            "fingerprint": json.loads(result["fingerprint"].canonical_json),
            "fingerprint_sha256": result["fingerprint"].fingerprint_hash,
            "transitions": [asdict(t) for t in result["transitions"]],
            "recurrences": {"method": "recurrence-v1", "items": [r.to_dict() for r in result["recurrences"]],
                            "confounders": list(CONFOUNDERS)},
            "mains_hum": result["hum"], "channels": result["channels"], "musical": result["musical"],
            "notes": notes or [], "markers": markers or []}


def full_report(result: dict, notes=None, markers=None) -> dict:
    return build_report(result["path"], result["sha256"], report_sections(result, notes, markers))
