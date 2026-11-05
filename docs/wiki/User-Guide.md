# User Guide

## What you get

For each recording the app gives you:

- the SHA-256 of the original file (computed from the bytes on disk, separate from the features)
- framewise RMS level, spectral centroid, spectral flatness and fixed-band power, in dB
- candidate transitions, which are frames where the features change sharply from one frame to the next
- a fingerprint, a versioned summary of the features, that can be compared with another recording
- an optional RT60 estimate from an impulse response (experimental)

Nothing is changed in the source file. The file is read only, and no downmix is applied.

## Install and run

From source:

```
python -m pip install -e .
python -m audio_enviro_fingerprint
```

On Linux you need the Tk package from your distribution if `tkinter` is missing. Windows and Linux builds are produced by the GitHub Actions workflow (see [[Developer-Build-and-Test]]).

## Open a recording

Click **Open PCM WAV…**. The file must be uncompressed integer PCM WAV with 8, 16, 24 or 32-bit samples. Other formats are rejected. The app analyses channel 1 only.

Analysis uses 2-second frames with a 1-second hop.

## Read the results

- **Framewise values**: one row per frame. Level is RMS in dBFS. Centroid is the spectral centroid in Hz. Flatness is near 0 for tonal sound and near 1 for noise-like sound. Band power is per fixed band (0 to 125 Hz, 125 to 250 Hz and the bands after them).
- **Candidate transitions**: frames where the adjacent-frame difference in one or more features passes the threshold (default 0.35). Each candidate lists the per-feature deltas it was found from. A candidate is a place to look, not a conclusion.
- **Level summary**: a summary of the frame levels, used for the noise figures.

## Compare two recordings

Click **Compare recording…** and pick the second file. The comparison lists each feature difference and gives a descriptive similarity score. The score is exp(-RMS distance), which is uncalibrated. It says how close the measured features are, not how likely the recordings are to match in the real world. The explanation text states the number of features used.

Compare only fingerprints made with the same version (`aefp-1` at present). A version mismatch raises an error.

## Notes and evidence

Use the **Examiner Notes** tab to add a timestamped note with a title and body. Notes are stored in a local SQLite file, and each one is linked to the source SHA-256. The file is hashed again before analysis and before export. If it has changed, the app stops with an error and asks for a stable copy.

## Export

**Export analysis JSON…** writes the evidence path and SHA-256, the analysis (frames, transitions and level summary) and the canonical fingerprint. It refuses to export if the source file no longer matches the hash recorded at import.

## RT60 (experimental)

The Schroeder decay-slope estimate works on impulse responses only. It is not an ISO 3382 measurement workflow. Use the result as a rough indicator, not a certified value.

## Limits

- Integer PCM WAV only. No MP3, FLAC or float WAV.
- The change threshold and the similarity score are not validated on representative datasets.
- The app does not say where a recording was made, and it does not authenticate a file.
- Results need examiner review before anyone relies on them.
