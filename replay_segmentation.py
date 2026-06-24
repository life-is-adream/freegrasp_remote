"""Replay LangSAM with frozen reasoning decisions and no VLM calls."""

import argparse
import io
import json
from pathlib import Path

import numpy as np


def frozen_decision(detail):
    reasoning = detail.get("reasoning", {})
    selected_id = reasoning.get("selected_object_id")
    point = reasoning.get("molmo_point")
    if selected_id is None or point is None:
        raise ValueError("Replay requires selected_object_id and molmo_point")
    query = reasoning.get("mask_query") or reasoning.get("class_name")
    if not query:
        raise ValueError("Replay requires mask_query or class_name")
    return {
        "selected_object_id": int(selected_id),
        "molmo_point": tuple(int(value) for value in point),
        "mask_query": str(query),
        "rsr_correct": int(detail["rsr_correct"]),
    }


def replay_row(detail, segment, iou_threshold=0.5):
    decision = frozen_decision(detail)
    segmentation = segment(decision)
    iou = float(segmentation["iou"])
    return {
        "scene_id": int(detail["scene_id"]),
        "object_id": int(detail["object_id"]),
        "selected_object_id": decision["selected_object_id"],
        "molmo_point": list(decision["molmo_point"]),
        "mask_query": decision["mask_query"],
        "rsr_correct": decision["rsr_correct"],
        "source_ssr_correct": int(detail.get("ssr_correct", 0)),
        "ssr_correct": int(iou >= iou_threshold),
        "iou": iou,
        "contains_point": segmentation.get("contains_point"),
        "failure_reason": segmentation.get("failure_reason"),
        "segmentation_metadata": segmentation.get("metadata", {}),
    }


def summarize_replay(rows, source_rsr_count):
    n = len(rows)
    rsr_count = sum(int(row["rsr_correct"]) for row in rows)
    if rsr_count != int(source_rsr_count):
        raise RuntimeError("Segmentation replay changed frozen reasoning outcomes")
    ssr_count = sum(int(row["ssr_correct"]) for row in rows)
    return {
        "n": n,
        "rsr_count": rsr_count,
        "ssr_count": ssr_count,
        "rsr": rsr_count / n if n else 0.0,
        "ssr": ssr_count / n if n else 0.0,
        "mean_iou": (
            sum(float(row["iou"]) for row in rows) / n if n else 0.0
        ),
        "rsr_only": sum(
            int(row["rsr_correct"] and not row["ssr_correct"])
            for row in rows
        ),
        "point_consistency_failures": sum(
            int(row.get("contains_point") is False) for row in rows
        ),
        "recovery_successes": sum(
            int(not row.get("source_ssr_correct", 0) and row["ssr_correct"])
            for row in rows
        ),
        "same_class_mask_swaps": sum(
            int(row.get("source_ssr_correct", 0) and not row["ssr_correct"])
            for row in rows
        ),
    }


def _load_dataframe(parquet_files):
    import pandas as pd

    return pd.concat([pd.read_parquet(path) for path in parquet_files])


def _load_gt_masks(npz_dir, scene_id):
    data = np.load(Path(npz_dir) / f"{scene_id}.npz", allow_pickle=True)
    key = "instances_objects.npy" if "instances_objects.npy" in data else "instances_objects"
    return data[key]


def _ground_truth_masks(instance_objects, gt_ids):
    for gt_id in gt_ids:
        if instance_objects.ndim == 3:
            if 0 < gt_id <= len(instance_objects):
                yield instance_objects[gt_id - 1] > 0
        else:
            mask = instance_objects == gt_id
            if mask.any():
                yield mask


def _compute_iou(predicted, target):
    intersection = np.logical_and(predicted, target).sum()
    union = np.logical_or(predicted, target).sum()
    return float(intersection / union) if union else 0.0


def _make_segmenter(detail, dataset_rows, npz_dir, variant):
    from PIL import Image
    from utils.utils import (
        _predict_langsam_mask,
        get_langsam_query_candidates,
    )

    matching = dataset_rows[dataset_rows["sceneId"] == int(detail["scene_id"])]
    if matching.empty:
        raise ValueError(f"Scene {detail['scene_id']} is absent from the dataset")
    image = Image.open(io.BytesIO(matching.iloc[0]["image"]["bytes"])).convert("RGB")
    gt_ids = [int(value) for value in detail.get("gt_ids", [])]
    gt_masks = list(
        _ground_truth_masks(
            _load_gt_masks(npz_dir, detail["scene_id"]),
            gt_ids,
        )
    )

    def segment(decision):
        candidates = get_langsam_query_candidates(
            decision["mask_query"],
            detail.get("annotation"),
        )
        mask, _bbox, metadata = _predict_langsam_mask(
            image,
            candidates if variant != "baseline" else candidates[:1],
            decision["molmo_point"],
            variant,
        )
        ious = [_compute_iou(np.asarray(mask, dtype=bool), gt) for gt in gt_masks]
        return {
            "iou": max(ious, default=0.0),
            "contains_point": metadata.get("langsam_mask_contains_point"),
            "failure_reason": metadata.get("langsam_failure_reason"),
            "metadata": metadata,
        }

    return segment


def replay_run(source_run, output_run, variant, splits, subsets, parquet_files, npz_dir):
    source_run = Path(source_run)
    output_run = Path(output_run)
    dataset_rows = _load_dataframe(parquet_files)
    all_rows = []
    summaries = {}

    for split in splits:
        split_rows = []
        for subset in subsets:
            source_path = source_run / f"split_{split}" / f"details_{subset}.json"
            details = json.loads(source_path.read_text())
            rows = []
            for detail in details:
                segmenter = _make_segmenter(
                    detail,
                    dataset_rows,
                    npz_dir,
                    variant,
                )
                rows.append(replay_row(detail, segmenter))
            source_rsr = sum(int(detail["rsr_correct"]) for detail in details)
            key = f"split_{split}/{subset}"
            summaries[key] = summarize_replay(rows, source_rsr)
            target_dir = output_run / f"split_{split}"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / f"details_{subset}.json").write_text(
                json.dumps(rows, indent=2)
            )
            split_rows.extend(rows)
            all_rows.extend(rows)
        summaries[f"split_{split}/overall"] = summarize_replay(
            split_rows,
            sum(int(row["rsr_correct"]) for row in split_rows),
        )

    summaries["overall"] = summarize_replay(
        all_rows,
        sum(int(row["rsr_correct"]) for row in all_rows),
    )
    output_run.mkdir(parents=True, exist_ok=True)
    summary = {
        "source_run": str(source_run),
        "segmentation_variant": variant,
        "groups": summaries,
    }
    (output_run / "segmentation_replay_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    return summary


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--output-run", required=True)
    parser.add_argument(
        "--segmentation-variant",
        choices=["baseline", "point_retry", "geometric_consistency"],
        required=True,
    )
    parser.add_argument("--splits", nargs="+", default=["0", "1", "2"])
    parser.add_argument(
        "--subsets",
        nargs="+",
        default=[
            "easy_no_ambi",
            "easy_yes_ambi",
            "medium_no_ambi",
            "medium_yes_ambi",
            "hard_no_ambi",
            "hard_yes_ambi",
        ],
    )
    parser.add_argument(
        "--parquet-files",
        nargs="+",
        default=[
            "data/train-00000-of-00002.parquet",
            "data/train-00001-of-00002.parquet",
        ],
    )
    parser.add_argument("--npz-dir", default="data/npz_file")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    replay_run(
        source_run=args.source_run,
        output_run=args.output_run,
        variant=args.segmentation_variant,
        splits=args.splits,
        subsets=args.subsets,
        parquet_files=args.parquet_files,
        npz_dir=args.npz_dir,
    )


if __name__ == "__main__":
    main()
