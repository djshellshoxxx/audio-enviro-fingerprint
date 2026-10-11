import unittest

from audio_enviro_fingerprint.reference import (CAPTURE_CHECKLIST, RANKING_CAVEAT, ReferenceMetadata,
                                                quality_review, rank_against_references, validate_reference)


def _metadata(**changes):
    values = dict(location_id="LAB-1", captured_at_utc="2026-10-01T12:00:00+00:00", operator="Examiner A",
                  recorder_make_model="Recorder X", recorder_serial="SN1", microphone_make_model="Mic Y",
                  input_chain="XLR to recorder", channel=0, sample_rate_hz=48000, placement="table centre",
                  orientation="facing door", height_m=1.2, source_signal="ambient, no stimulus",
                  occupancy_activity="empty", weather="n/a indoors", calibration="94 dB SPL tone before capture",
                  repeat_index=1, deviations="none", consent_authority="Site permit 42")
    values.update(changes)
    return ReferenceMetadata(**values)


class ReferenceTests(unittest.TestCase):
    def test_valid_complete_metadata_grades_a(self):
        meta = _metadata()
        self.assertEqual(validate_reference(meta), [])
        review = quality_review(meta, {"sample_rate": 48000, "channels": 2, "duration_seconds": 120,
                                       "repeat_count": 3, "sha256": "a" * 64})
        self.assertEqual(tuple(review["checklist"]), CAPTURE_CHECKLIST)
        self.assertEqual(review["completeness"], 1.0)
        self.assertEqual(review["grade"], "A")

    def test_validation_failures_are_listed(self):
        problems = validate_reference(_metadata(location_id=" ", captured_at_utc="2026-10-01 12:00",
                                                height_m=-1.0, repeat_index=0, sample_rate_hz=0))
        text = " ".join(problems)
        for expected in ("location_id", "captured_at_utc", "height_m", "repeat_index", "sample_rate_hz"):
            self.assertIn(expected, text)

    def test_from_dict_round_trip_and_unknown_field(self):
        meta = _metadata()
        self.assertEqual(ReferenceMetadata.from_dict(meta.to_dict()), meta)
        with self.assertRaises(ValueError):
            ReferenceMetadata.from_dict({**meta.to_dict(), "gps": "x"})

    def test_mismatched_or_short_capture_is_downgraded(self):
        meta = _metadata()
        self.assertEqual(quality_review(meta, {"sample_rate": 44100, "duration_seconds": 120})["grade"],
                         "insufficient")
        short = quality_review(meta, {"sample_rate": 48000, "duration_seconds": 5, "repeat_count": 3,
                                      "sha256": "a" * 64})
        self.assertEqual(short["grade"], "C")

    def test_ranking_orders_by_score_and_skips_incompatible_versions(self):
        query = {"version": "aefp-1", "features": {"spectral_centroid_hz": 500.0, "median_rms_dbfs": -40.0}}
        near = {"version": "aefp-1", "features": {"spectral_centroid_hz": 520.0, "median_rms_dbfs": -41.0}}
        far = {"version": "aefp-1", "features": {"spectral_centroid_hz": 3000.0, "median_rms_dbfs": -20.0}}
        refs = [{"reference_id": 1, "metadata": {"location_id": "far"}, "fingerprint": far},
                {"reference_id": 2, "metadata": {"location_id": "near"}, "fingerprint": near},
                {"reference_id": 3, "metadata": {"location_id": "new"}, "fingerprint": {"version": "aefp-9",
                                                                                         "features": {}}},
                {"reference_id": 4, "metadata": {}, "fingerprint": None}]
        ranked = rank_against_references(query, refs)
        self.assertEqual([item["location_id"] for item in ranked[:2]], ["near", "far"])
        self.assertEqual([item["rank"] for item in ranked], [1, 2, None, None])
        self.assertEqual({item["status"] for item in ranked[2:]}, {"skipped"})
        self.assertTrue(all(item["caveat"] == RANKING_CAVEAT for item in ranked))


if __name__ == "__main__":
    unittest.main()
