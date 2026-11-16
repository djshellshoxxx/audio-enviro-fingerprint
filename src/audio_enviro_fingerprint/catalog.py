"""Deterministic complete-link grouping of measured recording descriptors.

Groups are review aids. They do not attribute a room, microphone or recorder.
"""
from __future__ import annotations

import math
from pathlib import Path

from .comparison import compare_fingerprints
from .control import check_cancelled
from .pipeline import analyze_file

METHOD = 'aefp-catalog-complete-link-1'


def cluster_recordings(paths, max_distance: float = 0.25, *, cancel_event=None) -> dict:
    """Cluster up to 64 unique local recordings with all pair explanations.

    Distance is 1 minus the existing uncalibrated descriptive similarity.
    Complete-link merges only when every pair across groups meets the threshold,
    avoiding chains of individually similar files joining dissimilar endpoints.
    """
    if not math.isfinite(max_distance) or not 0 <= max_distance <= 1:
        raise ValueError('Cluster distance must be finite and in [0, 1]')
    paths = sorted(Path(p).resolve(strict=True) for p in paths)
    if not 1 <= len(paths) <= 64 or len(set(paths)) != len(paths):
        raise ValueError('Supply 1 to 64 unique recording paths')
    should_cancel = cancel_event.is_set if cancel_event is not None else None
    recordings = []
    fingerprints = []
    for path in paths:
        check_cancelled(should_cancel)
        result = analyze_file(path, musical=False, cancel_event=cancel_event)
        fp = result['fingerprint']
        fingerprints.append({'version': fp.version, 'features': fp.features})
        recordings.append({'path': str(path), 'sha256': result['sha256'],
                           'fingerprint_sha256': fp.fingerprint_hash,
                           'fingerprint_version': fp.version, 'features': fp.features,
                           'decoder': result['audio'].decoder})
        del result  # Do not retain decoded audio for the entire catalog.
    distances, comparisons = {}, []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            check_cancelled(should_cancel)
            comparison = compare_fingerprints(fingerprints[i], fingerprints[j])
            distance = 1.0 - comparison.score
            distances[i, j] = distance
            comparisons.append({'first': i, 'second': j, 'distance': distance,
                                'method': comparison.method, 'differences': comparison.differences,
                                'explanation': comparison.explanation})
    groups = [[i] for i in range(len(paths))]
    while len(groups) > 1:
        check_cancelled(should_cancel)
        candidates = []
        for i, a in enumerate(groups):
            for j in range(i + 1, len(groups)):
                distance = max(distances[min(x, y), max(x, y)] for x in a for y in groups[j])
                candidates.append((distance, i, j))
        distance, i, j = min(candidates)
        if distance > max_distance:
            break
        groups[i] = sorted(groups[i] + groups[j])
        del groups[j]
    return {'method': METHOD, 'max_distance': max_distance, 'recordings': recordings,
            'groups': sorted(groups), 'comparisons': comparisons,
            'limitations': ['Distance and threshold are uncalibrated, not probabilities.',
                            'Groups do not identify a physical room or recording device.',
                            'Shared sources, gain, codecs and microphone differences confound grouping.']}
