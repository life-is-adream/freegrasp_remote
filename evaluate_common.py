import os

# Disable proxies and use HF mirror to prevent SSLEOFError
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
os.environ.pop(k, None)
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# Set DASHSCOPE_API_KEY in the environment before running DashScope calls.
# Force PyTorch SDPA to NOT use flash_attn (cu123 flash-attn is incompatible with CUDA 12.4)
os.environ["PYTORCH_SDP_DISABLE_FLASH_ATTENTION"] = "1"

import pandas as pd

from calculate_SR import calculate_accuracy, calculate_reasoning_accuracy
from molmo_eval import batch_process_molmo
from reasoning_eval import process_dataset


PARQUET_FILES = [
    "data/train-00000-of-00002.parquet",
    "data/train-00001-of-00002.parquet",
]
NPZ_DIR = "data/npz_file"
MOLMO_OUTPUT_DIR = "data/output/molmo_output"

SUBSET_FILTERS = {
    "easy_no_ambi": ("Easy", False),
    "easy_yes_ambi": ("Easy", True),
    "medium_no_ambi": ("Medium", False),
    "medium_yes_ambi": ("Medium", True),
    "hard_no_ambi": ("Hard", False),
    "hard_yes_ambi": ("Hard", True),
}


def load_dataset() -> pd.DataFrame:
    return pd.concat([pd.read_parquet(path) for path in PARQUET_FILES])


def prepare_subset(df: pd.DataFrame, subset_name: str, selected_split: str) -> pd.DataFrame:
    if subset_name not in SUBSET_FILTERS:
        raise ValueError(f"Unknown subset_name: {subset_name}")

    difficulty, ambiguous = SUBSET_FILTERS[subset_name]
    split_df = df[df["split"] == selected_split]
    return split_df[(split_df["difficulty"] == difficulty) & (split_df["ambiguious"] == ambiguous)]


def missing_molmo_scene_ids(df: pd.DataFrame, molmo_output_dir: str = MOLMO_OUTPUT_DIR) -> list[int]:
    missing = []
    for scene_id in sorted(int(scene_id) for scene_id in df["sceneId"].unique()):
        scene_dir = os.path.join(molmo_output_dir, f"scene{scene_id}")
        image_path = os.path.join(scene_dir, f"{scene_id}.png")
        id_path = os.path.join(scene_dir, f"{scene_id}_id.txt")
        if not os.path.exists(image_path) or not os.path.exists(id_path):
            missing.append(scene_id)
    return missing


def ensure_molmo_cache_exists(df: pd.DataFrame, molmo_output_dir: str = MOLMO_OUTPUT_DIR) -> None:
    missing = missing_molmo_scene_ids(df, molmo_output_dir)
    if not missing:
        return

    preview = ", ".join(str(scene_id) for scene_id in missing[:10])
    raise RuntimeError(
        f"Molmo cache is missing {len(missing)} required scene(s): {preview}. "
        "Run with --regenerate-molmo once to rebuild data/output/molmo_output."
    )


def evaluate_subset(
    subset_name: str,
    selected_split: str = "0",
    output_dir: str = "data/output",
    prepare_molmo: bool = True,
    model_name: str = "qwen3.6-flash",
    prompt_variant: str = "legacy",
    max_output_tokens: int = 64,
    resume: bool = False,
    mimo_retry_mode: str = "none",
    segmentation_variant: str = "baseline",
) -> dict:
    os.makedirs(MOLMO_OUTPUT_DIR, exist_ok=True)

    df = load_dataset()
    batch_process_molmo(df, NPZ_DIR, MOLMO_OUTPUT_DIR)

    selected_subset = prepare_subset(df, subset_name, selected_split)
    print(
        f"Total number of examples in [SPLIT {selected_split}] "
        f"of [SET {subset_name}]: {len(selected_subset)}"
    )

    output_json_path = os.path.join(output_dir, f"out_{subset_name}.json")
    details_json_path = os.path.join(output_dir, f"details_{subset_name}.json")
    process_dataset(
        selected_subset,
        NPZ_DIR,
        MOLMO_OUTPUT_DIR,
        output_json_path,
        prompt_variant=prompt_variant,
        model_name=model_name,
        max_output_tokens=max_output_tokens,
        resume=resume,
        mimo_retry_mode=mimo_retry_mode,
        segmentation_variant=segmentation_variant,
        evaluation_subset=subset_name,
        details_json_path=details_json_path,
    )
    return {
        "ssr": calculate_accuracy(output_json_path),
        "rsr": calculate_reasoning_accuracy(output_json_path),
    }
