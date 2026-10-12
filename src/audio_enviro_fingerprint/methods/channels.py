"""Descriptive per-channel and inter-channel statistics for multichannel review.

These figures describe level, offset and similarity between recorded channels. They do
not localize sources, estimate direction, or establish where a recording was made.
"""
from __future__ import annotations

import numpy as np

from .noise import dbfs, rms_dbfs

SILENCE_FLOOR_DBFS = -240.0


def describe_channels(channel_data: np.ndarray, sample_rate: int) -> dict:
    data = np.asarray(channel_data, dtype=np.float64)
    if data.ndim == 1:
        data = data[:, np.newaxis]
    if data.ndim != 2 or data.shape[0] == 0 or data.shape[1] < 1:
        raise ValueError("Expected channel data shaped (frames, channels) with at least one frame")
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive")
    if not np.all(np.isfinite(data)):
        raise ValueError("Channel data contains non-finite values")
    count = int(data.shape[1])
    per_channel, levels, constant = [], [], []
    for index in range(count):
        column = data[:, index]
        level = rms_dbfs(column)
        levels.append(level)
        constant.append(bool(np.ptp(column) == 0.0))
        per_channel.append({"channel": index, "rms_dbfs": level,
                            "peak_dbfs": dbfs(float(np.max(np.abs(column)))),
                            "dc_offset": float(np.mean(column))})
    # Columns are centered one at a time so long multichannel files are not copied whole.
    means = data.mean(axis=0)

    def centered(index):
        return data[:, index] - means[index]

    norms = [float(np.sqrt(np.dot(column, column))) for column in map(centered, range(count))]
    correlation = [[0.0] * count for _ in range(count)]
    for i in range(count):
        if norms[i] == 0.0:
            continue
        correlation[i][i] = 1.0
        column_i = centered(i) if count > 1 else None
        for j in range(i + 1, count):
            if norms[j] != 0.0:
                value = float(np.clip(np.dot(column_i, centered(j)) / (norms[i] * norms[j]), -1.0, 1.0))
                correlation[i][j] = correlation[j][i] = value
    differences = {f"{i + 1}-{j + 1}": float(levels[i] - levels[j])
                   for i in range(count) for j in range(i + 1, count)}
    notes = ["Descriptive channel statistics only; they do not localize sources or identify a location.",
             "Channel labels in level_difference_db are one-based ('1-2' = channel 1 minus channel 2)."]
    if count == 1:
        notes.append("Mono recording: no inter-channel comparison is possible.")
    silent = [index for index in range(count) if constant[index]]
    if silent:
        notes.append("Constant (silent or DC-only) channel(s) " + ", ".join(str(i + 1) for i in silent)
                     + ": Pearson correlation is undefined and reported as 0.")
    floor_hits = [index for index in range(count) if levels[index] <= SILENCE_FLOOR_DBFS]
    if floor_hits:
        notes.append(f"Digital-silence channels are reported at the {SILENCE_FLOOR_DBFS:g} dBFS floor; "
                     "level differences involving them are not meaningful.")
    if count >= 2 and any(correlation[i][j] < -0.5 for i in range(count) for j in range(i + 1, count)):
        notes.append("Strong negative correlation between channels: averaging them would cancel content.")
    return {"channel_count": count, "per_channel": per_channel, "correlation": correlation,
            "level_difference_db": differences, "notes": notes}
