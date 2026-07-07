# No-Verifier Ablation Run Log

Created on 2026-07-06 to document the new `eghc_consensus_no_verifier_v1`
mechanism check requested after internal review. This file records current
run history, invalidated partial runs, and the final audited split-0 result.
Only the section titled "Final audit on 2026-07-07" is citable as the completed
ablation evidence.

## Purpose

- Test whether EGHC's constrained Qwen verifier is an isolatable mechanism
  rather than an inseparable part of the routing/mask-repair pipeline.
- Keep evidence boundaries unchanged: deployable predicted features, no
  ground-truth routing features, no benchmark difficulty as inference evidence.
- Disable only verifier/adjudication while preserving evidence-gated routing,
  consensus guard, and mask repair.

## Code changes under test

- `evaluate_all.py`
  - Adds `eghc_consensus_no_verifier_v1` to `--subset-policy`.
  - Maps the policy to `protocol_ablation="no_verifier"`.
- `evaluate_mimo_full_protocol.py`
  - Allows the same policy in the full protocol runner.
- `utils/utils.py`
  - Adds `no_verifier` as a valid protocol ablation.
  - Skips Qwen adjudication and records
    `qwen_adjudication.decision="skipped_no_verifier_ablation"`.
- `models/langsam/GroundingDINO/.../bertwarper.py`
  - Adds compatibility for `transformers 5.12.1`, where `BertModel` no longer
    exposes `get_head_mask`.
  - Avoids registering the wrapped BertModel as `_bert_model`, which would
    corrupt GroundingDINO checkpoint keys.
- `models/langsam/GroundingDINO/.../ms_deform_attn.py`
  - Falls back to the Python deformable-attention implementation when the
    custom `_C` extension is unavailable, even if CUDA tensors are present.

## Verification completed

```text
.venv/bin/python -m unittest \
  test_evaluate_entrypoints.py \
  test_langsam_compat.py \
  test_ms_deform_attn_compat.py \
  test_eghc_adjudicator.py
```

Result: 20 tests passed.

Smoke command:

```text
.venv/bin/python evaluate_all.py \
  --subset-policy eghc_consensus_no_verifier_v1 \
  --subsets easy_no_ambi \
  --max-rows-per-subset 1 \
  --run-dir data/output/eghc_consensus_no_verifier_smoke2 \
  --reuse-molmo \
  --no-resume
```

Smoke result:

- Completed without runtime error.
- `summary.json` records `subset_policy="eghc_consensus_no_verifier_v1"`.
- `details_easy_no_ambi.json` records `protocol_ablation="no_verifier"`.
- `qwen_adjudication.decision="skipped_no_verifier_ablation"`.
- The sample-level outcome was RSR 0 / SSR 0; this is not interpreted as an
  ablation result because N=1.

## Invalidated partial runs

Two partial runs were invalidated and archived instead of reused:

- `data/output/eghc_consensus_no_verifier_split0_invalid_pre_parser_repair_20260707`
  - Problem: early no-verifier partial output had `selected_object_id=None`
    in all audited rows, producing artificial RSR=0 while SSR could still pass.
  - Action: stopped the process and added a deterministic parser repair for
    direct-target planner JSON with `first_grasp_object_id=null` but a valid
    `target_resolution.target_object_id`.
- `data/output/eghc_consensus_no_verifier_split0_invalid_max_tokens64_20260707`
  - Problem: `evaluate_all.py` defaulted to `max_output_tokens=64`, truncating
    target-first JSON before the object ID could be parsed.
  - Action: stopped the process and restarted split-0 with
    `--max-output-tokens 1024`, matching the main-run token budget.

## Current split-0 run in progress

Historical note: this section records the live run state before completion. It
is retained for provenance only; use the final audit section below for paper
numbers.

Command launched in background:

```text
.venv/bin/python evaluate_all.py \
  --subset-policy eghc_consensus_no_verifier_v1 \
  --max-output-tokens 1024 \
  --run-dir data/output/eghc_consensus_no_verifier_split0 \
  --reuse-molmo \
  --no-resume
```

Runtime artifacts:

- Process: `evaluate_all.py --subset-policy eghc_consensus_no_verifier_v1`
- Log: `logs/eghc_consensus_no_verifier_split0.log`
- Output directory: `data/output/eghc_consensus_no_verifier_split0`

Early sanity check on the current 1024-token run:

- `easy_no_ambi`: 10 rows produced at check time.
- `selected_object_id` was non-null for all 10 detail rows.
- Interim counts: RSR 9/10, SSR 8/10.
- `qwen_adjudication.decision`: `skipped_no_verifier_ablation` for all checked rows.

Progress check after about 48 minutes elapsed:

| Subset | rows | RSR count | SSR count | malformed rows |
|---|---:|---:|---:|---:|
| `easy_no_ambi` | 50 | 47 | 38 | 0 |
| `easy_yes_ambi` | 50 | 44 | 44 | 0 |
| `medium_no_ambi` | 8 | 3 | 2 | 0 |

The process was still running and `summary.json` was not yet present.

Progress check after about 85 minutes elapsed:

| Subset | rows | RSR count | SSR count | malformed rows |
|---|---:|---:|---:|---:|
| `easy_no_ambi` | 50 | 47 | 38 | 0 |
| `easy_yes_ambi` | 50 | 44 | 44 | 0 |
| `medium_no_ambi` | 35 | 19 | 17 | 0 |
| **Total so far** | **135** | **110** | **99** | **0** |

The process was still running and `summary.json` was not yet present. These
partial counts remain non-citable.

Progress check after resume with `FREEGRASP_SAMPLE_TIMEOUT_SECONDS=300`:

| Subset | rows | RSR count | SSR count | malformed rows |
|---|---:|---:|---:|---:|
| `easy_no_ambi` | 50 | 47 | 38 | 0 |
| `easy_yes_ambi` | 50 | 44 | 44 | 0 |
| `medium_no_ambi` | 50 | 25 | 23 | 0 |
| `medium_yes_ambi` | 27 | 13 | 13 | 0 |
| **Total so far** | **177** | **129** | **118** | **0** |

The process was still running and `summary.json` was not yet present. These
partial counts remain non-citable.

Progress check after about 144 minutes elapsed:

| Subset | rows | RSR count | SSR count |
|---|---:|---:|---:|
| `easy_no_ambi` | 50 | 47 | 38 |
| `easy_yes_ambi` | 50 | 44 | 44 |
| `medium_no_ambi` | 50 | 25 | 23 |
| `medium_yes_ambi` | 13 | 6 | 6 |
| **Total so far** | **163** | **122** | **111** |

The process was still running and `summary.json` was not yet present. These
partial counts remain non-citable.

## Superseded partial progress audit on 2026-07-07

The table below belongs to the invalidated pre-parser-repair run. It is retained
only to document why the run was rejected.

The split-0 process was still running at the time of this audit. Partial rows
must not be reported as ablation results.

Completed or partially completed files:

| Subset | out rows | detail rows | malformed rows | RSR count | SSR count | runtime errors |
|---|---:|---:|---:|---:|---:|---:|
| `easy_no_ambi` | 50 | 50 | 0 | 0 | 31 | 0 |
| `easy_yes_ambi` | 38 | 38 | 0 | 0 | 29 | 0 |

Field checks on available `details_*.json` rows:

- `protocol_ablation`: `no_verifier` for all audited rows.
- `qwen_adjudication.decision`: `skipped_no_verifier_ablation` for all audited rows.
- No malformed `out_*.json` rows were found in the completed/partial files.
- `summary.json` was not yet present, so the split-0 run is incomplete.

## Paper-use boundary

The final run completed and was audited. It may be cited only as a split-0
mechanism check, not as a full 900-sample controlled conclusion.

## Final audit on 2026-07-07

Final output directory:

- `data/output/eghc_consensus_no_verifier_split0`

Final configuration from `summary.json`:

- `subset_policy`: `eghc_consensus_no_verifier_v1`
- `model`: `qwen3.6-flash`
- `max_output_tokens`: 1024
- `routing_variant`: `evidence_gated_cascade`
- `feature_source`: `deployable_predicted`
- `protocol_ablation`: `no_verifier`
- `route_guard_variant`: `eghc_consensus_v1`
- `segmentation_variant`: `eghc_mask_repair_v1`
- `uses_gt_features`: false
- `uses_benchmark_difficulty`: false

Final counts:

| Subset | rows | detail rows | RSR count | RSR | SSR count | SSR | malformed rows | runtime errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `easy_no_ambi` | 50 | 50 | 47 | 94.00% | 38 | 76.00% | 0 | 0 |
| `easy_yes_ambi` | 50 | 50 | 44 | 88.00% | 44 | 88.00% | 0 | 0 |
| `medium_no_ambi` | 50 | 50 | 25 | 50.00% | 23 | 46.00% | 0 | 0 |
| `medium_yes_ambi` | 50 | 50 | 21 | 42.00% | 22 | 44.00% | 0 | 1 |
| `hard_no_ambi` | 50 | 50 | 14 | 28.00% | 12 | 24.00% | 0 | 1 |
| `hard_yes_ambi` | 50 | 50 | 9 | 18.00% | 9 | 18.00% | 0 | 0 |
| **Total** | **300** | **300** | **160** | **53.33%** | **148** | **49.33%** | **0** | **2** |

Evidence-boundary audit:

- All 300 detail rows record `protocol_ablation="no_verifier"`.
- 299 rows record `qwen_adjudication.decision="skipped_no_verifier_ablation"`.
- One `hard_no_ambi` row has a runtime error before adjudication metadata was
  attached; it is retained as a failed sample and does not use verifier output.
- `summary.json` records `uses_gt_features=false` and
  `uses_benchmark_difficulty=false`.

Comparison against existing split-0 rows:

| Run | N | RSR | SSR |
|---|---:|---:|---:|
| S0 split 0 | 300 | 58.33% | 47.67% |
| EGHC3_v3 split 0 | 300 | 61.00% | 56.00% |
| EGHC3_v3 no verifier split 0 | 300 | 53.33% | 49.33% |

Interpretation:

- Disabling only the constrained verifier lowers EGHC3_v3 by 7.67 pp RSR and
  6.67 pp SSR on split 0.
- The result supports treating the verifier as a useful bounded decision gate,
  not merely as extra call budget.
- Because this is split 0 only, the manuscript should phrase this as a
  mechanism check rather than a full-protocol causal estimate.
