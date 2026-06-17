import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from PIL import Image

utils_stub = types.ModuleType("utils.utils")
utils_stub.get_prediction_result = lambda *args, **kwargs: None
sys.modules.setdefault("utils.utils", utils_stub)

from reasoning_eval import process_dataset


def _image_bytes() -> bytes:
    image = Image.new("RGB", (2, 2), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ReasoningResumeTest(unittest.TestCase):
    def test_resume_preserves_existing_rows_and_only_processes_missing_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_root = root / "npz"
            molmo_root = root / "molmo"
            dataset_root.mkdir()
            molmo_root.mkdir()
            output_path = root / "out_easy_no_ambi.json"

            existing_row = [101, 1, "pick the red block", 0, 0]
            output_path.write_text(json.dumps([existing_row], indent=4))

            gt_masks = np.ones((1, 2, 2), dtype=np.uint8)
            np.savez(dataset_root / "202.npz", **{"instances_objects.npy": gt_masks})

            df = pd.DataFrame(
                [
                    {
                        "sceneId": 101,
                        "queryObjId": 0,
                        "annotation": "pick the red block",
                        "groundTruthObjIds": "0",
                        "image": {"bytes": _image_bytes()},
                    },
                    {
                        "sceneId": 202,
                        "queryObjId": 0,
                        "annotation": "pick the blue block",
                        "groundTruthObjIds": "0",
                        "image": {"bytes": _image_bytes()},
                    },
                ]
            )

            prediction = {
                "mask": np.ones((2, 2), dtype=np.uint8),
                "reasoning": {"selected_object_id": 1, "selected_gt_id": 1},
            }
            with patch("reasoning_eval.get_prediction_result", return_value=prediction) as mocked_prediction:
                process_dataset(
                    df,
                    dataset_root,
                    molmo_root,
                    output_path,
                    resume=True,
                    model_name="qwen3.6-flash",
                    prompt_variant="legacy",
                    max_output_tokens=64,
                )

            results = json.loads(output_path.read_text())
            self.assertEqual(results[0], existing_row)
            self.assertEqual(results[1][:5], [202, 1, "pick the blue block", 1, 1])
            self.assertEqual(mocked_prediction.call_count, 1)
            self.assertEqual(mocked_prediction.call_args.kwargs["max_output_tokens"], 64)

    def test_process_dataset_passes_boost_options_and_writes_details_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_root = root / "npz"
            molmo_root = root / "molmo"
            dataset_root.mkdir()
            molmo_root.mkdir()
            output_path = root / "out_hard_yes_ambi.json"
            details_path = root / "details_hard_yes_ambi.json"

            gt_masks = np.ones((1, 2, 2), dtype=np.uint8)
            np.savez(dataset_root / "303.npz", **{"instances_objects.npy": gt_masks})

            df = pd.DataFrame(
                [
                    {
                        "sceneId": 303,
                        "queryObjId": 0,
                        "annotation": "pick the hidden block",
                        "groundTruthObjIds": "0",
                        "image": {"bytes": _image_bytes()},
                    },
                ]
            )

            prediction = {
                "mask": np.ones((2, 2), dtype=np.uint8),
                "reasoning": {
                    "selected_object_id": 1,
                    "selected_gt_id": 1,
                    "raw_outputs": ["bad", "[1, red block]"],
                    "retry_count": 1,
                    "mimo_retry_mode": "id_repair",
                    "segmentation_variant": "point_retry",
                    "molmo_point": [0, 0],
                },
            }
            with patch("reasoning_eval.get_prediction_result", return_value=prediction) as mocked_prediction:
                process_dataset(
                    df,
                    dataset_root,
                    molmo_root,
                    output_path,
                    resume=False,
                    model_name="mimo-v2.5",
                    prompt_variant="hard_occlusion",
                    max_output_tokens=713,
                    mimo_retry_mode="id_repair",
                    segmentation_variant="point_retry",
                    evaluation_subset="hard_yes_ambi",
                    details_json_path=details_path,
                )

            self.assertEqual(mocked_prediction.call_args.kwargs["mimo_retry_mode"], "id_repair")
            self.assertEqual(mocked_prediction.call_args.kwargs["segmentation_variant"], "point_retry")
            self.assertEqual(mocked_prediction.call_args.kwargs["evaluation_subset"], "hard_yes_ambi")

            details = json.loads(details_path.read_text())
            self.assertEqual(len(details), 1)
            self.assertEqual(details[0]["scene_id"], 303)
            self.assertEqual(details[0]["iou"], 1.0)
            self.assertEqual(details[0]["ssr_correct"], 1)
            self.assertEqual(details[0]["rsr_correct"], 1)
            self.assertEqual(details[0]["reasoning"]["retry_count"], 1)


if __name__ == "__main__":
    unittest.main()
