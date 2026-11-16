"""Small best-effort desktop recording history, separate from evidence storage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

MAX_RECENT = 10
MAX_SETTINGS_BYTES = 64 * 1024


def _read_recent(path: Path) -> list[str]:
    if not path.is_file():
        raise ValueError('Preferences must be a regular file')
    with path.open('rb') as stream:
        raw = stream.read(MAX_SETTINGS_BYTES + 1)
    if len(raw) > MAX_SETTINGS_BYTES:
        raise ValueError('Preferences exceed the supported size')
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict) or set(data) != {'recent'}:
        raise ValueError('Unrecognized preferences format')
    recent = data['recent']
    if not isinstance(recent, list) or not all(isinstance(item, str) and item and '\x00' not in item for item in recent):
        raise ValueError('Invalid recent recordings')
    return list(dict.fromkeys(recent))[:MAX_RECENT]


def load_recent(path: str | Path) -> list[str]:
    """Missing, unreadable or malformed settings never prevent startup."""
    try:
        return _read_recent(Path(path))
    except (OSError, ValueError, UnicodeError):
        return []


def remember_recent(path: str | Path, recording: str | Path, *, previous: list[str] | None = None) -> list[str]:
    """Return session history and persist only into recognized settings or a new file.

    Unknown existing bytes may be evidence or another application's data. Leave
    them untouched even after later opens or a process restart; malformed
    settings disable persistence but never recording review or session history.
    """
    path = Path(path)
    scratch = None
    recent = list(previous or [])
    try:
        evidence = Path(recording).resolve()
        source = str(evidence)
        history = dict.fromkeys([*(previous or []), *load_recent(path)])
        recent = [source, *(item for item in history if item != source)][:MAX_RECENT]
        if path.resolve() == evidence or (path.exists() and evidence.exists() and path.samefile(evidence)):
            return recent
        if path.exists() or path.is_symlink():
            try:
                _read_recent(path)
            except (OSError, ValueError, UnicodeError):
                return recent
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.aefp-settings-', delete=False) as stream:
            scratch = Path(stream.name)
            json.dump({'recent': recent}, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(scratch, path)
        return recent
    except (OSError, ValueError):
        return recent
    finally:
        if scratch is not None:
            try:
                scratch.unlink(missing_ok=True)
            except OSError:
                pass
