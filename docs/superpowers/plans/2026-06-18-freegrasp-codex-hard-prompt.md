# FreeGrasp Codex Hard Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve FreeGrasp hard-scene first-grasp reasoning without editing `/home/public/zb/FreeGrasp_code-main`.

**Architecture:** Work only in `/home/public/zb/FreeGrasp_code-freegrasp_codex` on branch `freegrasp_codex`. Add a compact evidence-gated target-first prompt variant and a hard-scene subset policy that routes medium/hard cases through it. Keep existing variants backward-compatible.

**Tech Stack:** Python 3.13 virtual environment, existing FreeGrasp evaluation scripts, MiMo OpenAI-compatible chat client, reused Molmo cache.

---

### Task 1: Baseline Checks

**Files:**
- Read: `utils/utils.py`
- Read: `evaluate_all.py`
- Test: existing unit tests

- [ ] Run cheap unit tests in `.venv` to identify pre-existing failures.
- [ ] Inspect prompt variant tests and output-token tests.
- [ ] Do not clear `data/output/molmo_output`.

### Task 2: Failing Tests For Evidence-Gated Prompt

**Files:**
- Modify: `test_utils_output_limit.py`
- Modify: `test_evaluate_all_summary.py` or `test_evaluate_entrypoints.py` if policy surface is covered there

- [ ] Add a test that `get_reasoning_system_prompt("target_first_evidence_gate_v9_json")` exists and contains blocker evidence constraints.
- [ ] Add a test that `_build_reasoning_input_text(..., "target_first_evidence_gate_v9_json", geometry_features=...)` includes candidate geometry relations.
- [ ] Add a test that `evaluate_all._subset_config(..., "target_first_evidence_gate_v9")` maps medium/hard subsets to the new prompt and geometry repair.
- [ ] Run the targeted tests and verify RED.

### Task 3: Minimal Implementation

**Files:**
- Modify: `utils/utils.py`
- Modify: `evaluate_all.py`

- [ ] Add the new prompt variant with compact target-first schema.
- [ ] Include explicit rule: spatial words are target localization unless direct blocker evidence exists.
- [ ] Include explicit rule: blocker choices must cite visible relation evidence.
- [ ] Route new prompt through spatial, semantic, geometry candidate formatting.
- [ ] Add subset policy entry for `target_first_evidence_gate_v9`.
- [ ] Run targeted tests and verify GREEN.

### Task 4: Hard Evaluation

**Files:**
- Write outputs only under `data/output/freegrasp_codex_*` in isolated copy.

- [ ] Run hard smoke first if script support exists.
- [ ] Run hard_no_ambi and hard_yes_ambi with `.venv`, MiMo model, `--reuse-molmo`, and no cache clearing.
- [ ] Compare RSR/SSR against `mimo-v2.5_best_known_v1` and `target_first_grasp_planner_v6` summaries.
- [ ] Report command, output path, RSR, SSR, and failure caveats.
