# 2026-06-22 Stage 1 Ablation Readiness

Status: Running. Paid inference was approved with `RUN_PAID_INFERENCE`.

Actual start: 2026-06-23 00:01 CST.

The `freegrasp` conda environment could import pandas but its full LangSAM
initialization did not complete reliably through the remote execution channel.
The run therefore uses the project `.venv`, which is the environment that
previously completed the v10 experiment. The persistent execution session uses
`.venv/bin/python` for both the matrix runner and child evaluators.

Initial verified progress:

- S0 manifest ID:
  `3bee2979a3e9dad1fac422a9ea8b1d309baa3145982c7426bad28e0ac834eb15`
- S0 split 0 `easy_no_ambi`: n=50, RSR=90.00%, SSR=68.00%.
- All observed MiMo preflight/sample requests returned HTTP 200.

## Hypotheses

- S0 measures the original FreeGrasp protocol with matched MiMo-v2.5 and
  1024-token settings.
- S1 is an oracle-routed, oracle-feature diagnostic upper bound and is not the
  deployable method.
- S2-S4 isolate count-only, pure-VLM, and predicted-geometry routing.
- S5-S7 remove blocker-first, geometry repair, and invalid-ID repair one at a
  time from S4.

## Fixed Configuration

- Branch: `freegrasp_codex`
- Environment: `/home/wyl/miniconda3/envs/freegrasp` (Python 3.10.18)
- Model: `mimo-v2.5`
- Maximum output tokens: 1024
- Dataset: 900 rows, 291 unique scenes, splits 0/1/2
- Molmo policy: reuse only
- Complete Molmo scene pairs: 291/291
- Complete NPZ files: 291/291
- Molmo cache SHA-256:
  `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed`
- Output root: `data/output/ablation_matrix`
- Primary metric: RSR
- Secondary metrics: SSR, mean IoU, calls/sample, failure categories

The worktree is intentionally dirty because the automatic router and v10
implementation have not been separated from earlier local research changes.
Every run manifest must record this fact and the current commit.

## Historical Anchors

- Original-protocol MiMo split-0 run:
  `mimo-v2.5_legacy_old_713_reuse_molmo`, n=300,
  RSR=56.33%, SSR=49.33%.
- Existing oracle-feature v10 run:
  `freegrasp_codex_v10_full_20260618_165628`, n=900,
  RSR=67.67%, SSR=60.33%, 1202 recorded POST calls.
- The historical v10 result is not evidence for the deployable automatic
  method because it uses benchmark routing/oracle features.

## Call Budget

- S0: approximately 900 calls.
- S1: approximately 1202 calls, based on the existing matched v10 run.
- S2: at least 1221 calls plus any invalid-ID repairs. The fixed cache has 30
  rows with fewer than 4 objects, 321 rows with 4-5 objects, and 549 rows with
  at least 6 objects.
- S3-S7: route-dependent. Each run is bounded by roughly 900-2700 calls.
- Conservative total Stage 1 range: approximately 7823-17402 calls before any
  failed-request retries.

Actual calls must be read from `details_*.json`, not inferred from the planned
configuration.

## Validity Gates

- Every reasoning run must contain 900 unique sample keys.
- Every run must match model, token limit, split list, and cache SHA-256.
- Automatic methods must report `uses_gt_features=false` and
  `uses_benchmark_difficulty=false`.
- S1 must be labeled `oracle_feature` in every paper table.
- A mismatch in cache or immutable run manifest must stop execution.
- Stage 1 execution requires both `--execute` and the literal confirmation
  `--confirm-paid-inference RUN_PAID_INFERENCE`.

## Launch Command

```bash
/home/wyl/miniconda3/envs/freegrasp/bin/python run_ablation_matrix.py \
  --stage 1 \
  --cache-sha256 705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed \
  --run-root data/output/ablation_matrix \
  --execute \
  --confirm-paid-inference RUN_PAID_INFERENCE
```

Do not launch this command until the user explicitly approves paid inference.
