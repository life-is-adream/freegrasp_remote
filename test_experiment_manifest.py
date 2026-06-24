import tempfile
import unittest
from pathlib import Path

from experiment_manifest import build_manifest, guard_provenance, hash_directory


class ExperimentManifestTest(unittest.TestCase):
    def test_directory_hash_is_order_independent_and_content_sensitive(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first = Path(first)
            second = Path(second)
            (first / "b.txt").write_bytes(b"two")
            (first / "a.txt").write_bytes(b"one")
            (second / "a.txt").write_bytes(b"one")
            (second / "b.txt").write_bytes(b"two")
            self.assertEqual(hash_directory(first), hash_directory(second))
            (second / "a.txt").write_bytes(b"changed")
            self.assertNotEqual(hash_directory(first), hash_directory(second))

    def test_automatic_manifest_rejects_oracle_inputs(self):
        base = {
            "model": "mimo-v2.5",
            "max_output_tokens": 1024,
            "routing_variant": "predicted_geometry",
        }
        with self.assertRaisesRegex(ValueError, "ground-truth features"):
            build_manifest({**base, "uses_gt_features": True})
        with self.assertRaisesRegex(ValueError, "benchmark difficulty"):
            build_manifest({**base, "uses_benchmark_difficulty": True})

    def test_guard_provenance_is_stable(self):
        self.assertEqual(
            guard_provenance("conservative_v1"),
            {
                "route_guard_variant": "conservative_v1",
                "direct_confidence_threshold": 0.9,
                "direct_max_object_count": None,
                "target_overlap_threshold": 0.15,
                "guard_code_version": "conservative-v1",
            },
        )

    def test_target_evidence_provenance_is_stable(self):
        self.assertEqual(
            guard_provenance("target_evidence_v2"),
            {
                "route_guard_variant": "target_evidence_v2",
                "target_evidence_max_candidates": 3,
                "duplicate_mask_iou_threshold": 0.85,
                "duplicate_bbox_overlap_threshold": 0.95,
                "guard_code_version": "target-evidence-v2",
            },
        )


if __name__ == "__main__":
    unittest.main()
