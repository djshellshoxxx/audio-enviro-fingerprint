"""Conservative WAV reader (integer PCM, IEEE float, WAVE_FORMAT_EXTENSIBLE, RF64).

Source bytes are never rewritten. Channel 1 is exposed as ``samples`` for the
single-channel methods; every channel is retained in ``all_channels``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import BinaryIO

import numpy as np

_FMT_PCM, _FMT_FLOAT, _FMT_EXTENSIBLE = 1, 3, 0xFFFE
_MAX_CHUNK_HEADER = 8


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int
    channels: int
    source_width_bytes: int
    all_channels: np.ndarray | None = field(default=None, repr=False, compare=False)
    sample_format: str = "pcm"
    decoder: dict = field(default_factory=lambda: {"name": "aefp-wav", "version": "1"}, compare=False)

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate

    def channel(self, index: int) -> np.ndarray:
        """Return one channel (0-based) as float64 without mixing."""
        if self.all_channels is None:
            if index != 0:
                raise ValueError("Only channel 1 is available")
            return self.samples
        if not 0 <= index < self.all_channels.shape[1]:
            raise ValueError(f"Channel {index + 1} does not exist")
        return self.all_channels[:, index]


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
    if width not in (4, 8):
        raise ValueError(f"Unsupported float sample width: {width * 8}-bit")
    values = np.frombuffer(raw, dtype="<f4" if width == 4 else "<f8").astype(np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("Float WAV contains NaN or infinite samples")
    return values


def _parse_riff(source: BinaryIO, max_decoded_bytes: int) -> tuple[dict, bytes, int]:
    """Read bounded metadata, skipping ancillary chunks before allocating audio."""
    source.seek(0, 2)
    file_size = source.tell()

    def read_at(offset: int, size: int) -> bytes:
        source.seek(offset)
        result = source.read(size)
        if len(result) != size:
            raise ValueError("WAV payload or metadata is truncated")
        return result

    data = read_at(0, min(16, file_size))
    if len(data) < 12 or data[8:12] != b"WAVE" or data[:4] not in (b"RIFF", b"RF64"):
        raise ValueError("Not a RIFF/WAVE file")
    is_rf64 = data[:4] == b"RF64"
    riff_size = struct.unpack_from("<I", data, 4)[0]
    if is_rf64:
        if riff_size != 0xFFFFFFFF or data[12:16] != b"ds64":
            raise ValueError("RF64 requires its size sentinel and initial ds64 chunk")
        container_end = file_size  # Replaced by the checked ds64 size below.
    else:
        container_end = 8 + riff_size
        if riff_size < 4 or container_end > file_size:
            raise ValueError("RIFF container is truncated or has an invalid declared size")
    rf64_data_size = None
    table_next = table_end = 0
    fmt = None
    payload = None
    declared = 0
    pos = 12
    while pos + _MAX_CHUNK_HEADER <= container_end:
        chunk_header = read_at(pos, _MAX_CHUNK_HEADER)
        cid = chunk_header[:4]
        size = struct.unpack_from("<I", chunk_header, 4)[0]
        body = pos + _MAX_CHUNK_HEADER
        if cid == b"ds64" and is_rf64:
            if rf64_data_size is not None or size < 28 or body + size > container_end:
                raise ValueError("Corrupt RF64 ds64 chunk")
            metadata = read_at(body, 28)
            riff_size, data_size, _sample_count = struct.unpack_from("<QQQ", metadata)
            table_length = struct.unpack_from("<I", metadata, 24)[0]
            if size < 28 + 12 * table_length:
                raise ValueError("Truncated RF64 ds64 size table")
            container_end = 8 + riff_size
            if riff_size < 4 or container_end > file_size or body + size > container_end:
                raise ValueError("RF64 container is truncated or has an invalid declared size")
            rf64_data_size = data_size
            table_next = body + 28
            table_end = table_next + 12 * table_length
        if is_rf64 and size == 0xFFFFFFFF:
            if cid == b"data" and rf64_data_size is not None:
                size = rf64_data_size
            else:
                if table_next + 12 > table_end:
                    raise ValueError("RF64 chunk has no ds64 size-table entry")
                entry_id, entry_size = struct.unpack("<4sQ", read_at(table_next, 12))
                if entry_id != cid:
                    raise ValueError("RF64 ds64 size-table chunk order does not match")
                size = entry_size
                table_next += 12
        if body + size > container_end:
            raise ValueError("WAV chunk exceeds the declared RIFF/RF64 container")
        if cid == b"fmt ":
            if size < 16 or body + size > container_end:
                raise ValueError("Corrupt fmt chunk")
            metadata = read_at(body, min(size, 40))
            tag, ch, rate, byte_rate, align, bits = struct.unpack_from("<HHIIHH", metadata)
            if tag == _FMT_EXTENSIBLE:
                if size < 40 or not 22 <= struct.unpack_from("<H", metadata, 16)[0] <= size - 18:
                    raise ValueError("Corrupt WAVE_FORMAT_EXTENSIBLE chunk")
                subtype = metadata[24:40]
                if subtype[4:] != bytes.fromhex("00001000800000aa00389b71"):
                    raise ValueError("Unsupported extensible audio subtype GUID")
                tag = struct.unpack_from("<I", subtype)[0]
                valid_bits = struct.unpack_from("<H", metadata, 18)[0]
                if not 0 < valid_bits <= bits:
                    raise ValueError("Invalid extensible valid-bit count")
            if bits % 8 or align != ch * (bits // 8) or byte_rate != rate * align:
                raise ValueError("Inconsistent WAV block alignment or byte rate")
            fmt = {"tag": tag, "channels": ch, "rate": rate, "bits": bits}
        elif cid == b"data":
            if fmt is None:
                raise ValueError("WAV has no fmt chunk before audio data")
            tag, ch, rate, bits = fmt["tag"], fmt["channels"], fmt["rate"], fmt["bits"]
            if tag not in (_FMT_PCM, _FMT_FLOAT):
                raise ValueError("Only uncompressed PCM or IEEE-float WAV is supported")
            if ch < 1 or rate < 1 or bits < 8 or bits % 8:
                raise ValueError("WAV header describes an unsupported stream")
            width = bits // 8
            if (tag == _FMT_PCM and width not in (1, 2, 3, 4)) or (tag == _FMT_FLOAT and width not in (4, 8)):
                raise ValueError("Unsupported WAV sample width")
            if size % (width * ch):
                raise ValueError("WAV data ends in a partial channel frame")
            if size // width * 8 > max_decoded_bytes:
                raise ValueError("Decoded audio exceeds the configured memory limit")
            declared = size
            payload = read_at(body, size)
            break
        pos = body + size + (size & 1)
    if fmt is None:
        raise ValueError("WAV has no fmt chunk")
    if payload is None:
        raise ValueError("WAV has no data chunk")
    return fmt, payload, declared


def load_wav(path: str | Path, max_decoded_bytes: int = 512 * 1024 * 1024) -> AudioData:
    """Read WAV audio with a bound on decoded float64 bytes across all channels.

    Metadata is read in bounded pieces and ancillary chunks are skipped. The
    limit is checked before reading the audio payload or allocating samples;
    it is not a bound on total process memory or decoder temporary arrays.
    """
    if isinstance(max_decoded_bytes, bool) or not isinstance(max_decoded_bytes, int) or max_decoded_bytes <= 0:
        raise ValueError("Decoded byte limit must be a positive integer")
    path = Path(path)
    if not path.is_file():
        raise ValueError("Audio input must be a regular local file")
    try:
        with path.open("rb") as source:
            fmt, raw, declared = _parse_riff(source, max_decoded_bytes)
    except OSError as exc:
        raise ValueError(f"Unable to read WAV: {exc}") from exc
    channels, rate, bits, tag = fmt["channels"], fmt["rate"], fmt["bits"], fmt["tag"]
    if not raw:
        raise ValueError("WAV contains no analyzable audio frames")
    width = bits // 8
    scalar = _decode_float(raw, width) if tag == _FMT_FLOAT else _decode_pcm(raw, width)
    audio = scalar.reshape(-1, channels)
    # Averaging channels can cancel out-of-phase content. Channel 1 is selected
    # deterministically; the original multichannel file remains untouched.
    return AudioData(audio[:, 0], rate, channels, width, audio,
                     "float" if tag == _FMT_FLOAT else "pcm")


def load_audio(path: str | Path, max_decoded_bytes: int = 512 * 1024 * 1024) -> AudioData:
    """Read WAV natively or supported compressed audio through local FFmpeg.

    The decode limit applies to float64 interleaved sample bytes for all formats.
    Original bytes remain untouched and are hashed by the analysis pipeline.
    """
    if isinstance(max_decoded_bytes, bool) or not isinstance(max_decoded_bytes, int) or max_decoded_bytes <= 0:
        raise ValueError("Decoded byte limit must be a positive integer")
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Audio input must be a regular local file")
    with path.open("rb") as source:
        header = source.read(12)
    if header[:4] in (b"RIFF", b"RF64") or path.suffix.lower() in (".wav", ".wave"):
        return load_wav(path, max_decoded_bytes)
    from .codec_io import decode_compressed
    return decode_compressed(path, max_decoded_bytes)
