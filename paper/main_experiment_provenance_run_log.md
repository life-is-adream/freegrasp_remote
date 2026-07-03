# Main Experiment Provenance / Reconstructed Run Log

Created for T4 main-experiment closeout on 2026-07-04. This is a reconstructed provenance note from existing artifacts, not a raw console transcript. No evaluation, VLM/API call, cache clearing, or new `out_*.json` generation was performed while creating it.

## Closeout identity

- Repository: `/home/public/zb/FreeGrasp_code-freegrasp_codex`.
- Current HEAD during closeout: `5b5dd3fcee860f4aa56e35b34b6110882479068b`.
- Main run path: `data/output/ablation_matrix/EGHC3_v3_qwen35_full/`.
- Main run manifest commit: `7a34492e34be45a8d5141093e69c68a4b0f1f44b`.
- Manifest creation time: `2026-06-28T11:06:50.010917+00:00`.
- Manifest dirty worktree flag: `True`.
- Fixed Molmo cache SHA-256: `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed` (prefix `705d0883`).
- Summary cache policy: `reuse_existing`.

## Frozen method configuration

- `model`: `mimo-v2.5`
- `max_output_tokens`: `1024`
- `subset_policy`: `eghc_consensus_v1`
- `splits`: `['0', '1', '2']`
- `feature_source`: `deployable_predicted`
- `routing_variant`: `evidence_gated_cascade`
- `route_guard_variant`: `eghc_consensus_v1`
- `segmentation_variant`: `eghc_mask_repair_v1`
- `uses_gt_features`: `False`
- `uses_benchmark_difficulty`: `False`
- `guard_code_version`: `eghc-consensus-v1`

## Audited input files

Primary controlled sample-level files:

- `EGHC3_v3_qwen35_full`: `data/output/ablation_matrix/EGHC3_v3_qwen35_full/split_{0,1,2}/out_{easy_no_ambi,easy_yes_ambi,medium_no_ambi,medium_yes_ambi,hard_no_ambi,hard_yes_ambi}.json`
- `S0`: `data/output/ablation_matrix/S0/split_{0,1,2}/out_{easy_no_ambi,easy_yes_ambi,medium_no_ambi,medium_yes_ambi,hard_no_ambi,hard_yes_ambi}.json`
- `S1`: `data/output/ablation_matrix/S1/split_{0,1,2}/out_{easy_no_ambi,easy_yes_ambi,medium_no_ambi,medium_yes_ambi,hard_no_ambi,hard_yes_ambi}.json`

Summary/statistical artifacts:

- `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json` — sha256 `6a47f8c6a2e045b10700c18111328f563df0a598dcb29f219d83d1ab80cb89d7`
- `data/output/ablation_matrix/EGHC3_v3_qwen35_full/run_manifest.json` — sha256 `137cba79df4744327cf604f168aa6d7884ff0d88b95f4bbce384d892d08b4650`
- `data/output/ablation_matrix/S0/full_protocol_summary.json` — sha256 `1042f2e499fcb63c2b5ff6631b0b113207afb058bdfe9b9cb0771061b6095473`
- `data/output/ablation_matrix/S1/full_protocol_summary.json` — sha256 `337185bb8514e37630493238d206642bdaf0b282b45b53e677ed9a73478bae52`
- `data/output/statistics/eghc3_bootstrap_ci.json` — sha256 `11abfde471aef805973d1b84b221dc62ef9f94a8f4e66247799267fb71a58039`
- `data/output/statistics/ral_ablation_call_budget_with_routing.md` — sha256 `0c813f18df19655bf5d2555568af84d3d2d848b991e2cacc36c7e37f09dbc326`

## Read-only commands used during this closeout

- READ ONLY: `pwd; git rev-parse HEAD; git status --short; sed -n ... docs/superpowers/plans/2026-07-04-ral-master-plan.md`
- READ ONLY: `sed -n ... docs/superpowers/plans/daily_report_2026-07-03.md; sed -n ... docs/superpowers/plans/2026-06-18-ral-submission-plan.md; sed -n ... docs/experiments/ablation_table.md`
- READ ONLY: `find docs/superpowers/plans -maxdepth 1 -type f; find docs/experiments -maxdepth 2 -type f; find data/output -path "*full_protocol_summary.json"`
- READ ONLY: `python3 read-only JSON inspection of full_protocol_summary.json, run_manifest.json, bootstrap CI, and call-budget markdown`
- READ ONLY: `python3 read-only recomputation of SSR/RSR from sample-level out_*.json using SSR=row[3]==1 and RSR=row[4]==1`
- READ ONLY: `python3 read-only grep-equivalent search in paper/docs/statistics for prior-paper GPT-4o and existing manuscript values`

Write commands used:

- WROTE ONLY: `python3` file creation for `paper/results_main_table.md` and `paper/main_experiment_provenance_run_log.md`.

## Commands intentionally not run

- NOT RUN: `evaluate_all.py`
- NOT RUN: `reasoning_eval.py full evaluation over large subsets`
- NOT RUN: `evaluate_mimo_full_protocol.py`
- NOT RUN: `evaluate_mimo.py when it could generate new out_*.json`
- NOT RUN: `MiMo/Qwen/GPT/OpenAI-compatible API calls`
- NOT RUN: `cache clearing, fresh Molmo regeneration, or deletion of output/cache files`
- NOT RUN: `git commit, git reset, git checkout, or revert`

## Recomputed metric results

| Run | N | Malformed rows | RSR | SSR |
|---|---:|---:|---:|---:|
| `EGHC3_v3_qwen35_full` | 900 | 0 | 548/900 (60.89%) | 497/900 (55.22%) |
| `S0` | 900 | 0 | 521/900 (57.89%) | 428/900 (47.56%) |
| `S1` | 900 | 0 | 607/900 (67.44%) | 541/900 (60.11%) |

## Completeness checks

- `EGHC3_v3_qwen35_full`: 3 splits × 6 subsets × 50 rows = 900 sample rows; all expected `out_*.json` and `details_*.json` files were present in the main run directory listing.
- `S0` and `S1`: sample-level recomputation also found 900 rows each and 0 malformed rows.
- Main-run `run_log.txt` was absent at closeout, so this file is explicitly labeled as reconstructed provenance rather than raw console output.

## Non-reproducibility / missing-risk notes

- The main run manifest records `dirty_worktree=true` at run creation; exact recreation from `git_commit` alone may not reproduce the same code state.
- The audit used a fixed/reused Molmo cache identified by SHA-256 and did not verify cache internals beyond recorded hashes and output consistency.
- Raw console logs for the original full run were not found; timing, retries, and transient API/server messages cannot be reconstructed beyond artifact metadata and summary counters.
- Original FreeGrasp GPT-4o prior-paper rates in the manuscript are descriptive only; this closeout did not locate local sample-level GPT-4o output rows for count-level auditing.
- Real-robot/UR5 grasp success remains unmeasured and must not be inferred from RSR/SSR.
