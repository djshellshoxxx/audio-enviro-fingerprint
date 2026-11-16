import unittest
import numpy as np

from audio_enviro_fingerprint.methods.quality import review_quality
from audio_enviro_fingerprint.reference import ReferenceMetadata, review_reference


class QualityTests(unittest.TestCase):
    def test_flags_dropouts_and_dc_offset(self):
        signal = np.concatenate([np.zeros(16000 * 5), np.full(16000, 0.1)])
        result = review_quality(signal, 16000)
        checks = {c['check']: c for c in result['checks']}
        self.assertEqual(checks['silence_fraction']['status'], 'fail')
        self.assertEqual(checks['dc_offset']['status'], 'warn')
        self.assertIn('silence_fraction', {c['check'] for c in review_reference(
            ReferenceMetadata(), signal, 16000)['checks']})

    def test_rejects_nonfinite_samples(self):
        with self.assertRaises(ValueError):
            review_quality(np.array([0.0, float('nan')]), 16000)
