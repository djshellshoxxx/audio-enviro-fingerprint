# Audio input, channels and decoder provenance

## Supported inputs

| Input | Reader | Notes |
|---|---|---|
| Integer PCM WAV (8/16/24/32-bit) | Python `wave` (stdlib) | Declared frame count is checked against the payload; truncation is rejected. |
| IEEE-float WAV (32/64-bit) | Built-in RIFF parser (NumPy) | Values above full scale are kept unclipped and noted. |
| `WAVE_FORMAT_EXTENSIBLE` PCM/float WAV | Built-in RIFF parser | Valid-bits narrower than the container are noted. |
| FLAC, AIFF/AIFC, OGG/Vorbis/Opus, MP3, RF64, W64 | Optional `soundfile` (libsndfile) | Installed with `pip install ".[formats]"` and bundled in packaged builds. Without it, non-WAV input is rejected with a clear message. |

The container is identified from the file's leading bytes, not its extension. Empty audio, non-finite samples, inconsistent block alignment, unknown format tags and partial frames are rejected with `ValueError`; the source file is never modified.

## Channels

All channels are decoded and retained (`AudioData.channel_data`, shape `(frames, channels)`). One channel (zero-based `channel`, shown one-based in the UI) is selected for analysis. Channels are never averaged, because anti-phase content would cancel. The **Channels** view and report `channel_summary` give per-channel RMS, peak and DC offset, pairwise Pearson correlation and level differences (`methods/channels.py`). These are descriptive statistics only. They do not localize sources or estimate direction. Constant (silent) channels report correlation 0 with a note.

## Decoder provenance

Every `AudioData.decoder` (and report `audio.decoder`) records:

- `backend`: `stdlib-wave`, `riff-numpy` or `soundfile`
- `backend_version`: the Python, NumPy or soundfile/libsndfile version
- `container` and `encoding` (e.g. `WAV` / `pcm_s24`, `FLAC` / `pcm_16`)
- `lossy`: true for MP3, Vorbis and Opus
- `notes`: header/frame-count discrepancies, extensible headers, over-range floats, and the lossy-codec warning

Lossy coding alters spectral detail, noise floor and band levels. Features from lossy sources are not comparable with lossless sources, and the Compare view warns when either side is lossy. Decoding differences between libsndfile versions are possible. Record the backend version with any result you rely on.

## Performance

Decoding is in memory. Analysis runs on a worker thread with progress reporting and cancellation (`analyze_audio(progress=..., cancel=...)`). A cancelled or failed analysis keeps the previous result on screen. Streaming decode for very long recordings remains future work.
