# EGHC No-Mask-Repair Split-0 Ablation

Date: 2026-07-02

## Hypothesis

If the split-0 SSR gain of EGHC3_v3 is partly caused by point-constrained mask
repair, then disabling `eghc_mask_repair_v1` while keeping the same EGHC
routing, consensus guard, model, Molmo cache, and split should reduce SSR more
than RSR.

This is a component ablation only. It is not a candidate main method.

## Command

```bash
run="data/output/ablation_matrix/eghc_consensus_no_mask_repair_v1_split0"
setsid .venv/bin/python -u evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy eghc_consensus_no_mask_repair_v1 \
  --splits 0 \
  --reuse-molmo \
  --resume \
  --run-root "$run" \
  --skip-mimo-preflight \
  > "$run/nohup.log" 2>&1 < /dev/null &
```

## Configuration

| Field | Value |
|---|---|
| Run directory | `data/output/ablation_matrix/eghc_consensus_no_mask_repair_v1_split0` |
| Entry point | `evaluate_mimo_full_protocol.py` |
| Model | `mimo-v2.5` |
| Split | `0` |
| Samples | 300 |
| Molmo cache policy | reuse existing |
| Prompt/protocol | EGHC3_v3 consensus policy |
| Routing | `evidence_gated_cascade` |
| Route guard | `eghc_consensus_v1` |
| Feature source | `deployable_predicted` |
| Segmentation | `baseline` |
| Protocol ablation | `no_mask_repair` |
| GT features | false |
| Benchmark difficulty label | false |
| Max output tokens | 1024 |

## Run Integrity

Two partial `medium_no_ambi` attempts were excluded from the active outputs and
retained only as debugging provenance:

| Backup directory | Reason |
|---|---|
| `failed_json_import_20260702_000318` | `utils/utils.py` was missing `import json`, causing JSON parsing failures |
| `failed_missing_qwen_key_20260702_000521` | consensus adjudication could not call DashScope before the API key was exported |

The final active split output contains 300 rows. The final log contains no
remaining `Traceback`, missing-key, or `json is not defined` failures.

## Result

| Subset | N | RSR | SSR |
|---|---:|---:|---:|
| Easy, no ambiguity | 50 | 96.00% | 68.00% |
| Easy, ambiguity | 50 | 80.00% | 64.00% |
| Medium, no ambiguity | 50 | 62.00% | 54.00% |
| Medium, ambiguity | 50 | 74.00% | 60.00% |
| Hard, no ambiguity | 50 | 26.00% | 28.00% |
| Hard, ambiguity | 50 | 32.00% | 30.00% |
| **Overall** | **300** | **61.67%** | **50.67%** |

Call budget:

| Metric | Value |
|---|---:|
| Reasoning calls | 638 |
| Router calls | 300 |
| Repair calls | 20 |
| Calls per sample | 2.13 |

## Split-0 Comparison

| Method | Routing | Segmentation | Calls/sample | RSR | SSR |
|---|---|---|---:|---:|---:|
| S0 original protocol | none | baseline | 1.00 | 58.33% | 47.67% |
| Original + budget-2 vote | none | baseline | 2.00 | 56.67% | 46.33% |
| EGHC3_v3 no mask repair | evidence-gated cascade | baseline | 2.13 | 61.67% | 50.67% |
| EGHC3_v3 full | evidence-gated cascade | EGHC mask repair | 2.10 | 61.00% | 56.00% |
| S1 oracle | oracle/difficulty-assisted | repair path | 1.34 | 69.00% | 62.67% |

Direct comparison against full EGHC3_v3 on split 0:

| Comparison | RSR delta | SSR delta | Interpretation |
|---|---:|---:|---|
| No mask repair - EGHC3_v3 | +0.67 pp | -5.33 pp | Mask repair primarily improves segmentation consistency rather than first-grasp ID selection |

## Interpretation

The no-mask-repair ablation supports the claim that EGHC3_v3's controlled SSR
gain is not only a routing effect. With the same EGHC routing and consensus
guard but baseline segmentation, split-0 RSR stays essentially unchanged while
SSR drops from 56.00% to 50.67%. This is consistent with the method design:
point-constrained mask repair ties the selected Molmo candidate to the final
segmentation mask and reduces correct-ID/failed-mask cases.

Because this ablation is split-0 only, it should be reported as component
evidence rather than as a full 900-sample statistical claim.

## Next

1. Add the row to the split-0 ablation table in the manuscript.
2. Run routing-specific split-0 ablations to separate routing/consensus effects
   from mask-repair effects.
