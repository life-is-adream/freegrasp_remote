# Candidate Grasp Semantic V5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `candidate_grasp_semantic_v5`, a FreeGrasp MiMo ablation that augments visible Molmo candidates with short semantic labels while preserving the v4 spatial candidate table.

**Architecture:** Build semantic labels from the local simulation masks: `Molmo_ID -> GT object id -> instances_semantic -> MetaGraspNet short label`. The label is displayed as `label=<short_category>` in the candidate table; raw GT object ids are not exposed to MiMo. The v5 subset policy uses the existing first-grasp JSON + verifier flow for medium and hard subsets.

**Tech Stack:** Python, NumPy `.npz` semantic masks, existing FreeGrasp `evaluate_all.py` / `evaluate_mimo.py` CLI, unittest.

---

### Task 1: Tests For Semantic Candidate Rows

**Files:**
- Modify: `test_utils_output_limit.py`
- Modify: `utils/utils.py`

- [ ] **Step 1: Write failing tests**

Add tests that require:
- `candidate_grasp_semantic_json` prompt mentions semantic labels.
- `_format_visible_object_candidates(..., include_semantic=True, semantic_labels={...})` prints `label=...`.
- The formatted candidate table does not expose `GT_ID` or `gt_id`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
FreeGrasp_code-main/.venv/bin/python -m unittest FreeGrasp_code-main/test_utils_output_limit.py
```

Expected: fail because `candidate_grasp_semantic_json` and semantic formatting do not exist.

- [ ] **Step 3: Implement minimal semantic formatting**

Add:
- MetaGraspNet semantic id to short label mapping.
- Object-id to semantic-label extraction from `data/npz_file/<scene>.npz`.
- `include_semantic` support in `_format_visible_object_candidates`.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same unittest command and expect all tests in the file to pass.

### Task 2: CLI And Subset Policy Hook

**Files:**
- Modify: `evaluate_all.py`
- Modify: `evaluate_mimo.py`
- Modify: `test_evaluate_all_summary.py`
- Modify: `test_evaluate_mimo.py`

- [ ] **Step 1: Write failing tests**

Add tests that require:
- both CLIs accept `candidate_grasp_semantic_json`;
- both CLIs accept `candidate_grasp_semantic_v5`;
- policy maps easy subsets to `direct_target + id_repair`;
- policy maps medium/hard subsets to `candidate_grasp_semantic_json + first_grasp_verify + point_retry`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
FreeGrasp_code-main/.venv/bin/python -m unittest FreeGrasp_code-main/test_evaluate_all_summary.py FreeGrasp_code-main/test_evaluate_mimo.py
```

Expected: fail because v5 options are not wired.

- [ ] **Step 3: Implement minimal policy wiring**

Update CLI choices and `_subset_config` to include v5.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same unittest command and expect all tests in both files to pass.

### Task 3: Fixed Hard Smoke

**Files:**
- No new code files.

- [ ] **Step 1: Check running FreeGrasp processes**

Run:

```bash
pgrep -af 'python evaluate_all.py|python evaluate_mimo.py|python evaluate_resume.py' || true
```

- [ ] **Step 2: Run fixed hard smoke**

Run v5 on the same four hard scenes used by v3/v4 smoke. Reuse `data/output/molmo_output`, use `mimo-v2.5`, and set `--max-output-tokens 1024`.

- [ ] **Step 3: Compare against v4 smoke**

Compare RSR/SSR and failed scene reasoning for scenes `1113`, `6835`, `59`, and `242`.

