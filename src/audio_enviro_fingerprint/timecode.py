"""Examiner timestamp input in seconds, MM:SS or HH:MM:SS."""
from __future__ import annotations

import math


def parse_timecode(text: str) -> float:
    """Parse finite nonnegative time, rejecting ambiguous clock components."""
    try:
        parts = text.strip().split(':')
        if len(parts) == 1:
            value = float(parts[0])
        elif len(parts) in (2, 3):
            if not all(part.isascii() and part.isdigit() for part in parts[:-1]):
                raise ValueError
            seconds = float(parts[-1])
            if not math.isfinite(seconds) or not 0 <= seconds < 60:
                raise ValueError
            if len(parts) == 3 and not 0 <= int(parts[1]) < 60:
                raise ValueError
            value = seconds + 60 * int(parts[-2])
            if len(parts) == 3:
                value += 3600 * int(parts[0])
        else:
            raise ValueError
        if not math.isfinite(value) or value < 0:
            raise ValueError
        return value
    except (AttributeError, ValueError, OverflowError) as exc:
        raise ValueError('Enter a finite nonnegative time in seconds, MM:SS or HH:MM:SS') from exc
