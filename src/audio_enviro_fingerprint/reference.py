"""Known-location reference acquisition: capture metadata, quality review and ranking.

A reference recording is an exemplar captured under a documented, controlled
protocol at a location described by the operator. The location label is
self-reported metadata: nothing here verifies it, and a high similarity score
against a reference is a screening observation, never a location identification.
Quality grades and the repeat/duration minimums are unvalidated beta defaults.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime
import math
import re

from .comparison import compare_fingerprints

MIN_DURATION_SECONDS = 30.0
MIN_REPEATS = 3
RANKING_CAVEAT = ("The reference location label is self-reported capture metadata and is not verified by "
                  "this software. A high descriptive similarity score is not an identification of the "
                  "recording location, not a probability of common origin, and must be weighed against "
                  "device, placement, activity, processing and time-of-capture confounders.")

CAPTURE_CHECKLIST: tuple[str, ...] = (
    "location_identifier_recorded",
    "capture_time_utc_recorded",
    "operator_recorded",
    "consent_authority_documented",
    "recorder_make_model_and_serial_documented",
    "microphone_documented",
    "input_chain_documented",
    "channel_and_sample_rate_documented",
    "placement_orientation_height_documented",
    "source_signal_documented",
    "occupancy_activity_documented",
    "weather_documented",
    "calibration_documented",
    "deviations_documented",
    "source_hash_recorded",
    "repeat_series_captured",
)

_REQUIRED_TEXT = ("location_id", "captured_at_utc", "operator", "recorder_make_model",
                  "microphone_make_model", "consent_authority", "source_signal", "placement")


@dataclass(frozen=True)
class ReferenceMetadata:
    location_id: str
    captured_at_utc: str
    operator: str
    recorder_make_model: str
    recorder_serial: str = ""
    microphone_make_model: str = ""
    input_chain: str = ""
    channel: int = 0
    sample_rate_hz: int = 0
    placement: str = ""
    orientation: str = ""
    height_m: float | None = None
    source_signal: str = ""
    occupancy_activity: str = ""
    weather: str = ""
    calibration: str = ""
    repeat_index: int = 1
    deviations: str = ""
    consent_authority: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReferenceMetadata":
        if not isinstance(data, dict):
            raise ValueError("Reference metadata must be a mapping")
        names = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - names)
        if unknown:
            raise ValueError(f"Unknown reference metadata fields: {', '.join(unknown)}")
        missing = [name for name in ("location_id", "captured_at_utc", "operator", "recorder_make_model")
                   if name not in data]
        if missing:
            raise ValueError(f"Missing reference metadata fields: {', '.join(missing)}")
        return cls(**data)


def _parse_utc(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_reference(meta: ReferenceMetadata) -> list[str]:
    """Return a list of problems; an empty list means the metadata is structurally valid."""
    if isinstance(meta, dict):
        try:
            meta = ReferenceMetadata.from_dict(meta)
        except (TypeError, ValueError) as exc:
            return [str(exc)]
    problems = []
    for name in _REQUIRED_TEXT:
        if not _text(getattr(meta, name)):
            problems.append(f"{name} is required")
    if _text(meta.captured_at_utc) and _parse_utc(meta.captured_at_utc) is None:
        problems.append("captured_at_utc must be an ISO-8601 date-time with a timezone offset")
    if not _is_int(meta.sample_rate_hz) or meta.sample_rate_hz <= 0:
        problems.append("sample_rate_hz must be a positive integer")
    if not _is_int(meta.channel) or meta.channel < 0:
        problems.append("channel must be a non-negative integer (zero-based)")
    if meta.height_m is not None:
        if isinstance(meta.height_m, bool) or not isinstance(meta.height_m, (int, float)) \
                or not math.isfinite(meta.height_m) or meta.height_m < 0:
            problems.append("height_m must be a finite non-negative number when given")
    if not _is_int(meta.repeat_index) or meta.repeat_index < 1:
        problems.append("repeat_index must be an integer of at least 1")
    for f in fields(meta):
        value = getattr(meta, f.name)
        if f.name not in ("channel", "sample_rate_hz", "height_m", "repeat_index") and not isinstance(value, str):
            problems.append(f"{f.name} must be text")
    return problems


def quality_review(meta: ReferenceMetadata, audio_info: dict | None = None) -> dict:
    """Checklist completeness, issues and a beta grade for a reference capture.

    audio_info (optional) may contain: sample_rate (or sample_rate_hz), channels,
    duration_seconds, clipping (bool) or clipped_fraction (float), repeat_count
    (captures of this location in the series) and sha256 (source file hash).
    """
    info = dict(audio_info or {})
    problems = validate_reference(meta)
    if isinstance(meta, dict):
        try:
            meta = ReferenceMetadata.from_dict(meta)
        except (TypeError, ValueError):
            meta = None
    get = (lambda name: getattr(meta, name)) if meta is not None else (lambda name: None)
    sha = info.get("sha256")
    repeat_count = info.get("repeat_count")
    checklist = {
        "location_identifier_recorded": _text(get("location_id")),
        "capture_time_utc_recorded": _parse_utc(get("captured_at_utc")) is not None,
        "operator_recorded": _text(get("operator")),
        "consent_authority_documented": _text(get("consent_authority")),
        "recorder_make_model_and_serial_documented": _text(get("recorder_make_model")) and _text(get("recorder_serial")),
        "microphone_documented": _text(get("microphone_make_model")),
        "input_chain_documented": _text(get("input_chain")),
        "channel_and_sample_rate_documented": _is_int(get("channel")) and _is_int(get("sample_rate_hz"))
        and get("sample_rate_hz") > 0,
        "placement_orientation_height_documented": _text(get("placement")) and _text(get("orientation"))
        and get("height_m") is not None,
        "source_signal_documented": _text(get("source_signal")),
        "occupancy_activity_documented": _text(get("occupancy_activity")),
        "weather_documented": _text(get("weather")),
        "calibration_documented": _text(get("calibration")),
        "deviations_documented": _text(get("deviations")),
        "source_hash_recorded": isinstance(sha, str) and re.fullmatch(r"[0-9a-fA-F]{64}", sha) is not None,
        "repeat_series_captured": _is_int(repeat_count) and repeat_count >= MIN_REPEATS,
    }
    assert tuple(checklist) == CAPTURE_CHECKLIST
    completeness = sum(checklist.values()) / len(checklist)
    issues = [f"Metadata: {problem}" for problem in problems]
    blocking = bool(problems)
    cap = "A"

    def lower(grade):
        nonlocal cap
        cap = max(cap, grade)  # "A" < "B" < "C"

    rate = info.get("sample_rate", info.get("sample_rate_hz"))
    if rate is not None and meta is not None and _is_int(meta.sample_rate_hz) and int(rate) != meta.sample_rate_hz:
        issues.append(f"Decoded sample rate {int(rate)} Hz differs from documented {meta.sample_rate_hz} Hz")
        blocking = True
    channels = info.get("channels")
    if channels is not None and meta is not None and _is_int(meta.channel) and meta.channel >= int(channels):
        issues.append(f"Documented channel {meta.channel} does not exist in a {int(channels)}-channel file")
        blocking = True
    duration = info.get("duration_seconds")
    if duration is None:
        issues.append("Recording duration not supplied; minimum duration could not be checked")
        lower("B")
    elif not math.isfinite(float(duration)) or float(duration) < MIN_DURATION_SECONDS:
        issues.append(f"Duration {float(duration):.1f} s is below the {MIN_DURATION_SECONDS:.0f} s minimum")
        lower("C")
    clipped = info.get("clipping")
    fraction = info.get("clipped_fraction")
    if clipped or (fraction is not None and float(fraction) > 0):
        issues.append("Clipping reported in the reference capture")
        lower("C")
    if repeat_count is None:
        issues.append(f"Number of repeat captures not supplied (protocol asks for at least {MIN_REPEATS})")
        lower("B")
    elif not checklist["repeat_series_captured"]:
        issues.append(f"Only {repeat_count} repeat capture(s); protocol asks for at least {MIN_REPEATS}")
        lower("B")
    if meta is not None and _is_int(meta.repeat_index) and _is_int(repeat_count) and meta.repeat_index > repeat_count:
        issues.append(f"repeat_index {meta.repeat_index} exceeds repeat_count {repeat_count}")
        lower("C")
    if not checklist["source_hash_recorded"]:
        issues.append("Source SHA-256 not supplied for this reference")
        lower("B")
    if completeness < 0.6:
        lower("C")
    elif completeness < 1.0:
        lower("B")
    grade = "insufficient" if blocking else cap
    return {"checklist": checklist, "completeness": completeness, "issues": issues, "grade": grade}


def rank_against_references(query_fingerprint: dict, references: list[dict]) -> list[dict]:
    """Rank references by descriptive similarity to a query fingerprint.

    Incompatible references (version mismatch, missing fingerprint, no comparable
    features) are returned after the ranked items with status "skipped" and score None.
    """
    query_version = query_fingerprint.get("version", "aefp-1")
    query_features = query_fingerprint.get("features", query_fingerprint)
    ranked, skipped = [], []
    for ref in references:
        metadata = ref.get("metadata") or {}
        fingerprint = ref.get("fingerprint")
        item = {"reference_id": ref.get("reference_id"),
                "location_id": metadata.get("location_id") or "unspecified",
                "score": None, "differences": {}, "explanation": "", "caveat": RANKING_CAVEAT,
                "status": "ranked", "notes": []}
        if not fingerprint:
            item.update(status="skipped", explanation="Reference has no stored fingerprint.")
            skipped.append(item)
            continue
        ref_version = fingerprint.get("version", "aefp-1")
        if ref_version != query_version:
            item.update(status="skipped", explanation=(
                f"Fingerprint version mismatch (query {query_version}, reference {ref_version}); "
                "re-analyse with the same method version before comparing."))
            skipped.append(item)
            continue
        try:
            result = compare_fingerprints(query_fingerprint, fingerprint)
        except ValueError as exc:
            item.update(status="skipped", explanation=f"Not comparable: {exc}")
            skipped.append(item)
            continue
        ref_rate = fingerprint.get("features", {}).get("sample_rate_hz")
        if ref_rate is not None and query_features.get("sample_rate_hz") not in (None, ref_rate):
            item["notes"].append(f"Sample rates differ (query {query_features.get('sample_rate_hz')} Hz, "
                                 f"reference {ref_rate} Hz); band features above the lower Nyquist limit "
                                 "are not comparable.")
        item.update(score=float(result.score), differences=result.differences, explanation=result.explanation)
        ranked.append(item)
    ranked.sort(key=lambda item: (-item["score"], str(item["reference_id"])))
    skipped.sort(key=lambda item: str(item["reference_id"]))
    for position, item in enumerate(ranked, 1):
        item["rank"] = position
    for item in skipped:
        item["rank"] = None
    return ranked + skipped
