"""Single entry point: command-line arguments run the CLI, otherwise the GUI starts."""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        from .cli import run
        return run(args)
    from .app import main as gui_main   # imported lazily: Tk is optional for CLI use
    gui_main()
    return 0
