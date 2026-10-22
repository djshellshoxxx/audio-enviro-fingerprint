"""Acquisition review checks provenance values rather than field presence alone."""
from pathlib import Path
import tempfile
import unittest

import numpy as np

from audio_enviro_fingerprint.case_store import CaseStore
from audio_enviro_fingerprint.reference import REQUIRED, ReferenceMetadata, review_reference


class AcquisitionValidationTests(unittest.TestCase):
    def metadata(self):
        metadata = ReferenceMetadata(**{field: 'documented' for field in REQUIRED})
        metadata.recorded_utc = '2026-10-22T12:00:00Z'
        metadata.height_m = '1.2'
        metadata.repeat_number = metadata.repeats_planned = 3
        metadata.calibration = 'Documented not calibrated'
        return metadata

    def review(self, metadata):
        rate = 16000
        t = np.arange(rate * 2) / rate
        samples = 0.2 * np.sin(2 * np.pi * 300 * t)
        return {item['check']: item['status'] for item in review_reference(metadata, samples, rate)['checks']}

    def test_rejects_invalid_provenance_values(self):
        for field, value, check in [
            ('recorded_utc', 'x', 'recorded_utc'),
            ('recorded_utc', '2026-10-22T12:00:00', 'recorded_utc'),
            ('recorded_utc', '2026-10-22T12:00:00+02:00', 'recorded_utc'),
            ('height_m', 'nan', 'height_m'), ('height_m', '-1', 'height_m'),
            ('operator', None, 'required_metadata'),
            ('repeat_number', 4, 'repeats'), ('repeat_number', '1', 'repeats'),
            ('repeats_planned', 0, 'repeats')]:
            metadata = self.metadata()
            setattr(metadata, field, value)
            with self.subTest(field=field, value=value):
                self.assertEqual(self.review(metadata)[check], 'fail')

    def test_accepts_valid_utc_height_and_repeat_metadata(self):
        checks = self.review(self.metadata())
        for field in ('required_metadata', 'recorded_utc', 'height_m', 'repeats'):
            self.assertEqual(checks[field], 'pass')

    def test_detects_positive_full_scale_in_eight_bit_pcm(self):
        review = review_reference(self.metadata(), np.full(16000, 127 / 128), 16000)
        clipping = next(item for item in review['checks'] if item['check'] == 'clipping')
        self.assertEqual(clipping['status'], 'fail')

    def test_case_store_refuses_nonfinite_reference_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.wav'
            source.write_bytes(b'original evidence')
            with CaseStore(root / 'case.sqlite') as store:
                evidence = store.register_evidence(source)
                for metadata, review in [({'height_m': float('nan')}, {}),
                                         ({}, {'score': float('inf')})]:
                    with self.assertRaises(ValueError):
                        store.add_reference(evidence, metadata, review)
                self.assertEqual(store.references(), [])

    def test_missing_optional_calibration_is_reviewed_without_crashing(self):
        metadata = self.metadata()
        metadata.calibration = None
        self.assertEqual(self.review(metadata)['calibration'], 'warn')
