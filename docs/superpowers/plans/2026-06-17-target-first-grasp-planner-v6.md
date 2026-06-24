# Target First Grasp Planner V6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a v6 MiMo/FreeGrasp reasoning policy that explicitly separates target resolution from first-grasp planning for hard occlusion scenes.

**Architecture:** Reuse the existing candidate-grasp JSON parser and `first_grasp_verify` retry path. Add semantic labels to the visible candidate table, then add a stricter v6 prompt variant and subset policy that keep easy scenes direct while using v6 for medium/hard.

**Tech Stack:** Python, unittest, FreeGrasp `evaluate_all.py`, `evaluate_mimo.py`, `utils/utils.py`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `test_utils_output_limit.py`
- Modify: `test_evaluate_all_summary.py`
- Modify: `test_evaluate_mimo.py`

- [ ] Add tests for `candidate_grasp_semantic_json` because existing tests are red in this workspace.
- [ ] Add tests for `target_first_grasp_planner_json` prompt wording, candidate table labels, and first-grasp verifier retry.
- [ ] Add CLI/policy tests for `target_first_grasp_planner_v6`.
- [ ] Run targeted tests and confirm they fail before implementation.

### Task 2: Implement Prompt And Candidate Table

**Files:**
- Modify: `utils/utils.py`

- [ ] Add semantic label support to `_format_visible_object_candidates`.
- [ ] Add `candidate_grasp_semantic_json` support where current tests already expect it.
- [ ] Add `target_first_grasp_planner_json` with required fields: `target_resolution` and `first_grasp_planning`.
- [ ] Include first-grasp hard negative examples focused on “do not pick the target when a direct blocker must move first.”
- [ ] Ensure parser accepts `first_grasp_planning.first_grasp_object_id` without changing old JSON formats.

### Task 3: Expose CLI And Policy

**Files:**
- Modify: `evaluate_all.py`
- Modify: `evaluate_mimo.py`

- [ ] Add `target_first_grasp_planner_json` to `--prompt-variant`.
- [ ] Add `target_first_grasp_planner_v6` to `--subset-policy`.
- [ ] Configure easy subsets as `direct_target + id_repair + point_retry`.
- [ ] Configure medium/hard subsets as `target_first_grasp_planner_json + first_grasp_verify + point_retry`.

### Task 4: Verify

**Files:**
- No new files.

- [ ] Run targeted unittest for prompt/parser/policy behavior.
- [ ] Run the broader local unittest suite that does not trigger paid inference.
- [ ] Run `py_compile` for touched Python files.
- [ ] Provide the exact MiMo hard smoke command with `--reuse-molmo`, fixed run-dir, and `--max-output-tokens 1024`.
