# Codebase Map

| I want to... | Look in |
|---|---|
| Application (Tk GUI) | `src/audio_enviro_fingerprint/app.py`, `__main__.py`, `run_app.py` |
| WAV reading | `src/audio_enviro_fingerprint/audio_io.py` |
| Framewise features | `src/audio_enviro_fingerprint/features.py` |
| Feature methods (noise, reverberation, spectral) | `src/audio_enviro_fingerprint/methods/` |
| Fingerprint assembly | `src/audio_enviro_fingerprint/fingerprint.py` |
| Change points | `src/audio_enviro_fingerprint/transitions.py` |
| Comparison | `src/audio_enviro_fingerprint/comparison.py` |
| Hashing and integrity | `src/audio_enviro_fingerprint/integrity.py` |
| Case notes (SQLite) | `src/audio_enviro_fingerprint/case_store.py` |
| Tests | `tests/test_core.py` |
| Docs | `docs/` (`SPECIFICATIONS.md`, `VALIDATION.md`, `CODE_AUDIT.md`, `BUILDING.md`, `FUTURE_FEATURES.md`) |
