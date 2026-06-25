# Outcome Policy Selector V1 Protocol

Date: 2026-06-25

Branch: `freegrasp_codex`

Purpose: hand off a safer next experiment to another agent. The goal is not to
match `Easy/Medium/Hard`; the goal is to select the protocol most likely to
make the current query succeed. If the selector is uncertain, choose the hardest
safe protocol.

## 1. Why This Protocol Exists

The depth-classifier route failed its no-leak audit:

- Row-random CV looked high because same-scene samples leaked across folds.
- Scene-grouped CV was low, showing weak cross-scene generalization.
- The fixed v2 router can use the correct query target, but difficulty
  classification is still the wrong optimization target.

The original FreeGrasp protocols can be strong. The hard part is not choosing a
global protocol for a whole scene; it is choosing a protocol for a specific
query target in that scene. One scene may contain both easy visible targets and
hard occluded targets. Therefore the selector must be query-conditioned.

## 2. Core Principle

Train and audit a query-conditioned outcome selector.

Instead of predicting:

```text
scene difficulty -> protocol
```

predict:

```text
(query, target, local geometry/depth/semantic evidence, candidate protocol)
    -> probability that RSR succeeds
```

At inference, score candidate protocols and select the best one.

If uncertainty is detected, select the hardest protocol:

```text
blocker_first / hard_blocker_first_v10
```

This favors hard-scene safety over easy-scene convenience.

## 3. Candidate Protocols

Start with three route modes already supported by the pipeline:

- `direct`: direct target grasp.
- `target_first`: target-focused reasoning with repair.
- `blocker_first`: hard-scene blocker-first reasoning.

For implementation, map them to the existing `route_mode` dispatch in
`utils/utils.py`. Do not invent new prompts in V1.

Recommended action order from easiest to hardest:

```text
direct < target_first < blocker_first
```

Hard fallback always chooses the hardest available action:

```text
uncertain -> blocker_first
```

## 4. Replay Table

Build a replay table from existing experiment outputs. This is a read-only
offline step and must not call MiMo.

Each row should represent one `(sample, protocol_candidate)` observation:

- `sample_key`: split, subset, source row or scene/object/annotation tuple.
- `scene_id`
- `query_object_id`
- `annotation`
- `candidate_protocol`: `direct`, `target_first`, or `blocker_first`
- `protocol_source_run`: e.g. `S0`, `S1`, `S4`, historical run name.
- `rsr_success`: `1` if `row[4] == 1`, else `0`.
- `ssr_success`: `1` if `row[3] == 1`, else `0`.
- query-conditioned features available without paid inference.

Preferred source runs:

- `data/output/ablation_matrix/S0`: original protocol baseline.
- `data/output/ablation_matrix/S1`: oracle-feature v10 diagnostic upper bound.
- `data/output/ablation_matrix/S4`: predicted-geometry automatic evidence.
- `data/output/ablation_matrix/S5-S7`: component ablations if complete.
- Existing single-policy historical runs may be used only if sample keys can be
  matched exactly and cache provenance is recorded.

Do not train directly on benchmark difficulty labels as the main target. They
can be included only as optional weak features or audit strata.

## 5. Query-Conditioned Features

Use features that describe the current target, not only the whole scene:

- number of visible Molmo objects;
- query target Molmo id validity;
- target depth statistics;
- target-vs-scene depth;
- number of objects in front of target;
- nearest object distance to target;
- same-class or same-label ambiguity if labels are available;
- target local crowding;
- predicted overlap / contact / depth occlusion if cached geometry exists;
- previous parser or repair risk flags if available from historical details.

Features must be computable without paid VLM calls. SAM-based geometry may be
used only when a cached geometry/evidence file exists or when the user approves
that offline SAM cost is acceptable.

## 6. Selector Model

Use a simple model first:

- tabular classifier or ranker;
- input: `(sample_features, candidate_protocol)`;
- output: `P(RSR success | sample, candidate_protocol)`;
- optional secondary output: `P(SSR success | sample, candidate_protocol)`.

A RandomForest, GradientBoosting, or calibrated logistic model is enough for
V1. Avoid deep models until the replay labels and validation protocol are
trusted.

Decision rule:

1. Score `direct`, `target_first`, and `blocker_first`.
2. Sort by predicted RSR success.
3. If confident, choose top-1.
4. If uncertain, choose `blocker_first`.

## 7. Uncertainty Gate

A sample is uncertain if any of the following are true:

- top-1 score is below `0.55`;
- top-1 minus top-2 margin is below `0.10`;
- target id is missing or feature extraction falls back;
- model ensemble disagrees on the top protocol;
- sample is out-of-distribution under scene-grouped validation diagnostics;
- candidate protocols have conflicting historical replay labels.

For uncertain samples:

```text
route_mode = blocker_first
uncertainty_fallback = hard
```

Do not downgrade uncertain samples to `direct`. The user explicitly prefers the
hardest protocol when the selector is unsure.

## 8. Offline Validation

No paid experiment may run until these audits are complete.

Required validation:

- Scene-grouped cross-validation on replay rows.
- Held-out split validation.
- Per-subset replay RSR estimate.
- Hard-subset replay RSR estimate.
- Uncertainty rate.
- Hard-fallback rate.
- Regret against replay oracle:
  `oracle_success - selected_success`.

Main metrics:

- selected replay RSR;
- selected replay SSR;
- hard subset replay RSR;
- oracle regret;
- percentage of samples routed to `blocker_first` by uncertainty.

Report row-random CV only as a diagnostic. It is not a headline result.

## 9. Offline Gates

Proceed to paid split-0 experiment only if all gates pass:

- Scene-grouped selected replay RSR is at least S0 replay RSR + 3 percentage
  points, or hard-subset replay RSR is at least S0 hard replay RSR + 5
  percentage points.
- Oracle regret is below 8 percentage points overall.
- Hard-subset oracle regret is below 12 percentage points.
- Uncertainty fallback does not route more than 70% of all samples to
  `blocker_first`, unless hard-subset gains justify it.
- No subset collapses below S0 replay RSR by more than 5 percentage points.

If gates fail, do not run MiMo. Improve features or abandon selector training
and return to protocol/segmentation improvements.

## 10. Paid Experiment Sequence

Only after offline gates pass:

1. Run split 0 only with reuse Molmo cache.
2. Compare against S0, S1, S4, D1, and depth_classifier_v2 audit outputs.
3. Stop if split-0 RSR is not above S0 split-0 RSR.
4. Run ablations only after the main selector beats S0:
   - no uncertainty fallback;
   - no query-depth features;
   - no geometry features;
   - no hard fallback.
5. Run full 900 only after split-0 and ablations support the method.

## 11. Stop Conditions

The supervising agent must stop immediately if:

- a command would call MiMo before offline gates pass;
- row-random CV is presented as the main evidence;
- sample keys do not match exactly across replay runs;
- any replay source mixes fresh-cache and reuse-cache results without
  provenance;
- uncertainty fallback is disabled or changed away from `blocker_first` without
  user approval;
- the script writes over existing S0/S1/S4/D1 outputs.

## 12. Implementation Targets

Expected new files:

- `build_outcome_policy_replay.py`
- `train_outcome_policy_selector.py`
- `audit_outcome_policy_selector.py`
- `models/outcome_policy_selector_v1.joblib`
- `data/output/outcome_policy_selector_v1/replay_table.csv`
- `data/output/outcome_policy_selector_v1/offline_audit.json`
- `docs/experiments/2026-06-25-outcome-policy-selector-v1-offline.md`

Expected code hooks after offline gates pass:

- `routing_variant="outcome_policy_selector"`
- `subset_policy="outcome_policy_selector_v1_auto"`
- ablations for no hard fallback and no feature families.

## 13. Execution Instructions for Supervising Agent

### 13.1 Start from the correct branch

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
git status --short --branch
```

Expected branch:

```text
freegrasp_codex
```

Do not modify `/home/public/zb/FreeGrasp_code-main`.

### 13.2 Confirm no paid inference is running

```bash
ps -ef | grep -E "evaluate_mimo|reasoning_eval|mimo|qwen|dashscope" | grep -v grep || true
```

If a paid run is active, stop and ask the user before starting anything.

### 13.3 Build replay table

After implementing `build_outcome_policy_replay.py`, run:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python build_outcome_policy_replay.py \
  --runs \
    S0=data/output/ablation_matrix/S0 \
    S1=data/output/ablation_matrix/S1 \
    S4=data/output/ablation_matrix/S4 \
    S5=data/output/ablation_matrix/S5 \
    S6=data/output/ablation_matrix/S6 \
    S7=data/output/ablation_matrix/S7 \
    D1=data/output/ablation_matrix/D1 \
  --molmo-root data/output/molmo_output \
  --npz-root data/npz_file \
  --output data/output/outcome_policy_selector_v1/replay_table.csv \
  --report data/output/outcome_policy_selector_v1/replay_manifest.json
```

If any run is incomplete, the script must record it and either exclude it or
stop. Do not silently mix incomplete rows.

### 13.4 Train and audit selector offline

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python train_outcome_policy_selector.py \
  --replay-table data/output/outcome_policy_selector_v1/replay_table.csv \
  --model-output models/outcome_policy_selector_v1.joblib \
  --audit-output data/output/outcome_policy_selector_v1/offline_audit.json
```

Then generate a readable report:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python audit_outcome_policy_selector.py \
  --replay-table data/output/outcome_policy_selector_v1/replay_table.csv \
  --model models/outcome_policy_selector_v1.joblib \
  --output-json data/output/outcome_policy_selector_v1/offline_audit.json \
  --report docs/experiments/2026-06-25-outcome-policy-selector-v1-offline.md
```

The report must explicitly include:

- scene-grouped replay RSR;
- split-holdout replay RSR;
- hard-subset replay RSR;
- uncertainty fallback rate;
- oracle regret;
- gate pass/fail.

### 13.5 Run tests

```bash
.venv/bin/python -m unittest discover -v
```

If tests fail, stop. Do not run paid experiments.

### 13.6 Paid split-0 run only if gates pass

Only if offline gates pass and the user approves paid inference:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy outcome_policy_selector_v1_auto \
  --routing-variant outcome_policy_selector \
  --segmentation-variant point_retry \
  --run-root data/output/ablation_matrix/OPS1 \
  --splits 0 \
  --reuse-molmo \
  --resume
```

Stop after split 0 and compare against S0 split 0. Do not proceed to full 900
unless the user approves.

### 13.7 Paid ablations only after OPS1 beats S0

Suggested ablation run ids:

- `OPS2`: no hard fallback.
- `OPS3`: no depth features.
- `OPS4`: no geometry features.
- `OPS5`: no uncertainty gate.

Command shape:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy outcome_policy_selector_v1_no_hard_fallback \
  --routing-variant outcome_policy_selector \
  --segmentation-variant point_retry \
  --run-root data/output/ablation_matrix/OPS2 \
  --splits 0 \
  --reuse-molmo \
  --resume
```

Do not run OPS2-OPS5 if OPS1 does not beat S0 on split 0.

## 14. Expected Decision

If the offline selector passes gates, it is worth a split-0 paid test.

If it fails gates, the correct conclusion is not "protocol is weak". The
correct conclusion is that offline evidence is insufficient to choose among
strong protocols. In that case, move effort to protocol or segmentation repair
instead of spending more on route selection.

