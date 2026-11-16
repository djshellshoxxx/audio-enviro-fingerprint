"""Cryptographic integrity operations; hashes cover original file bytes."""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat


def evidence_stat(path: str | Path) -> tuple[int, int, int, int, int]:
    """Return a regular file's identity/change token, not an authenticity proof."""
    info = Path(path).stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Evidence input must be a regular local file")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024, *, should_cancel=None) -> str:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError("Hash chunk size must be a positive integer")
    from .control import check_cancelled
    check_cancelled(should_cancel)
    source = Path(path)
    evidence_stat(source)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
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
