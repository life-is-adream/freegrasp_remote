# Main Experiment Results Table

Generated for T4 main-experiment closeout on 2026-07-04. This table is paper-facing and traces every controlled count to existing sample-level `out_*.json` files. No evaluation command or paid/API call was run to create this file.

## Metric contract

- Denominator: FreeGraspData full protocol, 3 splits × 6 subsets × 50 samples = `N=900`; each subset has `N=150`.
- `SSR`: count rows where `row[3] == 1`.
- `RSR`: count rows where `row[4] == 1`.
- All controlled rows below report `count/denominator (rate)` and were recomputed from sample-level JSON, not copied only from summaries.

## Table 1. Main controlled comparison

| Method / role | Source run | Deployable? | Uses GT features? | Uses benchmark difficulty? | N | RSR | SSR | Paper use |
|---|---|---:|---:|---:|---:|---:|---:|---|
| S0 original protocol (controlled same-cache baseline) | `data/output/ablation_matrix/S0/` | Yes | false | false | 900 | 521/900 (57.89%) | 428/900 (47.56%) | Controlled baseline under the same fixed Molmo cache. |
| EGHC3_v3 (proposed, deployable) | `data/output/ablation_matrix/EGHC3_v3_qwen35_full/` | Yes | false | false | 900 | 548/900 (60.89%) | 497/900 (55.22%) | Main paper method; strongest controlled claim is SSR gain over S0. |
| S1 oracle upper bound (diagnostic only) | `data/output/ablation_matrix/S1/` | No | true | true | 900 | 607/900 (67.44%) | 541/900 (60.11%) | Diagnostic oracle upper bound only; not deployable and not a main-method claim. |
| Original FreeGrasp GPT-4o reported baseline | prior-paper report as cited in `paper/sections/experiments.tex` | Yes | No | No | not sample-level re-audited here | 47.3% | 38.2% | Descriptive-only comparison; not paired and no local sample-level counts available in this closeout. |

Controlled deltas from audited counts:

| Comparison | ΔRSR | ΔSSR | Interpretation |
|---|---:|---:|---|
| EGHC3_v3 - S0 | +3.00 pp | +7.67 pp | Controlled same-cache improvement; RSR should be stated cautiously because the bootstrap lower bound reaches 0.00 pp. |
| S1 oracle - EGHC3_v3 | +6.56 pp | +4.89 pp | Remaining oracle headroom; diagnostic only. |

Scene-clustered bootstrap from `data/output/statistics/eghc3_bootstrap_ci.json`:

| Comparison | Metric | N | Clusters | Delta | 95% CI | Tail probability delta ≤ 0 |
|---|---|---:|---:|---:|---:|---:|
| EGHC3_v3 - S0 | RSR | 900 | 291 | +3.00 pp | [0.00, 5.95] pp | 0.02655 |
| EGHC3_v3 - S0 | SSR | 900 | 291 | +7.67 pp | [4.19, 11.33] pp | 0 |
| S1 - EGHC3_v3 | RSR | 900 | 291 | +6.56 pp | [3.41, 9.80] pp | 5e-05 |
| S1 - EGHC3_v3 | SSR | 900 | 291 | +4.89 pp | [1.86, 7.95] pp | 0.00095 |

## Table 2. EGHC3_v3 subset-level counts

| Subset | N | RSR | SSR | RSR-SSR gap |
|---|---:|---:|---:|---:|
| `easy_no_ambi` | 150 | 140/150 (93.33%) | 119/150 (79.33%) | 14.00 pp |
| `easy_yes_ambi` | 150 | 124/150 (82.67%) | 115/150 (76.67%) | 6.00 pp |
| `medium_no_ambi` | 150 | 90/150 (60.00%) | 85/150 (56.67%) | 3.33 pp |
| `medium_yes_ambi` | 150 | 95/150 (63.33%) | 94/150 (62.67%) | 0.67 pp |
| `hard_no_ambi` | 150 | 48/150 (32.00%) | 44/150 (29.33%) | 2.67 pp |
| `hard_yes_ambi` | 150 | 51/150 (34.00%) | 40/150 (26.67%) | 7.33 pp |
| **Overall** | **900** | **548/900 (60.89%)** | **497/900 (55.22%)** | **5.67 pp** |

## Table 3. Controlled subset deltas: EGHC3_v3 minus S0

| Subset | ΔRSR | ΔSSR | EGHC3_v3 RSR | S0 RSR | EGHC3_v3 SSR | S0 SSR |
|---|---:|---:|---:|---:|---:|---:|
| `easy_no_ambi` | +8.67 pp | +13.33 pp | 140/150 (93.33%) | 127/150 (84.67%) | 119/150 (79.33%) | 99/150 (66.00%) |
| `easy_yes_ambi` | +1.33 pp | +7.33 pp | 124/150 (82.67%) | 122/150 (81.33%) | 115/150 (76.67%) | 104/150 (69.33%) |
| `medium_no_ambi` | +0.00 pp | +7.33 pp | 90/150 (60.00%) | 90/150 (60.00%) | 85/150 (56.67%) | 74/150 (49.33%) |
| `medium_yes_ambi` | +5.33 pp | +8.67 pp | 95/150 (63.33%) | 87/150 (58.00%) | 94/150 (62.67%) | 81/150 (54.00%) |
| `hard_no_ambi` | +2.67 pp | +4.67 pp | 48/150 (32.00%) | 44/150 (29.33%) | 44/150 (29.33%) | 37/150 (24.67%) |
| `hard_yes_ambi` | +0.00 pp | +4.67 pp | 51/150 (34.00%) | 51/150 (34.00%) | 40/150 (26.67%) | 33/150 (22.00%) |

## Provenance and caveats for manuscript use

- Current repository HEAD at closeout: `5b5dd3fcee860f4aa56e35b34b6110882479068b`.
- Main run manifest commit: `7a34492e34be45a8d5141093e69c68a4b0f1f44b`; manifest records `dirty_worktree=true`, so this is not a clean-checkout reproducibility claim.
- Manifest creation time: `2026-06-28T11:06:50.010917+00:00`; `full_protocol_summary.json` filesystem mtime observed as `2026-06-29 03:24:38 CST`.
- Fixed Molmo cache SHA-256: `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed` (prefix `705d0883`); summary records `molmo_cache_policy=reuse_existing`. This audit did not regenerate cache contents.
- Main method provenance: `feature_source=deployable_predicted`, `routing_variant=evidence_gated_cascade`, `route_guard_variant=eghc_consensus_v1`, `segmentation_variant=eghc_mask_repair_v1`, `uses_gt_features=False`, `uses_benchmark_difficulty=False`.
- Call budget from summary: `1889` reasoning calls + `900` router calls + `59` repair calls = `3.16` total recorded calls/sample. The summary field `calls_per_sample=2.10` counts reasoning calls/sample only; use the total recorded calls/sample when comparing to the call-budget table.
- Missing item: no raw console `run_log.txt` was present at closeout; see `paper/main_experiment_provenance_run_log.md` for the reconstructed provenance note. Do not present it as raw console output.
- Descriptive-only prior-paper GPT-4o row lacks local sample-level JSON in this repository closeout, so counts and denominator were not re-audited here.
