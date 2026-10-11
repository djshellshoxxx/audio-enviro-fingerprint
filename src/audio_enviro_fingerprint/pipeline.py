"""One analysis pass over an evidence file, shared by the desktop app and the CLI.

The evidence SHA-256 is computed before and after decoding; a mismatch means the
file changed while it was being read and the result is rejected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .audio_io import AudioData, load_audio
from .features import AnalysisResult, analyze_audio
from .fingerprint import Fingerprint, make_fingerprint
from .integrity import sha256_file
from .methods.channels import describe_channels
from .recurrence import Recurrence, Segment, find_recurrences, segment_analysis
from .report import build_report
from .transitions import Transition, detect_transitions

DEFAULT_SETTINGS = {"frame_seconds": 2.0, "hop_seconds": 1.0, "transition_threshold": 0.35,
                    "minimum_separation_seconds": 3.0, "recurrence_max_distance": 0.25}


@dataclass(frozen=True)
class AnalysisBundle:
    path: Path
    sha256: str
    audio: AudioData
    analysis: AnalysisResult
    fingerprint: Fingerprint
    transitions: list[Transition]
    channel_summary: dict
    segments: list[Segment]
    recurrences: list[Recurrence]
    settings: dict = field(default_factory=dict)


def _settings(overrides: dict | None) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    for key, value in (overrides or {}).items():
        if key not in settings:
            raise ValueError(f"Unknown analysis setting: {key}")
        if value is not None:
            settings[key] = float(value)
    return settings


def analyze_file(path, channel: int = 0, settings: dict | None = None, progress=None,
                 cancel=None) -> AnalysisBundle:
    """Hash, decode, analyze and fingerprint one recording (read-only)."""
    path = Path(path)
    cfg = _settings(settings)
    initial = sha256_file(path)
    audio = load_audio(path, channel)
    analysis = analyze_audio(audio.samples, audio.sample_rate, cfg["frame_seconds"], cfg["hop_seconds"],
                             progress=progress, cancel=cancel)
    if not analysis.frames:
        raise ValueError(f"Recording is shorter than one {cfg['frame_seconds']:g} s analysis frame")
    fingerprint = make_fingerprint(analysis)
    transitions = detect_transitions(analysis, cfg["transition_threshold"], cfg["minimum_separation_seconds"])
    segments = segment_analysis(analysis, path.name, cfg["transition_threshold"],
                                cfg["minimum_separation_seconds"])
    recurrences = find_recurrences(segments, cfg["recurrence_max_distance"])
    channel_data = audio.channel_data if audio.channel_data is not None else audio.samples
    channel_summary = describe_channels(channel_data, audio.sample_rate)
    if sha256_file(path) != initial:
        raise ValueError("The source file changed while it was being analyzed. Re-open a stable copy.")
    return AnalysisBundle(path, initial, audio, analysis, fingerprint, transitions, channel_summary,
                          segments, recurrences, cfg)


def bundle_report(bundle: AnalysisBundle, application_version: str, notes=None, markers=None) -> dict:
    """Build an aefp-report-2 dictionary for an analysis bundle."""
    return build_report(evidence_path=bundle.path, evidence_sha256=bundle.sha256, audio=bundle.audio,
                        analysis=bundle.analysis, fingerprint=bundle.fingerprint,
                        transitions=bundle.transitions, notes=notes or [], markers=markers or [],
                        channel_summary=bundle.channel_summary, recurrences=bundle.recurrences,
                        application_version=application_version, settings=bundle.settings)
