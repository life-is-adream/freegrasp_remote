import json
import os
import io
import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path
from utils.utils import get_prediction_result
from rsr_metrics import is_reasoning_success

# Load dataset JSON file
def load_dataset(json_path):
    with open(json_path, "r") as f:
        data = json.load(f)
    return data["rows"]

# Compute IoU
def compute_iou(mask_pred, mask_gt):
    intersection = np.logical_and(mask_pred, mask_gt).sum()
    union = np.logical_or(mask_pred, mask_gt).sum()
    return intersection / union if union > 0 else 0


def _append_result(results, scene_id, obj_id, annotation, ssr_correct, rsr_correct):
    results.append([scene_id, obj_id, annotation, ssr_correct, rsr_correct])


def _sample_key(scene_id, obj_id, annotation):
    return (str(scene_id), int(obj_id), str(annotation))


def _result_key(result):
    if not isinstance(result, list) or len(result) < 3:
        return None
    try:
        return _sample_key(result[0], result[1], result[2])
    except (TypeError, ValueError):
        return None


def _load_existing_results(output_json_path):
    if not os.path.exists(output_json_path):
        return []
    with open(output_json_path, "r") as f:
        try:
            results = json.load(f)
        except json.JSONDecodeError:
            return []
    return results if isinstance(results, list) else []


def _write_results(output_json_path, results):
    with open(output_json_path, "w") as f:
        json.dump(results, f, indent=4)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _load_existing_details(details_json_path):
    if details_json_path is None or not os.path.exists(details_json_path):
        return []
    with open(details_json_path, "r") as f:
        try:
            details = json.load(f)
        except json.JSONDecodeError:
            return []
    return details if isinstance(details, list) else []


def _write_details(details_json_path, details):
    if details_json_path is None:
        return
    with open(details_json_path, "w") as f:
        json.dump(_json_safe(details), f, indent=4)


def _append_detail(
    details,
    scene_id,
    obj_id,
    annotation,
    gt_ids,
    ssr_correct,
    rsr_correct,
    iou,
    reasoning,
    error=None,
    failure_reason=None,
):
    if details is None:
        return
    details.append(
        {
            "scene_id": int(scene_id),
            "object_id": int(obj_id),
            "annotation": annotation,
            "gt_ids": [int(gt_id) for gt_id in gt_ids],
            "ssr_correct": int(ssr_correct),
            "rsr_correct": int(rsr_correct),
            "iou": float(iou),
            "failure_reason": failure_reason,
            "error": error,
            "reasoning": reasoning if isinstance(reasoning, dict) else {},
        }
    )


def _is_reasoning_success(reasoning, gt_ids):
    if not isinstance(reasoning, dict):
        return 0
    selected_gt_id = reasoning.get("selected_gt_id")
    try:
        return int(int(selected_gt_id) in set(gt_ids))
    except (TypeError, ValueError):
        return 0


# Process the entire dataset
def process_dataset(
    df,
    dataset_root,
    molmo_output_root,
    output_json_path,
    prompt_variant="legacy",
    model_name="qwen3.6-flash",
    max_output_tokens=64,
    resume=False,
    mimo_retry_mode="none",
    segmentation_variant="baseline",
    evaluation_subset=None,
    details_json_path=None,
):
    results = _load_existing_results(output_json_path) if resume else []
    details = _load_existing_details(details_json_path) if resume and details_json_path else ([] if details_json_path else None)
    correct_count = sum(1 for item in results if isinstance(item, list) and len(item) > 3 and item[3] == 1)
    processed_scenes = {key for key in (_result_key(result) for result in results) if key is not None}
    if resume and results:
        print(f"Resuming from {output_json_path}: loaded {len(results)} existing result(s).")

    for _, row in df.iterrows():
        # scene_id, obj_id, annotation, gt_id, _ = row
        scene_id = row["sceneId"]
        obj_id = row["queryObjId"]
        annotation = row["annotation"]
        gt_id = row["groundTruthObjIds"]
        image_bytes = row["image"]["bytes"]
        
        # Dataset object IDs start from 0, while pointed object IDs start from 1. Need to increment by 1.
        obj_id = int(obj_id) + 1
        
        if (scene_id, obj_id, annotation) in processed_scenes:
            print(f"Skipping Scene {scene_id}, Object {obj_id}, already processed.")
            continue
        
        print(f"Processing Scene {scene_id}, Object {obj_id}...")

        image_bytes = row["image"]["bytes"]
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        dataset_root = Path(dataset_root)
        gt_mask_path = dataset_root / f"{scene_id}.npz"
        molmo_folder = Path(molmo_output_root) / f"scene{scene_id}"
        molmo_image_path = molmo_folder/f"{scene_id}.png"

        if not gt_mask_path.exists():
            print(f"⚠️ GT mask file {gt_mask_path} not found!")
            continue

        gt_data = np.load(gt_mask_path, allow_pickle=True)
        gt_masks = gt_data["instances_objects.npy"]

        try:
            gt_ids = [int(x) + 1 for x in str(gt_id).split(",")]
        except ValueError:
            print(f"⚠️ Invalid GT ID format: {gt_id} → Skipping this scene.")
            continue
        
        valid_gt = False
        # image_path include original image for LangSAM, molmo_folder include labeled image (for GPT) and points coordinates (for LangSAM post-process).

        try:
            prediction = get_prediction_result(
                image,
                molmo_folder,
                scene_id,
                annotation,
                return_metadata=True,
                prompt_variant=prompt_variant,
                model_name=model_name,
                max_output_tokens=max_output_tokens,
                mimo_retry_mode=mimo_retry_mode,
                segmentation_variant=segmentation_variant,
                evaluation_subset=evaluation_subset,
            )
            reasoning = prediction.get("reasoning", {}) if isinstance(prediction, dict) else {}
            rsr_correct = int(
                is_reasoning_success(
                    reasoning.get("selected_object_id"),
                    {reasoning.get("selected_object_id"): reasoning.get("selected_gt_id")},
                    gt_ids,
                )
            )
            
            if isinstance(prediction, dict) and "error" in prediction:
                print(f"Scene {scene_id}, Object {obj_id} failed: {prediction['error']}")
                _append_result(results, scene_id, obj_id, annotation, 0, rsr_correct)
                _append_detail(
                    details,
                    scene_id,
                    obj_id,
                    annotation,
                    gt_ids,
                    0,
                    rsr_correct,
                    0.0,
                    reasoning,
                    error=prediction["error"],
                    failure_reason=reasoning.get("failure_reason"),
                )
                processed_scenes.add(sample_key)
                _write_results(output_json_path, results)
                _write_details(details_json_path, details)
                continue

            mask_pred = prediction["mask"] if isinstance(prediction, dict) else prediction
        
        except Exception as e:
            print(f"❌ Unexpected error in Scene {scene_id}, Object {obj_id}: {e}")
            _append_result(results, scene_id, obj_id, annotation, 0, 0)
            _append_detail(
                details,
                scene_id,
                obj_id,
                annotation,
                gt_ids,
                0,
                0,
                0.0,
                {},
                error=str(e),
                failure_reason="unexpected_error",
            )
            processed_scenes.add(sample_key)
            _write_results(output_json_path, results)
            _write_details(details_json_path, details)
            continue 

        if mask_pred is None:
            print(f"❌ Scene {scene_id}, Object {obj_id}: mask_pred is None, skipping.")
            _append_result(results, scene_id, obj_id, annotation, 0, rsr_correct)
            _append_detail(
                details,
                scene_id,
                obj_id,
                annotation,
                gt_ids,
                0,
                rsr_correct,
                0.0,
                reasoning,
                failure_reason="mask_pred_none",
            )
            processed_scenes.add(sample_key)
            _write_results(output_json_path, results)
            _write_details(details_json_path, details)
            continue

        mask_pred = np.asarray(mask_pred)
        # gt_masks can be 2D (H,W) or 3D (N,H,W). Get spatial shape.
        gt_spatial_shape = gt_masks.shape if gt_masks.ndim == 2 else gt_masks.shape[1:]
        if mask_pred.ndim != 2 or mask_pred.shape != gt_spatial_shape:
            print(f"❌ Scene {scene_id}, Object {obj_id}: mask_pred shape {mask_pred.shape} != expected {gt_spatial_shape}, skipping.")
            _append_result(results, scene_id, obj_id, annotation, 0, rsr_correct)
            _append_detail(
                details,
                scene_id,
                obj_id,
                annotation,
                gt_ids,
                0,
                rsr_correct,
                0.0,
                reasoning,
                failure_reason="mask_shape_mismatch",
            )
            processed_scenes.add(sample_key)
            _write_results(output_json_path, results)
            _write_details(details_json_path, details)
            continue

        iou = 0.0
        for gt_id in gt_ids:
            if gt_masks.ndim == 3:
                if 0 < gt_id <= len(gt_masks):
                    gt_mask = (gt_masks[gt_id - 1] > 0).astype(np.uint8)
                    iou = compute_iou(mask_pred, gt_mask)
                    if iou >= 0.5:
                        valid_gt = True
                        break
                else:
                    print(f"⚠️ GT ID {gt_id} is out of range for Scene {scene_id}.")
            else:
                # gt_masks is 2D, gt_id marks a pixel value
                gt_mask = (gt_masks == gt_id).astype(np.uint8)
                if gt_mask.sum() == 0:
                    print(f"⚠️ GT ID {gt_id} not found in 2D mask for Scene {scene_id}.")
                    continue
                iou = compute_iou(mask_pred, gt_mask)
                if iou >= 0.5:
                    valid_gt = True
                    break
                
        is_correct = 1 if valid_gt else 0
        correct_count += is_correct           
        _append_result(results, scene_id, obj_id, annotation, is_correct, rsr_correct)
        _append_detail(
            details,
            scene_id,
            obj_id,
            annotation,
            gt_ids,
            is_correct,
            rsr_correct,
            iou,
            reasoning,
            failure_reason=None if is_correct else "iou_below_threshold",
        )
        processed_scenes.add(sample_key)
        
        _write_results(output_json_path, results)
        _write_details(details_json_path, details)
        
        print(f"✅ Scene {scene_id}, Object {obj_id}: IoU={iou:.4f}, {'✔' if is_correct else '❌'}")

    # Calculate accuracy
    with open(output_json_path, "w") as f:
        json.dump(results, f, indent=4)

    accuracy = correct_count / len(df) if len(df) else 0
    print(f"\n🎯 Accuracy: {accuracy:.2%} ({correct_count}/{len(df)})")
    print(f"📂 Results saved to {output_json_path}")


if __name__ == "__main__":
    # Path of dataset
    PARQUET_FILES = [
        "data/train-00000-of-00002.parquet",
        "data/train-00001-of-00002.parquet"
    ]
    NPZ_DIR = "data/npz_file"
    molmo_output_root = "data/output/molmo_output"

    # Load the dataset
    df = pd.concat([pd.read_parquet(p) for p in PARQUET_FILES])

    # Select split to run
    selected_split = '0'  # Change this value to 0, 1, or 2

    df = df[df['split'] == selected_split]  # Filter dataset based on selected split

    # Select subsets for testing
    easy_no_ambi = df[(df['difficulty'] == 'Easy') & (df['ambiguious'] == False)]
    easy_yes_ambi = df[(df['difficulty'] == 'Easy') & (df['ambiguious'] == True)]
    medium_no_ambi = df[(df['difficulty'] == 'Medium') & (df['ambiguious'] == False)]
    medium_yes_ambi = df[(df['difficulty'] == 'Medium') & (df['ambiguious'] == True)]
    hard_no_ambi = df[(df['difficulty'] == 'Hard') & (df['ambiguious'] == False)]
    hard_yes_ambi = df[(df['difficulty'] == 'Hard') & (df['ambiguious'] == True)]

    # Choose a subset for testing (e.g., easy_no_ambi)
    subset_name = "easy_no_ambi"  
    selected_subset = eval(subset_name)  
    print(f"Total number of examples in [SPLIT {selected_split}] of [SET {subset_name}]: {len(selected_subset)}")

    # Run test
    dataset_root = NPZ_DIR
    output_json_path = f"data/output/out_{subset_name}.json"
    process_dataset(selected_subset, dataset_root, molmo_output_root, output_json_path)
