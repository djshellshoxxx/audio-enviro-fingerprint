"""Optional local FFmpeg decoder; retains original evidence and decoder provenance."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np

from .audio_io import AudioData

# Disallow playlist/network demuxers and protocols. The first audio stream is
# selected explicitly; there is no implicit downmix or sample-rate conversion.
_FORMATS = 'flac,mp3,ogg,mov'
_CODECS = {'flac', 'mp3', 'vorbis', 'opus', 'aac', 'alac'}


def decode_compressed(path: Path, max_decoded_bytes: int) -> AudioData:
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise ValueError('Compressed audio requires ffmpeg and ffprobe on PATH; WAV needs neither')
    restrictions = ['-protocol_whitelist', 'file,pipe', '-format_whitelist', _FORMATS]
    try:
        probe = subprocess.run([ffprobe, '-v', 'error', *restrictions,
                                '-select_streams', 'a:0', '-show_entries',
                                'stream=codec_name,sample_rate,channels,index', '-of', 'json', str(path)],
                               capture_output=True, timeout=30, check=True)
        streams = json.loads(probe.stdout).get('streams', [])
        if not streams:
            raise ValueError('No audio stream in recording')
        stream = streams[0]
        rate, channels = int(stream['sample_rate']), int(stream['channels'])
        codec = stream['codec_name']
        if codec not in _CODECS or not 1 <= channels <= 64 or not 1 <= rate <= 768000:
            raise ValueError('Unsupported compressed audio stream')
        version = subprocess.run([ffmpeg, '-version'], capture_output=True, timeout=10,
                                 check=True).stdout.decode('utf-8', errors='replace').splitlines()[0]
        with tempfile.TemporaryDirectory(prefix='aefp-decode-') as tmp:
            decoded = Path(tmp) / 'decoded.f64'
            command = [ffmpeg, '-nostdin', '-v', 'error', '-xerror', *restrictions,
                       '-i', str(path), '-map', '0:a:0', '-vn', '-sn', '-dn',
                       '-c:a', 'pcm_f64le', '-f', 'f64le', '-fs', str(max_decoded_bytes + 1), str(decoded)]
            subprocess.run(command, capture_output=True, timeout=300, check=True)
            size = decoded.stat().st_size
            if size >= max_decoded_bytes:
                raise ValueError('Decoded audio exceeds the configured memory limit')
            if not size or size % (8 * channels):
                raise ValueError('Decoder returned empty or partial audio frames')
            samples = np.fromfile(decoded, dtype='<f8').reshape(-1, channels)
        if not np.all(np.isfinite(samples)):
            raise ValueError('Decoded audio contains nonfinite samples')
        provenance = {'name': 'ffmpeg', 'version': version, 'codec': codec,
                      'stream_index': stream['index'], 'output_format': 'f64le',
                      'sample_rate_conversion': False, 'downmix': False,
                      'max_decoded_bytes': max_decoded_bytes}
        return AudioData(samples[:, 0], rate, channels, 8, samples, 'decoded_float', provenance)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Audio decoder exceeded its time limit') from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b'').decode('utf-8', errors='replace')[-1000:]
        raise ValueError(f'Audio decoder rejected the recording: {detail}') from exc
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid audio decoder metadata') from exc
