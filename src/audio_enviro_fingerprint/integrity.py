"""Cryptographic integrity operations; hashes cover original file bytes."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024, *, should_cancel=None) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            from .control import check_cancelled
            check_cancelled(should_cancel)
            digest.update(chunk)
    return digest.hexdigest()


def write_export(path: str | Path, payload: bytes, source_path: str | Path, *,
                 protected_paths: tuple[str | Path, ...] = ()) -> None:
    """Atomically publish an export while refusing the source and its aliases.

    Replacing a directory entry rather than opening the destination for writing
    also avoids following a symlink swapped into place during export.
    """
    import os
    import tempfile

    target, source = Path(path), Path(source_path)
    for protected in (source, *(Path(item) for item in protected_paths)):
        if target.resolve() == protected.resolve() or (target.exists() and protected.exists() and target.samefile(protected)):
            raise ValueError("Export destination must not overwrite evidence or the case database")
    scratch = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.aefp-export-', delete=False) as out:
            scratch = Path(out.name)
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(scratch, target)
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)
