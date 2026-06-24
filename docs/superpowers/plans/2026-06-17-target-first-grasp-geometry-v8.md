# Target First-Grasp Geometry V8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a v8 FreeGrasp ablation that augments hard-scene candidate reasoning with mask-derived geometry and pairwise spatial relations before deciding the first grasp object.

**Architecture:** Extend the existing v7 prompt/policy path in `utils/utils.py`, `evaluate_all.py`, and `evaluate_mimo.py`. Reuse Molmo IDs and the existing simulation `.npz` masks to add candidate geometry rows and a geometry consistency repair retry, without changing Molmo generation, LangSAM, or the model name.

**Tech Stack:** Python, NumPy masks, existing FreeGrasp MiMo evaluation CLI, unittest.

---

### Task 1: Geometry Candidate Formatting

**Files:**
- Modify: `test_utils_output_limit.py`
- Modify: `utils/utils.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring `target_first_grasp_geometry_v8_json` to include geometry wording, candidate rows to include `bbox=`, `area_rank=`, `bottom_edge_rank=`, and relation rows like `relation id=4->5`.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_utils_output_limit.UtilsOutputLimitTest.test_target_first_grasp_geometry_v8_prompt_requires_geometry_checks \
  test_utils_output_limit.UtilsOutputLimitTest.test_target_first_grasp_geometry_v8_input_adds_bbox_and_relations
```

Expected: fail because v8 prompt/input support does not exist.

- [ ] **Step 3: Implement minimal geometry formatting**

Add mask bbox/area helpers, candidate geometry table support, and pairwise relation text for v8.

- [ ] **Step 4: Run test to verify GREEN**

Run the same command and expect both tests to pass.

### Task 2: Geometry Repair Retry

**Files:**
- Modify: `test_utils_output_limit.py`
- Modify: `utils/utils.py`

- [ ] **Step 1: Write failing test**

Add a test requiring `mimo_retry_mode="geometry_consistency_repair"` to make a second MiMo call using a repair prompt that mentions bottom-edge rank, same-category instance confusion, and under/covered blocker checks.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_utils_output_limit.UtilsOutputLimitTest.test_get_prediction_result_v8_uses_geometry_consistency_repair
```

Expected: fail because the retry mode does not exist.

- [ ] **Step 3: Implement minimal retry path**

Add `geometry_consistency_repair` to valid retry modes and route v8 through a new repair text builder.

- [ ] **Step 4: Run test to verify GREEN**

Run the same command and expect it to pass.

### Task 3: CLI And Policy Wiring

**Files:**
- Modify: `test_evaluate_mimo.py`
- Modify: `test_evaluate_all_summary.py`
- Modify: `test_evaluate_entrypoints.py`
- Modify: `evaluate_all.py`
- Modify: `evaluate_mimo.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring both CLIs to accept `target_first_grasp_geometry_v8_json`, `geometry_consistency_repair`, and `target_first_grasp_geometry_v8`; policy maps easy subsets to `direct_target + id_repair + point_retry`, and medium/hard to v8 + geometry repair + point retry.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_evaluate_mimo.EvaluateMimoClientTest.test_parse_args_accepts_target_first_grasp_geometry_v8_hooks \
  test_evaluate_all_summary.EvaluateAllSummaryTest.test_target_first_grasp_geometry_policy_uses_v8_for_medium_and_hard \
  test_evaluate_entrypoints.EvaluateEntrypointsTest.test_evaluate_all_exposes_controlled_ablation_arguments
```

Expected: fail because CLI/policy strings are not wired.

- [ ] **Step 3: Implement minimal CLI/policy wiring**

Update parser choices and `_subset_config` in both evaluation entrypoints.

- [ ] **Step 4: Run test to verify GREEN**

Run the same command and expect all selected tests to pass.

### Task 4: Verification And Fixed Hard Smoke

**Files:**
- No production code beyond Tasks 1-3.

- [ ] **Step 1: Run broad local tests**

Run:

```bash
.venv/bin/python -m unittest \
  test_utils_output_limit.py \
  test_evaluate_all_summary.py \
  test_evaluate_mimo.py \
  test_evaluate_entrypoints.py \
  test_evaluate_mimo_full_protocol.py \
  test_reasoning_resume.py \
  test_rsr_metrics.py \
  test_langsam_import_paths.py
```

Expected: all tests pass.

- [ ] **Step 2: Run v8 fixed hard smoke**

Run the same four samples as v6/v7 fixed smoke: `(1113,1)`, `(6835,7)`, `(59,1)`, `(242,5)`, with `mimo-v2.5`, fixed Molmo cache, and `max_output_tokens=1024`.

- [ ] **Step 3: Interpret gate**

Continue to full run only if v8 smoke reaches at least `3/4 RSR` and `3/4 SSR` while keeping both hard_no samples correct.
