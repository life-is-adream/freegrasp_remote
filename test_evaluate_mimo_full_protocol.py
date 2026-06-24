import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import evaluate_mimo_full_protocol


class EvaluateMimoFullProtocolTest(unittest.TestCase):
    def test_default_args_match_full_protocol_best_known_v1(self):
        args = evaluate_mimo_full_protocol.parse_args([])

        self.assertEqual(args.model_name, "mimo-v2.5")
        self.assertEqual(args.max_output_tokens, 713)
        self.assertEqual(args.subset_policy, "best_known_v1")
        self.assertEqual(args.splits, ["0", "1", "2"])
        self.assertEqual(args.run_root, "data/output/mimo-v2.5_full_protocol_best_known_v1")
        self.assertTrue(args.resume)
        self.assertTrue(args.reuse_molmo)
        self.assertFalse(args.fresh_molmo)

    def test_parse_args_accepts_fresh_molmo(self):
        args = evaluate_mimo_full_protocol.parse_args(["--fresh-molmo"])

        self.assertTrue(args.fresh_molmo)
        self.assertTrue(args.reuse_molmo)

    def test_aggregate_run_results_counts_all_splits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            for split, rows in {
                "0": [[1, 1, "a", 1, 1], [2, 1, "b", 0, 1]],
                "1": [[3, 1, "c", 1, 0]],
            }.items():
                split_dir = run_root / f"split_{split}"
                split_dir.mkdir()
                (split_dir / "out_easy_no_ambi.json").write_text(json.dumps(rows))

            summary = evaluate_mimo_full_protocol.aggregate_run_results(
                run_root=run_root,
                splits=["0", "1"],
                subsets=["easy_no_ambi"],
                model_name="mimo-v2.5",
                max_output_tokens=713,
                subset_policy="best_known_v1",
                molmo_cache_policy="reuse_existing",
                scores_by_split={"0": {}, "1": {}},
            )

        self.assertEqual(summary["overall"]["n"], 3)
        self.assertEqual(summary["overall"]["ssr_count"], 2)
        self.assertEqual(summary["overall"]["rsr_count"], 2)
        self.assertAlmostEqual(summary["overall"]["ssr"], 2 / 3)
        self.assertAlmostEqual(summary["overall"]["rsr"], 2 / 3)
        self.assertEqual(summary["aggregate"]["easy_no_ambi"]["n"], 3)
        self.assertEqual(summary["molmo_cache_policy"], "reuse_existing")

    def test_summary_records_provenance_and_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            split_dir = run_root / "split_0"
            split_dir.mkdir()
            (split_dir / "out_easy_no_ambi.json").write_text(
                json.dumps([[1, 1, "a", 1, 1]])
            )
            (split_dir / "details_easy_no_ambi.json").write_text(
                json.dumps(
                    [
                        {
                            "reasoning": {
                                "raw_outputs": ["router", "answer", "repair"],
                                "router_call_count": 1,
                                "retry_count": 1,
                            }
                        }
                    ]
                )
            )

            summary = evaluate_mimo_full_protocol.aggregate_run_results(
                run_root=run_root,
                splits=["0"],
                subsets=["easy_no_ambi"],
                model_name="mimo-v2.5",
                max_output_tokens=1024,
                subset_policy="automatic_evidence_v1",
                molmo_cache_policy="reuse_existing",
                scores_by_split={"0": {}},
                manifest={
                    "manifest_id": "manifest-1",
                    "cache_sha256": "cache-1",
                    "feature_source": "predicted",
                    "routing_variant": "predicted_geometry",
                    "uses_gt_features": False,
                    "uses_benchmark_difficulty": False,
                    "route_guard_variant": "target_evidence_v2",
                    "target_evidence_max_candidates": 3,
                    "duplicate_mask_iou_threshold": 0.85,
                    "duplicate_bbox_overlap_threshold": 0.95,
                    "guard_code_version": "target-evidence-v2",
                },
            )

        self.assertEqual(summary["manifest_id"], "manifest-1")
        self.assertEqual(summary["cache_sha256"], "cache-1")
        self.assertEqual(summary["reasoning_calls"], 3)
        self.assertEqual(summary["router_calls"], 1)
        self.assertEqual(summary["repair_calls"], 1)
        self.assertEqual(summary["calls_per_sample"], 3.0)
        self.assertEqual(
            summary["route_guard_variant"],
            "target_evidence_v2",
        )
        self.assertEqual(summary["target_evidence_max_candidates"], 3)
        self.assertEqual(summary["duplicate_mask_iou_threshold"], 0.85)
        self.assertEqual(
            summary["duplicate_bbox_overlap_threshold"],
            0.95,
        )

    def test_fresh_molmo_regenerates_once_then_reuses_for_all_subsets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            molmo_dir = tmpdir / "molmo_output"
            molmo_dir.mkdir()
            old_file = molmo_dir / "old_cache.txt"
            old_file.write_text("old")
            run_root = tmpdir / "run"
            calls = {"batch": [], "evaluate": []}

            evaluate_common_stub = types.ModuleType("evaluate_common")
            evaluate_common_stub.NPZ_DIR = "data/npz_file"
            evaluate_common_stub.MOLMO_OUTPUT_DIR = str(molmo_dir)
            evaluate_common_stub.load_dataset = lambda: "df"

            def fake_evaluate_subset(subset_name, **kwargs):
                calls["evaluate"].append((subset_name, kwargs))
                output_dir = Path(kwargs["output_dir"])
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / f"out_{subset_name}.json").write_text(json.dumps([[1, 1, "a", 1, 1]]))
                return {"ssr": 1.0, "rsr": 1.0}

            evaluate_common_stub.evaluate_subset = fake_evaluate_subset

            molmo_eval_stub = types.ModuleType("molmo_eval")
            molmo_eval_stub.batch_process_molmo = lambda df, npz_dir, output_dir: calls["batch"].append(
                (df, npz_dir, output_dir)
            )

            evaluate_all_stub = types.ModuleType("evaluate_all")
            evaluate_all_stub._subset_config = lambda *args, **kwargs: {
                "prompt_variant": "legacy_old",
                "mimo_retry_mode": "id_repair",
                "segmentation_variant": "point_retry",
            }

            evaluate_mimo_stub = types.ModuleType("evaluate_mimo")
            evaluate_mimo_stub.create_mimo_client = lambda **kwargs: object()
            evaluate_mimo_stub.validate_mimo_supports_image_input = lambda *args, **kwargs: None
            evaluate_mimo_stub.patch_freegrasp_client = lambda *args, **kwargs: None

            module_names = ["evaluate_common", "molmo_eval", "evaluate_all", "evaluate_mimo"]
            originals = {name: sys.modules.get(name) for name in module_names}
            sys.modules["evaluate_common"] = evaluate_common_stub
            sys.modules["molmo_eval"] = molmo_eval_stub
            sys.modules["evaluate_all"] = evaluate_all_stub
            sys.modules["evaluate_mimo"] = evaluate_mimo_stub

            def restore_modules():
                for name, module in originals.items():
                    if module is None:
                        sys.modules.pop(name, None)
                    else:
                        sys.modules[name] = module

            self.addCleanup(restore_modules)

            args = evaluate_mimo_full_protocol.parse_args(
                [
                    "--fresh-molmo",
                    "--splits",
                    "0",
                    "--run-root",
                    str(run_root),
                    "--no-resume",
                ]
            )
            summary = evaluate_mimo_full_protocol.run_full_protocol(args)

        self.assertFalse(old_file.exists())
        self.assertEqual(calls["batch"], [("df", "data/npz_file", str(molmo_dir))])
        self.assertEqual(len(calls["evaluate"]), len(evaluate_mimo_full_protocol.DEFAULT_SUBSETS))
        self.assertTrue(all(call[1]["prepare_molmo"] is False for call in calls["evaluate"]))
        self.assertEqual(summary["molmo_cache_policy"], "fresh_once")


if __name__ == "__main__":
    unittest.main()
