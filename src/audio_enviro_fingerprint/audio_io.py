"""Conservative audio readers with decoder provenance. Source bytes are never rewritten.

Plain integer PCM WAV is read with the standard-library ``wave`` module. IEEE-float and
WAVE_FORMAT_EXTENSIBLE WAV are read by a small self-contained RIFF parser so packaged
builds do not need a third-party decoder for WAV. Other containers (FLAC, AIFF, OGG,
MP3, RF64, W64) use the optional ``soundfile`` package, imported lazily.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import platform
import struct
import wave

import numpy as np

SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".wav", ".wave", ".bwf", ".flac", ".aif", ".aiff", ".aifc",
    ".ogg", ".oga", ".opus", ".mp3", ".rf64", ".w64")

LOSSY_NOTE = ("Lossy codec: perceptual coding alters spectral detail, noise floor and "
              "band levels; spectral/noise features are not comparable with lossless sources.")

_WAVE_FORMAT_PCM = 0x0001
_WAVE_FORMAT_IEEE_FLOAT = 0x0003
_WAVE_FORMAT_EXTENSIBLE = 0xFFFE
# KSDATAFORMAT_SUBTYPE_* GUID tail shared by PCM (0x0001) and IEEE float (0x0003).
_GUID_TAIL = b"\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
_LOSSY_SUBTYPES = {"VORBIS", "OPUS", "MPEG_LAYER_I", "MPEG_LAYER_II", "MPEG_LAYER_III"}
_LOSSY_FORMATS = {"OGG", "MP3", "MPEG"}
_SUBTYPE_WIDTH = {"PCM_S8": 1, "PCM_U8": 1, "PCM_16": 2, "PCM_24": 3, "PCM_32": 4}


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int
    channels: int
    source_width_bytes: int
    channel_data: np.ndarray | None = None
    selected_channel: int = 0
    decoder: dict = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate

    def channel(self, index: int) -> np.ndarray:
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
            raise ValueError("Channel index must be an integer")
        if self.channel_data is None:
            if index != self.selected_channel:
                raise ValueError(f"Channel {index} is not available (only the selected channel was retained)")
            return self.samples
        if not 0 <= index < self.channel_data.shape[1]:
            raise ValueError(f"Channel index {index} out of range for {self.channel_data.shape[1]}-channel audio")
        return self.channel_data[:, index]


def soundfile_available() -> bool:
    try:
        import soundfile  # noqa: F401
    except Exception:  # ImportError, or OSError when libsndfile is missing
        return False
    return True


def _decode_pcm(raw: bytes, width: int) -> np.ndarray:
    if width == 1:
        return (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    if width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if width == 3:
        octets = np.frombuffer(raw, dtype=np.uint8)
        if len(octets) % 3:
            raise ValueError("Truncated 24-bit PCM sample data")
        triples = octets.reshape(-1, 3).astype(np.int32)
        values = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
        values = (values ^ 0x800000) - 0x800000
        return values.astype(np.float64) / 8388608.0
    if width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    raise ValueError(f"Unsupported PCM sample width: {width * 8}-bit")


def _decode_float(raw: bytes, width: int) -> np.ndarray:
    if width == 4:
        return np.frombuffer(raw, dtype="<f4").astype(np.float64)
    if width == 8:
        return np.frombuffer(raw, dtype="<f8").astype(np.float64)
    raise ValueError(f"Unsupported IEEE-float sample width: {width * 8}-bit")


def _finish(audio: np.ndarray, rate: int, width: int, channel: int, decoder: dict) -> AudioData:
    """Validate decoded (frames, channels) data and build AudioData for one channel."""
    if audio.ndim != 2 or audio.shape[0] == 0 or audio.shape[1] < 1 or rate < 1:
        raise ValueError("Audio contains no analyzable frames")
    if not np.all(np.isfinite(audio)):
        raise ValueError("Audio contains non-finite sample values (NaN or infinity)")
    channels = int(audio.shape[1])
    if isinstance(channel, bool) or not isinstance(channel, (int, np.integer)):
        raise ValueError("Channel index must be an integer")
    if not 0 <= channel < channels:
        raise ValueError(f"Channel index {channel} out of range for {channels}-channel audio "
                         f"(valid: 0-{channels - 1})")
    audio = np.ascontiguousarray(audio, dtype=np.float64)
    if decoder.get("encoding", "").startswith("float") and float(np.max(np.abs(audio))) > 1.0:
        decoder.setdefault("notes", []).append("Float samples exceed full scale (|x| > 1.0); values kept unclipped.")
    # Averaging channels can cancel out-of-phase content. One channel is selected
    # deterministically; all channels are retained and the original file is untouched.
    # A mono column is already contiguous; copying it would double peak memory for long files.
    selected = audio[:, channel] if channels == 1 else audio[:, channel].copy()
    return AudioData(selected, int(rate), channels, int(width), audio,
                     int(channel), decoder)


def _riff_chunks(path: Path) -> tuple[bytes, dict]:
    """Return (fmt chunk, data chunk location) from a RIFF/WAVE file without reading samples."""
    total = path.stat().st_size
    with path.open("rb") as handle:
        header = handle.read(12)
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise ValueError("Not a RIFF/WAVE file")
        fmt = None
        position = 12
        while position + 8 <= total:
            handle.seek(position)
            chunk_id, size = struct.unpack("<4sI", handle.read(8))
            body_start = position + 8
            if chunk_id == b"fmt ":
                fmt = handle.read(size)
                if len(fmt) < size:
                    raise ValueError("WAV fmt chunk is truncated")
            elif chunk_id == b"data":
                if fmt is None:
                    raise ValueError("WAV data chunk precedes fmt chunk")
                return fmt, {"offset": body_start, "declared": size,
                             "available": max(0, min(size, total - body_start))}
            position = body_start + size + (size & 1)
    if fmt is None:
        raise ValueError("WAV has no fmt chunk")
    raise ValueError("WAV has no data chunk")


def _wave_format(fmt: bytes) -> tuple[int, int, int, int, int]:
    """Return (base format tag, channels, rate, container width bytes, valid bits)."""
    if len(fmt) < 16:
        raise ValueError("WAV fmt chunk is too short")
    tag, channels, rate, _, block_align, bits = struct.unpack_from("<HHIIHH", fmt, 0)
    valid_bits = bits
    if tag == _WAVE_FORMAT_EXTENSIBLE:
        if len(fmt) < 40:
            raise ValueError("WAVE_FORMAT_EXTENSIBLE fmt chunk is too short")
        valid_bits = struct.unpack_from("<H", fmt, 18)[0] or bits
        guid = fmt[24:40]
        if guid[2:] != _GUID_TAIL:
            raise ValueError("Unsupported WAVE_FORMAT_EXTENSIBLE sub-format")
        tag = struct.unpack_from("<H", guid, 0)[0]
    if channels < 1 or rate < 1 or bits < 1 or bits % 8:
        raise ValueError("WAV fmt chunk declares an invalid layout")
    width = bits // 8
    if block_align != width * channels:
        raise ValueError("WAV block alignment is inconsistent with channels and sample width")
    return tag, channels, rate, width, valid_bits


def _read_wav_stdlib(path: Path, channel: int) -> AudioData:
    try:
        with wave.open(str(path), "rb") as source:
            if source.getcomptype() != "NONE":
                raise ValueError("Only uncompressed PCM WAV is supported in this beta")
            channels = source.getnchannels()
            width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.getnframes()
            raw = source.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"Unable to read PCM WAV: {exc}") from exc
    if channels < 1 or rate < 1 or not raw:
        raise ValueError("WAV contains no analyzable audio frames")
    expected_bytes = frames * channels * width
    if len(raw) != expected_bytes:
        raise ValueError("WAV payload is truncated or inconsistent with its declared frame count")
    scalar = _decode_pcm(raw, width)
    if len(scalar) % channels:
        raise ValueError("WAV data ends in a partial channel frame")
    decoder = {"backend": "stdlib-wave", "backend_version": platform.python_version(),
               "container": "WAV", "encoding": f"pcm_s{width * 8}" if width > 1 else "pcm_u8",
               "lossy": False, "notes": []}
    return _finish(scalar.reshape(-1, channels), rate, width, channel, decoder)


def _read_wav_riff(path: Path, fmt: bytes, chunk: dict, channel: int) -> AudioData:
    tag, channels, rate, width, valid_bits = _wave_format(fmt)
    if chunk["available"] != chunk["declared"]:
        raise ValueError("WAV payload is truncated or inconsistent with its declared data size")
    with path.open("rb") as handle:
        handle.seek(chunk["offset"])
        payload = handle.read(chunk["declared"])
    if not payload:
        raise ValueError("WAV contains no analyzable audio frames")
    if len(payload) % (width * channels):
        raise ValueError("WAV data ends in a partial channel frame")
    extensible = struct.unpack_from("<H", fmt, 0)[0] == _WAVE_FORMAT_EXTENSIBLE
    notes = ["WAVE_FORMAT_EXTENSIBLE header"] if extensible else []
    if tag == _WAVE_FORMAT_PCM:
        scalar = _decode_pcm(payload, width)
        encoding = f"pcm_s{width * 8}" if width > 1 else "pcm_u8"
        if valid_bits != width * 8:
            notes.append(f"{valid_bits} valid bits in a {width * 8}-bit container")
        source_width = width
    elif tag == _WAVE_FORMAT_IEEE_FLOAT:
        scalar = _decode_float(payload, width)
        encoding = f"float{width * 8}"
        source_width = 0
    else:
        raise ValueError(f"Unsupported WAV format tag 0x{tag:04X}; only PCM and IEEE float are supported")
    decoder = {"backend": "riff-numpy", "backend_version": np.__version__, "container": "WAV",
               "encoding": encoding, "lossy": False, "notes": notes}
    return _finish(scalar.reshape(-1, channels), rate, source_width, channel, decoder)


def _read_wav(path: Path, channel: int) -> AudioData:
    try:
        fmt, chunk = _riff_chunks(path)
        tag = struct.unpack_from("<H", fmt, 0)[0] if len(fmt) >= 2 else -1
    except (ValueError, struct.error, OSError) as exc:
        raise ValueError(f"Unable to read WAV: {exc}") from exc
    if tag == _WAVE_FORMAT_PCM:
        return _read_wav_stdlib(path, channel)
    if tag in (_WAVE_FORMAT_IEEE_FLOAT, _WAVE_FORMAT_EXTENSIBLE):
        return _read_wav_riff(path, fmt, chunk, channel)
    raise ValueError(f"Only uncompressed PCM or IEEE-float WAV is supported (format tag 0x{tag:04X})")


def load_wav(path: str | Path, channel: int = 0) -> AudioData:
    """Read PCM / IEEE-float / extensible WAV and select one channel without downmixing."""
    return _read_wav(Path(path), channel)


def _read_soundfile(path: Path, channel: int) -> AudioData:
    if not soundfile_available():
        raise ValueError(f"Reading {path.suffix or 'this'} files requires the optional 'soundfile' "
                         "package (pip install soundfile); only WAV is supported without it")
    import soundfile
    try:
        info = soundfile.info(str(path))
        audio = soundfile.read(str(path), dtype="float64", always_2d=True)[0]
    except Exception as exc:  # soundfile raises LibsndfileError / RuntimeError variants
        raise ValueError(f"Unable to decode audio with soundfile: {exc}") from exc
    container, subtype = str(info.format).upper(), str(info.subtype).upper()
    lossy = container in _LOSSY_FORMATS or subtype in _LOSSY_SUBTYPES
    notes = [LOSSY_NOTE] if lossy else []
    if info.frames and audio.shape[0] != info.frames:
        notes.append(f"Decoded {audio.shape[0]} frames; header declared {info.frames}")
    decoder = {"backend": "soundfile",
               "backend_version": f"soundfile {soundfile.__version__}; "
                                  f"libsndfile {getattr(soundfile, '__libsndfile_version__', 'unknown')}",
               "container": container, "encoding": subtype.lower(), "lossy": lossy, "notes": notes}
    if subtype in ("FLOAT", "DOUBLE"):
        decoder["encoding"] = "float32" if subtype == "FLOAT" else "float64"
    return _finish(audio, int(info.samplerate), _SUBTYPE_WIDTH.get(subtype, 0), channel, decoder)


def load_audio(path: str | Path, channel: int = 0) -> AudioData:
    """Read an audio file, keep all channels, and select ``channel`` (zero-based) for analysis.

    The container is identified from the file's leading bytes, not its extension.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            head = handle.read(12)
    except OSError as exc:
        raise ValueError(f"Unable to open audio file: {exc}") from exc
    if len(head) < 12:
        raise ValueError("File is too short to be an audio file")
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return _read_wav(path, channel)
    return _read_soundfile(path, channel)
