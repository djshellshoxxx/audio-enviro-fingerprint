"""Known-location reference exemplar records and acquisition checklist.

A reference is a *claim made by the person acquiring it*. The software records the
claim, binds it to an immutable source hash, and reviews audio quality, but it never
treats a self-reported location label as proof of a match.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math

SCHEMA = "aefp-reference-1"

REQUIRED_FIELDS = {
    "location_identifier": "Location identifier / name of the reference environment",
    "acquisition_datetime": "Acquisition date/time (ISO 8601, with time zone preferred)",
    "operator": "Operator / examiner who made the capture",
    "authority_basis": "Authority or consent under which the capture was made",
    "recorder_make_model": "Recorder make and model",
    "recorder_serial": "Recorder serial number (or 'unknown')",
    "microphone_make_model": "Microphone make and model",
    "microphone_serial": "Microphone serial number (or 'unknown')",
    "input_chain": "Input chain: preamp, gain setting, AGC/noise suppression state, cabling",
    "channel": "Channel(s) used and their roles",
    "sample_rate_hz": "Declared sample rate (Hz)",
    "placement": "Microphone placement in the room",
    "orientation": "Microphone orientation / pointing direction",
    "height_m": "Microphone height above floor (m)",
    "source_signal": "Source signal (ambient only, sweep, clap, speech, etc.)",
    "occupancy_activity": "Occupancy and activity during capture",
}
OPTIONAL_FIELDS = {
    "weather": "Weather (relevant for exterior/semi-exterior spaces)",
    "calibration": "Calibration performed (device, level, date) or 'none'",
    "repeat_number": "Repeat number for this location (1 = first pass)",
    "repeat_of_reference_id": "Earlier reference id this repeats",
    "deviations": "Deviations from the planned protocol",
}
CHECKLIST = (
    "Authority/consent for the capture is documented",
    "Recorder AGC, noise suppression and enhancements are disabled and recorded",
    "Fixed gain; no gain changes during the capture",
    "Microphone position, height and orientation recorded and photographed",
    "At least 30 s of undisturbed ambient capture, plus repeats on separate occasions",
    "Doors/windows/HVAC/occupancy state noted",
    "Original file copied read-only; hash computed immediately",
    "Deviations from protocol written down",
)


def validate_reference_metadata(metadata: dict) -> list[str]:
    """Return a list of problems; empty means the record may be stored."""
    problems = []
    for key, label in REQUIRED_FIELDS.items():
        value = metadata.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append(f"Missing required field: {label}")
    when = metadata.get("acquisition_datetime")
    if isinstance(when, str) and when.strip():
        try:
            datetime.fromisoformat(when.strip().replace("Z", "+00:00"))
        except ValueError:
            problems.append("acquisition_datetime must be ISO 8601, e.g. 2026-10-14T09:30:00+00:00")
    for key in ("sample_rate_hz", "height_m"):
        value = metadata.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(value)
            if not math.isfinite(number) or number <= 0:
                raise ValueError
        except (TypeError, ValueError):
            problems.append(f"{key} must be a positive number")
    if not metadata.get("checklist_confirmed"):
        problems.append("The acquisition checklist must be confirmed (or deviations recorded)")
    return problems


def canonical_metadata(metadata: dict) -> str:
    known = {**REQUIRED_FIELDS, **OPTIONAL_FIELDS, "checklist_confirmed": ""}
    clean = {k: (v.strip() if isinstance(v, str) else v) for k, v in metadata.items() if k in known}
    return json.dumps({"schema": SCHEMA, "metadata": clean}, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def metadata_hash(metadata: dict) -> str:
    return hashlib.sha256(canonical_metadata(metadata).encode("utf-8")).hexdigest()


def declared_rate_conflict(metadata: dict, actual_rate: int) -> str | None:
    try:
        declared = int(float(metadata.get("sample_rate_hz")))
    except (TypeError, ValueError):
        return None
    if declared != actual_rate:
        return f"Declared sample rate {declared} Hz differs from file rate {actual_rate} Hz"
    return None


def caveat(reference: dict) -> str:
    return (f"Reference '{reference.get('location_identifier', '?')}' is documented by "
            f"{reference.get('operator', '?')}; its location label is self-reported metadata and is not "
            "verified by this software. Similarity to a reference does not establish a common location.")
