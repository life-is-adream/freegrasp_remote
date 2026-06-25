# 2026-06-25 UHS1 Split-0 Failure Analysis

## Status

Completed offline/result analysis on the paid `unified_hard_safe_v1` split-0 run and
the preceding hard-only smoke runs.

This document records what happened, what the numbers support, and what they do
not support.

## Question

Does `unified_hard_safe_v1` fail mainly because of segmentation, because of hard-scene
reasoning, or because of transient MiMo service faults?

## Commands

Hard-only smoke:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python - <<'PY'
from evaluate_mimo import create_mimo_client, patch_freegrasp_client, validate_mimo_supports_image_input
from evaluate_all import _subset_config
from evaluate_common import evaluate_subset

model_name = "mimo-v2.5"
client = create_mimo_client()
validate_mimo_supports_image_input(client, model_name)
patch_freegrasp_client(client)

for subset_name, output_dir in [
    ("hard_yes_ambi", "data/output/ablation_matrix/UHS1_smoke_hard_yes_split0"),
    ("hard_no_ambi", "data/output/ablation_matrix/UHS1_smoke_hard_no_split0"),
]:
    config = _subset_config(
        subset_name,
        prompt_variant="legacy_old",
        mimo_retry_mode="id_repair",
        segmentation_variant="point_retry",
        subset_policy="unified_hard_safe_v1",
    )
    score = evaluate_subset(
        subset_name,
        selected_split="0",
        output_dir=output_dir,
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
    print(subset_name, score)
PY
```

Full split-0 run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy unified_hard_safe_v1 \
  --run-root data/output/ablation_matrix/UHS1_split0 \
  --splits 0 \
  --reuse-molmo \
  --resume
```

## Configuration And Provenance

- Branch: `experiment/routing-v2`
- Git commit: `9318a0860c222f5a90af1996e52a1c9fc873d478`
- Dirty worktree: `true`
- Model: `mimo-v2.5`
- Max output tokens: `1024`
- Split: `0`
- Subset policy: `unified_hard_safe_v1`
- Prompt variant: `unified_hard_safe_v1_json`
- Retry mode: `id_repair`
- Segmentation variant: `point_retry`
- Routing variant: `none`
- Manifest feature source: `none`
- Manifest `uses_gt_features`: `false`
- Manifest `uses_benchmark_difficulty`: `false`
- Molmo cache: reused existing cache

## Full Split-0 Results

| Subset | n | API 500 | RSR | SSR | RSR-only | Both fail |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| easy_no_ambi | 50 | 1 | 44/50 = 88% | 38/50 = 76% | 6 | 6 |
| easy_yes_ambi | 50 | 2 | 41/50 = 82% | 39/50 = 78% | 3 | 8 |
| medium_no_ambi | 50 | 0 | 30/50 = 60% | 24/50 = 48% | 8 | 18 |
| medium_yes_ambi | 50 | 2 | 29/50 = 58% | 27/50 = 54% | 3 | 20 |
| hard_no_ambi | 50 | 0 | 18/50 = 36% | 14/50 = 28% | 4 | 32 |
| hard_yes_ambi | 50 | 0 | 21/50 = 42% | 17/50 = 34% | 7 | 26 |
| overall | 300 | 5 | 183/300 = 61% | 159/300 = 53% | 31 | 110 |

Difficulty-grouped totals:

| Difficulty | n | RSR | SSR |
| --- | ---: | ---: | ---: |
| easy | 100 | 85% | 77% |
| medium | 100 | 59% | 51% |
| hard | 100 | 39% | 31% |

## Hard-Subset Breakdown From Raw `reasoning_json`

The persisted detail rows do not keep the post-repair fields
`hard_fallback_applied`, `action`, `pre_repair_action`, or `target_status` at
top level. However, the raw `reasoning_json` still contains the model's original
status/action proposal, so the hard subsets can still be analyzed from those
raw fields.

### Hard No-Ambi

| Raw status + action | n | RSR | SSR |
| --- | ---: | ---: | ---: |
| `visible_but_blocked` + `remove_blocker` | 35 | 16/35 = 45.7% | 13/35 = 37.1% |
| `uncertain` + `remove_blocker` | 3 | 2/3 = 66.7% | 1/3 = 33.3% |
| `free_visible` + `grasp_target` | 12 | 0/12 = 0% | 0/12 = 0% |

### Hard Yes-Ambi

| Raw status + action | n | RSR | SSR |
| --- | ---: | ---: | ---: |
| `visible_but_blocked` + `remove_blocker` | 31 | 14/31 = 45.2% | 11/31 = 35.5% |
| `uncertain` + `remove_blocker` | 7 | 4/7 = 57.1% | 3/7 = 42.9% |
| `free_visible` + `grasp_target` | 12 | 3/12 = 25.0% | 3/12 = 25.0% |

### Combined Hard Takeaways

- Raw `remove_blocker`: `76` samples, `RSR 36/76 = 47.4%`, `SSR 28/76 = 36.8%`
- Raw `grasp_target`: `24` samples, `RSR 3/24 = 12.5%`, `SSR 3/24 = 12.5%`
- Hard `free_visible` confidence values were all high: `0.90` (`3`), `0.95` (`18`), `1.00` (`3`)
- Therefore, raising the fallback confidence threshold from `0.70` to `0.85`
  would not catch the dominant hard direct-grasp failures. Those bad direct
  calls were already high-confidence.

## MiMo 500 Analysis

### Full Split-0 Run

There were `5` MiMo API `500` rows out of `300`, all outside the hard subsets:

- `easy_no_ambi`: `(7022, 5)`
- `easy_yes_ambi`: `(1393, 6)`, `(3033, 1)`
- `medium_yes_ambi`: `(1524, 3)`, `(2163, 6)`

If those `5` rows are excluded from the denominator purely to estimate service
noise magnitude, the same run becomes:

- official: `RSR 61.0%`, `SSR 53.0%`
- excluding API 500 rows only: `RSR 62.0%`, `SSR 53.9%`

This is at most about a `+1 pp` effect on headline performance.

### Hard-Only Smoke Comparison

Hard-only smoke results:

| Subset | Smoke RSR | Smoke SSR | Full RSR | Full SSR | Delta RSR | Delta SSR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard_no_ambi | 28% | 24% | 36% | 28% | +8 pp | +4 pp |
| hard_yes_ambi | 44% | 34% | 42% | 34% | -2 pp | 0 pp |

The smoke runs had hard-scene MiMo `500` rows on:

- `hard_yes_ambi`: `(5076, 3)`
- `hard_no_ambi`: `(1996, 6)`, `(5155, 5)`, `(6760, 5)`, `(6807, 1)`, `(7310, 1)`

Those same hard scenes did not fail with API `500` in the full split-0 run.
This is strong evidence that the MiMo `500` errors are transient service-side
faults, not deterministic corruption of those specific hard samples.

## Segmentation And Parsing Diagnostics

- Hard `RSR-only` rows: `11/100`
- Hard `both fail` rows: `58/100`
- Overall `RSR-only` rows: `31/300`
- Overall `both fail` rows: `110/300`
- Hard `langsam_failure_reason == no_retry_mask_contained_molmo_point`: `16/100`
- Overall `langsam_failure_reason == no_retry_mask_contained_molmo_point`: `39/300`
- Hard `parse_status == valid_id`: `100/100`
- Overall `parse_status == valid_id`: `295/300`
- Overall `parse_status == None`: `5/300`, exactly matching the `5` API `500` rows

This means:

1. The dominant hard failure mode is still reasoning or target/blocker choice,
   not segmentation alone.
2. Segmentation is still a real secondary bottleneck, especially via point-to-mask
   failures and `RSR-only` rows.
3. Invalid-ID repair is not the current primary blocker for this run, because
   every hard row that actually produced a model response had `parse_status == valid_id`.

## Provenance Gaps

Two metadata issues remain in the saved artifacts:

1. `details_*.json` rows still record `reasoning.feature_source == "oracle_feature"`
   even though the run manifest records `feature_source == "none"` and the
   command did not authorize GT inference features.
2. The detail rows do not persist post-repair fields such as:
   - `hard_fallback_applied`
   - `pre_repair_action`
   - repaired `action`
   - repaired `target_status`

These gaps do not invalidate the metric table above, but they do weaken
auditability. In particular, the run supports statements about the model's raw
status/action proposals, but not a fully auditable count of how often the
deterministic hard-fallback repair was actually applied downstream.

## Interpretation

The split-0 run supports the same big conclusion as the earlier smoke and manual
inspection:

- `unified_hard_safe_v1` is strong on easy, moderate on medium, and still weak
  on hard.
- The primary hard-scene bottleneck is not segmentation by itself. It is the
  model's scene interpretation and blocker selection chain.
- Raw direct hard decisions remain especially unsafe. Combined hard
  `free_visible + grasp_target` produced only `3/24` reasoning successes.
- Blocker-first behavior is better than direct on hard, but still only reaches
  `36/76` reasoning success, so blocker identity and blocker-choice ranking
  remain unresolved.
- MiMo API `500` faults are real but secondary. They introduce noise, especially
  in smoke runs, but they do not explain the hard-scene performance ceiling.

## Recommended Next Actions

1. Do not prioritize a simple confidence-threshold increase as the main fix.
   The worst hard direct-grasp failures were already high-confidence.
2. Prioritize analyses or ablations that suppress unsupported hard direct calls
   and improve blocker ranking/selection.
3. Treat segmentation as a secondary axis. It matters, but it is not the main
   explanation for the hard-scene gap.
4. Fix artifact logging before claiming strong causal evidence for hard fallback:
   persist `hard_fallback_applied`, repaired `action`, and repaired
   `target_status` in detail rows.
5. If a cleaner overall headline number is needed for reporting, targeted reruns
   of the `5` API `500` rows may be worthwhile. If the goal is specifically to
   understand the hard bottleneck, that rerun is lower priority because the full
   split-0 hard subsets had `0` API `500` rows.

## Artifacts

- Full summary JSON:
  `/home/public/zb/FreeGrasp_code-freegrasp_codex/data/output/ablation_matrix/UHS1_split0/full_protocol_summary.json`
- Full run manifest:
  `/home/public/zb/FreeGrasp_code-freegrasp_codex/data/output/ablation_matrix/UHS1_split0/run_manifest.json`
- Full split-0 outputs:
  `/home/public/zb/FreeGrasp_code-freegrasp_codex/data/output/ablation_matrix/UHS1_split0/split_0`
- Hard smoke outputs:
  - `/home/public/zb/FreeGrasp_code-freegrasp_codex/data/output/ablation_matrix/UHS1_smoke_hard_no_split0`
  - `/home/public/zb/FreeGrasp_code-freegrasp_codex/data/output/ablation_matrix/UHS1_smoke_hard_yes_split0`
