from dataclasses import replace
import unittest

from audio_enviro_fingerprint.features import analyze_audio
from audio_enviro_fingerprint.fingerprint import make_fingerprint
from test_extended import tone


class FingerprintReproducibilityTests(unittest.TestCase):
    def test_sub_resolution_float_drift_does_not_change_digest(self):
        analysis = analyze_audio(tone(440, 3), 16000)
        shifted = replace(analysis, frames=[replace(frame,
            spectral_centroid_hz=frame.spectral_centroid_hz + 1e-10) for frame in analysis.frames])
        self.assertEqual(make_fingerprint(analysis).fingerprint_hash,
                         make_fingerprint(shifted).fingerprint_hash)
        self.assertEqual(make_fingerprint(analysis).version, 'aefp-2')
