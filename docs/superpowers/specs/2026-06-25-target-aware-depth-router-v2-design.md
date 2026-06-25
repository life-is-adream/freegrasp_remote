# Target-Aware Depth Router V2 Design

Date: 2026-06-25

Branch: `freegrasp_codex`

## 1. Context

The current depth-classifier work introduced a RandomForest router that uses
NPZ depth maps and Molmo point coordinates to predict scene difficulty
(`Easy`, `Medium`, `Hard`) and map the prediction to a FreeGrasp first-grasp
protocol:

- `Easy` -> `direct`
- `Medium` -> `target_first`
- `Hard` -> `blocker_first`

The offline row-level 5-fold result reported for
`data/depth_difficulty_features.csv` is 95.10%. That number is reproducible, but
it is not a reliable estimate of the deployed D1 router for two reasons:

1. The 5-fold split is row-random and allows samples from the same scene to
   appear in both training and validation. A scene-grouped validation drops the
   measured accuracy sharply, so the 95.10% number is a leaky diagnostic rather
   than a publishable routing metric.
2. The training extractor uses the query object id:
   `target_id = query_obj_id + 1`. The deployed extractor in
   `utils/scene_router.py` currently defaults to `target_id = 1` because
   `query_obj_id` is not passed through the evaluation path. Most samples do
   not query object 1, so the deployed D1 router often extracts features around
   the wrong target.

This means D2-D4 should not be run yet. Their results would mostly measure a
known routing-interface bug rather than the value of the protocol ablations.

## 2. Goal

Build a target-aware, leakage-audited depth router that can be trusted before
running paid MiMo ablations.

The router should:

- Use the actual query target when extracting depth features.
- Preserve zero extra inference cost: no additional VLM router call and no SAM
  inference for routing.
- Report realistic route agreement under scene-safe evaluation.
- Keep the original FreeGrasp code path available for comparison.
- Produce enough provenance to debug per-sample route decisions.

## 3. Non-goals

This design does not change the prompt content, segmentation policy, MiMo model,
or success-rate definitions. It also does not claim that difficulty routing
alone can solve hard-scene RSR. The immediate goal is to make the router
correct and measurable.

## 4. Options Considered

### Option A: Run D2-D4 immediately

This is the fastest path, but it is not scientifically useful. The current D1
router is not using the same target definition as the training script, and the
reported 95.10% agreement is not a deployment-valid metric. Running D2-D4 now
risks spending paid inference on a confounded experiment.

### Option B: Patch only `query_obj_id` propagation

This fixes the most obvious bug and is low risk, but it is not enough by itself.
Without a no-leak audit and route-distribution report, the team could still
overstate the router's real agreement rate or miss fallback behavior.

### Option C: Target-aware router plus no-leak audit gates

This is the recommended path. It fixes the deployed feature extraction, adds
route provenance, and makes D1/D2-D4 conditional on offline audit gates. It is
slightly more work than Option B but protects both cost and paper validity.

## 5. Recommended Design

Implement `depth_classifier_v2` as a target-aware router. The existing
`depth_classifier` can remain as a legacy alias during transition, but new
experiments should use the v2 path.

### Data flow

1. `reasoning_eval.process_dataset()` reads each dataset row.
2. It already computes `obj_id = int(row["queryObjId"]) + 1` for evaluation.
3. Pass this 1-indexed query target id into `get_prediction_result()`.
4. `get_prediction_result()` passes it into `route_scene_depth_classifier()`.
5. `route_scene_depth_classifier()` passes it into
   `extract_depth_route_features()`.
6. Feature extraction samples the depth map around the correct Molmo target
   point and computes target-relative depth and spatial features.
7. The selected route controls the existing protocol dispatch:
   `direct`, `target_first`, or `blocker_first`.

### Interface changes

Add an optional parameter named `query_target_id` or `target_object_id` to the
routing path. It should be 1-indexed because Molmo object ids and FreeGrasp
ground-truth ids are handled as 1-indexed values in the reasoning/evaluation
path.

Affected call chain:

- `reasoning_eval.process_dataset(...)`
- `utils.utils.get_prediction_result(...)`
- `utils.scene_router.route_scene_depth_classifier(...)`
- `utils.scene_router.extract_depth_route_features(...)`

If `query_target_id` is missing or not present in Molmo parsed data, the router
must not silently pretend object 1 is the target. It should record an explicit
fallback reason and either:

- use the geometric router fallback; or
- use the nearest available Molmo id only when a dedicated fallback flag is set.

The default safe behavior should be geometric fallback with provenance.

### Provenance

Each depth-router decision should write a compact provenance object into
`reasoning["scene_complexity_features"]`:

- `model`: `depth_rf_v2`
- `route_mode`
- `query_target_id`
- `feature_target_valid`
- `fallback_reason`
- `num_objects`
- `n_depth_valid`
- `target_vs_scene_depth`
- `n_objects_in_front`
- `depth_rank_ratio`
- `n_close_in_front`

This is enough to debug the router without bloating every detail row with the
full feature vector.

## 6. Offline Audit Design

Add or update a cheap audit script that never calls MiMo. The audit should
answer: "If the deployed v2 router had been used, how often would it choose the
same protocol as the oracle difficulty label?"

Required metrics:

- Row-level route agreement on all available depth-feature rows.
- Scene-grouped cross-validation agreement.
- Official split holdout agreement.
- Per-difficulty confusion matrix.
- Route distribution by subset.
- Feature coverage: rows with valid target depth / total rows.
- Fallback rate and fallback reasons.

The report should clearly separate:

- `row_random_cv`: useful diagnostic only, not the headline metric.
- `scene_grouped_cv`: primary no-leak validation metric.
- `split_holdout`: secondary validation metric aligned with the benchmark
  splits.
- `deployed_replay_agreement`: agreement using the exact runtime feature path.

## 7. Experiment Gates

Do not run paid D1/D2-D4 until the offline gates pass.

Minimum gates:

- `feature_target_valid >= 95%` on the intended evaluation split.
- `deployed_replay_agreement >= 75%` on split 0.
- `scene_grouped_cv >= 70%`, or a documented reason if the scene grouping is
  too pessimistic for the benchmark's repeated-scene structure.
- No unexplained route collapse: each of `direct`, `target_first`, and
  `blocker_first` should appear in the expected difficulty bands.
- Fallback rate below 5%, unless the missing rows are explicitly excluded from
  D1/D2-D4 reporting.

If these gates fail, improve the feature extractor or training protocol before
running MiMo.

## 8. Paid Experiment Plan After Gates Pass

Once the offline gates pass:

1. Re-run D1 on split 0 with `depth_classifier_v2`.
2. Compare D1-v2 against the existing D1 and S0/S1 references:
   - S0 original protocol: full-protocol baseline.
   - S1 oracle-feature v10: diagnostic upper bound, not an automatic method.
3. Run D2-D4 only if D1-v2 improves or at least restores expected RSR relative
   to S0 on the same split/cache.
4. If D1-v2 remains below S0, stop routing experiments and move to protocol or
   segmentation improvements.

Expected command shape after implementation:

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy depth_classifier_v2_auto \
  --routing-variant depth_classifier_v2 \
  --segmentation-variant point_retry \
  --splits 0 \
  --reuse-molmo \
  --resume
```

## 9. Tests

Add unit tests before running paid experiments.

Required tests:

- `extract_depth_route_features()` uses the supplied query target id.
- Missing query target does not silently default to object 1.
- `get_prediction_result()` passes the query target id into the router.
- `process_dataset()` passes the 1-indexed query object id into
  `get_prediction_result()`.
- `depth_classifier_v2` appears in CLI choices and subset-policy mappings.
- Audit script reports row-random CV separately from scene-grouped CV.

Cheap verification commands:

```bash
.venv/bin/python -m unittest test_scene_router.py test_utils_output_limit.py
.venv/bin/python -m unittest discover -v
```

The offline audit should be run with the same Python path used by the existing
RandomForest environment:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python audit_depth_classifier_v2.py
```

## 10. Risks

The main risk is that scene-grouped validation remains low even after fixing
the target id. If that happens, the router is not a dependable replacement for
the benchmark difficulty label, and the team should not present it as a 90%+
oracle matcher.

Another risk is that difficulty classification is not the right objective.
The protocol choice that maximizes RSR may differ from the dataset difficulty
label. If D1-v2 has good difficulty agreement but poor RSR, the next design
should train a policy selector against observed best protocol outcomes rather
than `Easy/Medium/Hard`.

## 11. Acceptance Criteria

The design is successful if:

- The deployed depth router uses the real query target.
- Offline audit no longer relies on leaky row-random CV as the headline metric.
- D1-v2 is evaluated only after no-leak gates pass.
- D2-D4 are run only after D1-v2 gives a valid routing baseline.
- Reports clearly state that S1 is an oracle-feature diagnostic upper bound,
  not proof that the protocol is capped at 67.44% RSR.

