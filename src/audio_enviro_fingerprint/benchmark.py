"""Deterministic synthetic software benchmark.

LABEL: synthetic software benchmark, not forensic validation.

Simulated "rooms" are coloured noise beds with a resonance and optional mains
hum, convolved with a synthetic exponentially decaying impulse response. The
benchmark checks that the analysis pipeline behaves sensibly on signals whose
ground truth is known by construction. Results say nothing about error rates
on real recordings; see docs/BENCHMARK_PROTOCOL.md for the real-data protocol.
"""
from __future__ import annotations

from itertools import combinations
import math

import numpy as np

from .comparison import compare_fingerprints
from .features import analyze_audio
from .fingerprint import make_fingerprint
from .recurrence import find_recurrences
from .transitions import detect_transitions

LABEL = "synthetic software benchmark, not forensic validation"
BENCHMARK_VERSION = "aefp-bench-2"
CAVEATS = (
    "Signals are synthetic; real rooms, devices, codecs and human activity are far more variable.",
    "Scores and thresholds measured here must not be quoted as forensic error rates.",
    "Validation requires a representative, preregistered real-recording dataset (docs/BENCHMARK_PROTOCOL.md).",
)
COMPARISON_THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
TRANSITION_THRESHOLDS = (0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.45, 0.6)
RECURRENCE_THRESHOLDS = (0.1, 0.15, 0.25, 0.35, 0.5)
DEFAULT_TRANSITION_THRESHOLD = 0.35
DEFAULT_RECURRENCE_DISTANCE = 0.25


def _config(quick: bool) -> dict:
    if quick:
        return {"sample_rate": 8000, "rooms": 6, "repeats": 3, "recording_seconds": 12.0,
                "transition_recordings": 4, "segment_seconds": 14.0, "frame_seconds": 2.0,
                "hop_seconds": 1.0, "tolerance_seconds": 2.0}
    return {"sample_rate": 16000, "rooms": 12, "repeats": 4, "recording_seconds": 30.0,
            "transition_recordings": 16, "segment_seconds": 20.0, "frame_seconds": 2.0,
            "hop_seconds": 1.0, "tolerance_seconds": 2.0}


def make_room(rng: np.random.Generator, index: int) -> dict:
    return {"room_id": f"room-{index + 1}", "tilt": float(rng.uniform(0.0, 2.0)),
            "level_dbfs": float(rng.uniform(-50.0, -25.0)), "rt60_seconds": float(rng.uniform(0.2, 1.2)),
            "resonance_hz": float(rng.uniform(150.0, 3000.0)), "resonance_gain_db": float(rng.uniform(0.0, 15.0)),
            "hum_hz": float(rng.choice([0.0, 50.0, 60.0, 100.0, 120.0])),
            "hum_db": float(rng.uniform(-20.0, -3.0)), "ir_seed": int(rng.integers(0, 2 ** 31 - 1))}


def _impulse_response(room: dict, sample_rate: int) -> np.ndarray:
    rng = np.random.default_rng(room["ir_seed"])
    length = max(16, int(min(room["rt60_seconds"], 1.5) * sample_rate))
    t = np.arange(length) / sample_rate
    ir = rng.standard_normal(length) * np.exp(-6.907755 * t / room["rt60_seconds"]) * 0.3
    ir[0] = 1.0
    return ir / math.sqrt(float(np.sum(ir * ir)))


def render(room: dict, seconds: float, sample_rate: int, rng: np.random.Generator, gain_db: float = 0.0,
           events: int = 0, bandlimit_hz: float | None = None) -> np.ndarray:
    """One noise-bed realization of a room; events are short foreground bursts."""
    n = int(round(seconds * sample_rate))
    freqs = np.fft.rfftfreq(n, 1 / sample_rate)
    spectrum = np.fft.rfft(rng.standard_normal(n))
    shape = 1.0 / np.maximum(freqs, 20.0) ** (room["tilt"] / 2)
    octaves = np.log2(np.maximum(freqs, 1.0) / room["resonance_hz"])
    shape *= 1.0 + (10 ** (room["resonance_gain_db"] / 20) - 1) * np.exp(-0.5 * (octaves / 0.25) ** 2)
    dry = np.fft.irfft(spectrum * shape, n)
    dry /= math.sqrt(float(np.mean(dry * dry)))
    t = np.arange(n) / sample_rate
    if room["hum_hz"]:
        dry += math.sqrt(2) * 10 ** (room["hum_db"] / 20) * np.sin(2 * math.pi * room["hum_hz"] * t + rng.uniform(0, 6.28))
    for _ in range(events):
        length = int(0.3 * sample_rate)
        start = int(rng.integers(0, max(1, n - length)))
        burst = rng.standard_normal(length) * np.hanning(length) * 10 ** (12 / 20)
        burst += 3 * np.sin(2 * math.pi * rng.uniform(300, 2500) * np.arange(length) / sample_rate) * np.hanning(length)
        dry[start:start + length] += burst[: n - start]
    ir = _impulse_response(room, sample_rate)
    size = 1 << int(math.ceil(math.log2(n + ir.size)))
    wet = np.fft.irfft(np.fft.rfft(dry, size) * np.fft.rfft(ir, size), size)[:n]
    if bandlimit_hz:
        wet_spectrum = np.fft.rfft(wet)
        wet_spectrum[freqs > bandlimit_hz] = 0
        wet = np.fft.irfft(wet_spectrum, n)
    wet *= 10 ** ((room["level_dbfs"] + gain_db) / 20) / math.sqrt(float(np.mean(wet * wet)))
    return wet


def _fingerprint(samples: np.ndarray, cfg: dict) -> dict:
    analysis = analyze_audio(samples, cfg["sample_rate"], cfg["frame_seconds"], cfg["hop_seconds"])
    fp = make_fingerprint(analysis)
    return {"version": fp.version, "features": fp.features}


def roc_auc(positives: list[float], negatives: list[float]) -> float:
    """Probability a positive scores above a negative (ties count half)."""
    if not positives or not negatives:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return float(wins / (len(positives) * len(negatives)))


def _summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    data = np.asarray(values, dtype=np.float64)
    return {"n": int(data.size), "min": float(data.min()), "p25": float(np.percentile(data, 25)),
            "median": float(np.median(data)), "mean": float(data.mean()),
            "p75": float(np.percentile(data, 75)), "max": float(data.max())}


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "true_positives": tp,
            "false_positives": fp, "false_negatives": fn}


def match_events(detected: list[float], truth: list[float], tolerance: float) -> tuple[int, int, int]:
    """Greedy one-to-one matching of detected to true boundaries within tolerance."""
    unmatched = list(truth)
    tp = 0
    for time in sorted(detected):
        best = min(unmatched, key=lambda t: abs(t - time), default=None)
        if best is not None and abs(best - time) <= tolerance:
            unmatched.remove(best)
            tp += 1
    return tp, len(detected) - tp, len(unmatched)


def _comparison_benchmark(rooms: list[dict], cfg: dict, rng: np.random.Generator) -> dict:
    rate, seconds = cfg["sample_rate"], cfg["recording_seconds"]
    recordings = []
    for room in rooms:
        for _ in range(cfg["repeats"]):
            samples = render(room, seconds, rate, rng, gain_db=float(rng.uniform(-2, 2)), events=1)
            recordings.append((room["room_id"], _fingerprint(samples, cfg)))
    same, different = [], []
    for (room_a, fp_a), (room_b, fp_b) in combinations(recordings, 2):
        (same if room_a == room_b else different).append(compare_fingerprints(fp_a, fp_b).score)
    confounded = {"gain_plus_10db": [], "bandlimit_2khz": [], "foreground_events_x6": []}
    for room in rooms:
        reference = next(fp for room_id, fp in recordings if room_id == room["room_id"])
        variants = {"gain_plus_10db": render(room, seconds, rate, rng, gain_db=10.0, events=1),
                    "bandlimit_2khz": render(room, seconds, rate, rng, events=1, bandlimit_hz=2000.0),
                    "foreground_events_x6": render(room, seconds, rate, rng, events=6)}
        for name, samples in variants.items():
            confounded[name].append(compare_fingerprints(reference, _fingerprint(samples, cfg)).score)
    all_confounded = [score for values in confounded.values() for score in values]
    sweep = [{"threshold": t,
              "true_positive_rate": sum(s >= t for s in same) / len(same),
              "false_positive_rate": sum(s >= t for s in different) / len(different),
              "confounded_same_room_acceptance": sum(s >= t for s in all_confounded) / len(all_confounded)}
             for t in COMPARISON_THRESHOLDS]
    return {"same_room_pairs": _summary(same), "different_room_pairs": _summary(different),
            "confounded_same_room_pairs": {name: _summary(values) for name, values in confounded.items()},
            "roc_auc": roc_auc(same, different),
            "roc_auc_confounded_vs_different": roc_auc(all_confounded, different),
            "threshold_sweep": sweep}


def _sequence(rooms: list[dict], count: int, rng: np.random.Generator) -> list[int]:
    order = [int(rng.integers(0, len(rooms)))]
    while len(order) < count:
        choice = int(rng.integers(0, len(rooms)))
        if choice != order[-1]:
            order.append(choice)
    return order


def _transition_benchmark(rooms: list[dict], cfg: dict, rng: np.random.Generator) -> dict:
    rate, seg = cfg["sample_rate"], cfg["segment_seconds"]
    cases = []
    for index in range(cfg["transition_recordings"]):
        order = _sequence(rooms, 3 + index % 2, rng)
        parts = []
        for room_index in order:
            part = render(rooms[room_index], seg, rate, rng, events=1)
            if index % 2:  # gain-step confounder inside the segment; not an environment change
                part[len(part) // 2:] *= 10 ** (6 / 20)
            parts.append(part)
        truth = [seg * k for k in range(1, len(order))]
        analysis = analyze_audio(np.concatenate(parts), rate, cfg["frame_seconds"], cfg["hop_seconds"])
        cases.append((analysis, truth))
    sweep = []
    for threshold in TRANSITION_THRESHOLDS:
        tp = fp = fn = 0
        for analysis, truth in cases:
            detected = [e.timestamp_seconds for e in detect_transitions(analysis, threshold, 3.0)]
            a, b, c = match_events(detected, truth, cfg["tolerance_seconds"])
            tp, fp, fn = tp + a, fp + b, fn + c
        sweep.append({"threshold": threshold, **_prf(tp, fp, fn)})
    at_default = next(item for item in sweep if item["threshold"] == DEFAULT_TRANSITION_THRESHOLD)
    best = max(sweep, key=lambda item: (item["f1"], -item["threshold"]))
    return {"recordings": len(cases), "true_boundaries": sum(len(t) for _, t in cases),
            "tolerance_seconds": cfg["tolerance_seconds"], "minimum_separation_seconds": 3.0,
            "default_threshold": DEFAULT_TRANSITION_THRESHOLD, "at_default": at_default,
            "best_f1_threshold_on_synthetic_data": best["threshold"], "threshold_sweep": sweep,
            "confounders": "half the recordings contain a +6 dB gain step that is not an environment change"}


def _recurrence_benchmark(rooms: list[dict], cfg: dict, rng: np.random.Generator) -> dict:
    """Candidate-window coverage on positive ABA and negative ABC/CB plans.

    Coverage is not a calibrated error rate. A candidate counts as a return only
    if at least 80 percent of its later span overlaps the constructed A return.
    """
    rate, seg = cfg["sample_rate"], cfg["segment_seconds"]
    a, b, c = rooms[:3]
    plans = {"ABA": [a, b, a], "ABC": [a, b, c], "CB": [c, b]}
    analyses = {}
    for name, plan in plans.items():
        samples = np.concatenate([render(room, seg, rate, rng, events=1) for room in plan])
        analyses[name] = analyze_audio(samples, rate, cfg["frame_seconds"], cfg["hop_seconds"])
    sweep = []
    for threshold in RECURRENCE_THRESHOLDS:
        cases = []
        for name, analysis in analyses.items():
            candidates = find_recurrences(analysis, threshold=threshold)
            true_windows = 0
            for candidate in candidates:
                overlap = max(0.0, min(candidate.later_end_s, 3 * seg) - max(candidate.later_start_s, 2 * seg))
                if name == "ABA" and overlap >= 0.8 * (candidate.later_end_s - candidate.later_start_s):
                    true_windows += 1
            cases.append({"plan": name, "candidate_windows": len(candidates),
                          "return_windows": true_windows,
                          "other_windows": len(candidates) - true_windows,
                          "expected_return_interval": [2 * seg, 3 * seg] if name == "ABA" else None})
        sweep.append({"max_distance": threshold, "cases": cases})
    return {"threshold_sweep": sweep,
            "interpretation": "Synthetic candidate-window overlap only; not field precision or recall."}


def run_benchmark(seed: int = 0, quick: bool = False) -> dict:
    """Run every synthetic scenario; identical seed and mode give identical output."""
    cfg = _config(quick)
    rng = np.random.default_rng(seed)
    rooms = [make_room(rng, index) for index in range(cfg["rooms"])]
    return {"label": LABEL, "benchmark_version": BENCHMARK_VERSION, "seed": int(seed), "quick": bool(quick),
            "parameters": cfg, "rooms": rooms,
            "comparison": _comparison_benchmark(rooms, cfg, np.random.default_rng([seed, 1])),
            "transitions": _transition_benchmark(rooms, cfg, np.random.default_rng([seed, 2])),
            "recurrence": _recurrence_benchmark(rooms, cfg, np.random.default_rng([seed, 3])),
            "caveats": list(CAVEATS)}


def format_summary(result: dict) -> str:
    import json
    return result["label"].upper() + "\n" + json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
