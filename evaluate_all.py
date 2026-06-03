import os
import sys
import shutil
import json
from datetime import datetime
from evaluate_common import evaluate_subset, MOLMO_OUTPUT_DIR


def evaluate_pipeline():
    # Create a timestamped output folder
    model_name = "qwen3.6-plus"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = os.path.join("data/output", f"{model_name}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    # Always force rerun: clear old Molmo output so all scenes are re-processed
    if os.path.exists(MOLMO_OUTPUT_DIR):
        print(f"🗑️  Clearing old Molmo output: {MOLMO_OUTPUT_DIR}")
        shutil.rmtree(MOLMO_OUTPUT_DIR)
    os.makedirs(MOLMO_OUTPUT_DIR, exist_ok=True)

    subset_names = [
        "easy_no_ambi",
        "easy_yes_ambi",
        "medium_no_ambi",
        "medium_yes_ambi",
        "hard_no_ambi",
        "hard_yes_ambi",
    ]

    scores = {}
    for subset_name in subset_names:
        scores[subset_name] = evaluate_subset(subset_name, output_dir=run_dir)

    # Generate summary table
    summary_path = os.path.join(run_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.write("# Experiment Results\n\n")
        f.write(f"- **Model**: {model_name}\n")
        f.write(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| Method | Reas. | Segm. | Metric | Easy (w/o Amb.) | Easy (w/ Amb.) | Medium (w/o Amb.) | Medium (w/ Amb.) | Hard (w/o Amb.) | Hard (w/ Amb.) |\n")
        f.write("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        f.write(
            f"| FreeGrasp | ✓ |  | RSR "
            f"| {scores['easy_no_ambi']['rsr']:.2f} | {scores['easy_yes_ambi']['rsr']:.2f} "
            f"| {scores['medium_no_ambi']['rsr']:.2f} | {scores['medium_yes_ambi']['rsr']:.2f} "
            f"| {scores['hard_no_ambi']['rsr']:.2f} | {scores['hard_yes_ambi']['rsr']:.2f} |\n"
        )
        f.write(
            f"| FreeGrasp | ✓ | ✓ | SSR "
            f"| {scores['easy_no_ambi']['ssr']:.2f} | {scores['easy_yes_ambi']['ssr']:.2f} "
            f"| {scores['medium_no_ambi']['ssr']:.2f} | {scores['medium_yes_ambi']['ssr']:.2f} "
            f"| {scores['hard_no_ambi']['ssr']:.2f} | {scores['hard_yes_ambi']['ssr']:.2f} |\n"
        )

    # Save as JSON
    json_path = os.path.join(run_dir, "summary.json")
    with open(json_path, "w") as f:
        json.dump({"model": model_name, "timestamp": timestamp, "scores": scores}, f, indent=4)

    print(f"\n📊 Results saved to: {run_dir}")
    print(f"📄 Summary table: {summary_path}")
    print("\n" + "=" * 60)
    for k, v in scores.items():
        print(f"  {k:25s}: RSR {v['rsr']:.2%} | SSR {v['ssr']:.2%}")
    print("=" * 60)

    return scores


if __name__ == "__main__":
    evaluate_pipeline()
