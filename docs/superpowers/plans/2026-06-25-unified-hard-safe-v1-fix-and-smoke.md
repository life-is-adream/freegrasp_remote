# Unified Hard-Safe V1 Fix And Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `unified_hard_safe_v1` actually match the design intent before any paid experiment by wiring the missing ablation hooks, enforcing deterministic hard fallback behavior, and adding a true hard-only smoke path in the `freegrasp` environment.

**Architecture:** Keep the design single-protocol and non-routed. The only changes should be in protocol parsing/repair, subset-policy wiring, and tests. Do not touch dataset contents, router training, or `/home/public/zb/FreeGrasp_code-main`.

**Tech Stack:** Python, `unittest`, MiMo patching helpers, FreeGrasp evaluation scripts, Conda `freegrasp`

---

## File Map

- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/utils.py`
  - Owns `VALID_PROTOCOL_ABLATIONS`, `process_grasping_result`, and the main reasoning/repair flow.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_all.py`
  - Owns subset-policy to runtime-config mapping.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_mimo.py`
  - Owns single-run CLI choices; needed for true smoke commands.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_utils_output_limit.py`
  - Best existing place for parser and retry-flow unit tests.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_all_summary.py`
  - Best place for subset-policy config assertions.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_mimo.py`
  - Best place for single-run CLI acceptance tests.

### Task 1: Wire Missing Unified Ablations

**Files:**
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/utils.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_all.py`
- Test: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_all_summary.py`

- [ ] **Step 1: Write failing subset-policy tests**

Add assertions that:
- `unified_hard_safe_v1` uses `prompt_variant="unified_hard_safe_v1_json"` and `segmentation_variant="point_retry"`
- `unified_hard_safe_no_point_repair` switches to `segmentation_variant="baseline"`
- `unified_hard_safe_no_hard_fallback` sets `protocol_ablation="no_hard_fallback"`
- `unified_hard_safe_no_ranked_candidates` sets `protocol_ablation="no_ranked_candidates"`
- `unified_hard_safe_no_id_repair` keeps `protocol_ablation="no_id_repair"`

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_evaluate_all_summary.py -v
```

Expected:
- Failure because at least one unified hard-safe assertion is missing or wrong.

- [ ] **Step 3: Implement the minimal wiring**

Required code changes:
- Extend `VALID_PROTOCOL_ABLATIONS` with:
  - `"no_hard_fallback"`
  - `"no_ranked_candidates"`
  - `"no_point_repair"`
- In `_subset_config()`:
  - keep `unified_hard_safe_v1 -> segmentation_variant="point_retry"`
  - change `unified_hard_safe_no_point_repair -> segmentation_variant="baseline"`
  - keep the other hard-safe ablations on `point_retry`

- [ ] **Step 4: Re-run the focused test**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_evaluate_all_summary.py -v
```

Expected:
- PASS

### Task 2: Make Hard Fallback Deterministic Instead Of Cosmetic

**Files:**
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/utils.py`
- Test: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_utils_output_limit.py`

- [ ] **Step 1: Write failing parser tests**

Add tests covering these cases:
- blocked or uncertain target forces `action="remove_blocker"` under `protocol_ablation="full"`
- the same payload does **not** force fallback under `protocol_ablation="no_hard_fallback"`
- when fallback is active and `ranked_first_grasp_candidates=[5, 2, 7]`, the selected ID becomes `5`
- when fallback is active but `ranked_first_grasp_candidates=[]`, the parser must invalidate the chosen ID instead of silently keeping the original target ID

Use a payload shape like:

```python
payload = {
    "target_object_id": 3,
    "target_status": "uncertain",
    "first_grasp_object_id": 3,
    "action": "grasp_target",
    "ranked_first_grasp_candidates": [5, 2, 7],
    "mask_query": "white box",
    "confidence": 0.42,
    "evidence": {
        "blocker_evidence": "object 5 overlaps the target",
        "uncertainty": ["target partially hidden"],
    },
}
```

- [ ] **Step 2: Run the focused parser test and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_utils_output_limit.py -v
```

Expected:
- Failure because `process_grasping_result()` does not yet honor the new ablations or the empty-ranked-candidate safe failure behavior.

- [ ] **Step 3: Implement the minimal deterministic repair**

Required code changes:
- Change `process_grasping_result()` to accept `protocol_ablation="full"`
- Propagate that argument from every call site
- Apply hard fallback only when `protocol_ablation != "no_hard_fallback"`
- Ignore `ranked_first_grasp_candidates` when `protocol_ablation == "no_ranked_candidates"`
- If hard fallback is active:
  - set `result["action"] = "remove_blocker"`
  - if ranked candidates are available, use the first ranked visible candidate
  - if ranked candidates are unavailable, remove `selected_object_id` so downstream repair/retry handles it explicitly
- Preserve metadata fields:
  - `hard_fallback_applied`
  - `pre_repair_action`
  - `pre_repair_first_grasp_object_id`
  - `ranked_first_grasp_candidates`

- [ ] **Step 4: Re-run the focused parser test**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_utils_output_limit.py -v
```

Expected:
- PASS

### Task 3: Expose A True Hard-Only Smoke Entry

**Files:**
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_mimo.py`
- Test: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_mimo.py`

- [ ] **Step 1: Write failing CLI tests**

Add CLI acceptance checks that `evaluate_mimo.py` accepts:
- `--subset-policy unified_hard_safe_v1`
- `--subset-policy unified_hard_safe_no_hard_fallback`
- `--subset-policy unified_hard_safe_no_point_repair`

- [ ] **Step 2: Run the focused CLI test and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_evaluate_mimo.py -v
```

Expected:
- Failure because `evaluate_mimo.py` currently does not list unified hard-safe policies.

- [ ] **Step 3: Implement the minimal CLI support**

Required code changes:
- Add the unified hard-safe policies to the `--subset-policy` choices in `evaluate_mimo.py`
- Add `"unified_hard_safe_v1_json"` to the `--prompt-variant` choices only if the script still needs direct prompt use for debugging

- [ ] **Step 4: Re-run the focused CLI test**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_evaluate_mimo.py -v
```

Expected:
- PASS

### Task 4: Full Local Verification Before Any Paid Call

**Files:**
- No new files
- Verify only

- [ ] **Step 1: Run the targeted test set**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest \
  test_evaluate_all_summary.py \
  test_evaluate_mimo.py \
  test_utils_output_limit.py -v
```

Expected:
- PASS

- [ ] **Step 2: Run the broader regression set**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest \
  test_evaluate_mimo_full_protocol.py \
  test_evaluate_entrypoints.py \
  test_replay_segmentation.py \
  test_scene_evidence.py -v
```

Expected:
- PASS

### Task 5: Correct Smoke Commands

**Files:**
- No code changes
- Execution only

- [ ] **Step 1: Hard-only smoke on `hard_yes_ambi`, split `0`**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
export MIMO_API_KEY=YOUR_KEY
python - <<'PY'
from evaluate_mimo import create_mimo_client, patch_freegrasp_client, validate_mimo_supports_image_input
from evaluate_all import _subset_config
from evaluate_common import evaluate_subset

model_name = "mimo-v2.5"
client = create_mimo_client()
validate_mimo_supports_image_input(client, model_name)
patch_freegrasp_client(client)

config = _subset_config(
    "hard_yes_ambi",
    prompt_variant="legacy_old",
    mimo_retry_mode="id_repair",
    segmentation_variant="point_retry",
    subset_policy="unified_hard_safe_v1",
)

print(config)
score = evaluate_subset(
    "hard_yes_ambi",
    selected_split="0",
    output_dir="data/output/ablation_matrix/UHS1_smoke_hard_yes_split0",
    prepare_molmo=False,
    model_name=model_name,
    prompt_variant=config["prompt_variant"],
    max_output_tokens=1024,
    resume=True,
    mimo_retry_mode=config["mimo_retry_mode"],
    segmentation_variant=config["segmentation_variant"],
    routing_variant=config.get("routing_variant", "none"),
    feature_source=config.get("feature_source", "none"),
    protocol_ablation=config.get("protocol_ablation", "full"),
)
print(score)
PY
```

Expected:
- Only `hard_yes_ambi` split `0` runs
- output written to `data/output/ablation_matrix/UHS1_smoke_hard_yes_split0`

- [ ] **Step 2: Hard-only smoke on `hard_no_ambi`, split `0`**

Run the same command with:

```python
config = _subset_config(..., subset_policy="unified_hard_safe_v1")
score = evaluate_subset("hard_no_ambi", selected_split="0", ...)
```

Expected:
- Only `hard_no_ambi` split `0` runs

- [ ] **Step 3: Only after smoke looks sane, run the full split-0 protocol**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
export MIMO_API_KEY=YOUR_KEY
python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy unified_hard_safe_v1 \
  --run-root data/output/ablation_matrix/UHS1_split0 \
  --splits 0 \
  --reuse-molmo \
  --resume
```

Expected:
- This is the first command that runs all six subsets for split `0`

## Stop Conditions

- Stop immediately if any hard-safe ablation name still errors as `Unknown protocol_ablation`
- Stop immediately if `hard_fallback_applied` never appears in hard details rows
- Stop immediately if the smoke command writes results for more than one subset
- Do not launch `evaluate_mimo_full_protocol.py` until the hard-only smoke commands complete
