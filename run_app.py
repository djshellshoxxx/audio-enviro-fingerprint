"""Standalone PyInstaller entry point; package execution remains available via -m."""
from audio_enviro_fingerprint.launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
