# Architecture Summary

From the README and the source layout.

- **Evidence separation.** The original file's SHA-256 is kept apart from the acoustic feature fingerprint (README).
- **Read-only source.** The file is read only, with channel 1 used for analysis and no downmix (README).
- **Feature methods.** `methods/` holds noise, reverberation and spectral descriptors; `features.py` assembles framewise features (RMS, spectral centroid, flatness, fixed-band power).
- **Transitions and comparison.** `transitions.py` marks candidate change points from adjacent-frame differences; `comparison.py` compares two fingerprints with an explicitly uncalibrated score.
- **Local storage.** `case_store.py` stores timestamped notes linked to the evidence hash in SQLite (README).
- **Integrity and audio I/O.** `integrity.py` and `audio_io.py` handle hashing and WAV reading.
- **GUI.** `app.py` (Tk).
