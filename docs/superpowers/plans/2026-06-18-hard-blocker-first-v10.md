# Hard Blocker-First V10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in hard blocker-first prompt and subset policy, then measure it on the 100-scene hard protocol.

**Architecture:** Reuse the existing target-first JSON parser and candidate-table pipeline. Register a new hard-only prompt variant in `utils/utils.py`, route it through a new policy in `evaluate_all.py`, and expose both hooks through `evaluate_mimo.py`; keep v9 behavior for easy and medium subsets.

**Tech Stack:** Python unittest, existing FreeGrasp evaluation pipeline, MiMo OpenAI-compatible client, reused Molmo and Hugging Face caches.

---

### Task 1: Add Failing Prompt Tests

**Files:**
- Modify: `test_utils_output_limit.py`
- Test: `test_utils_output_limit.py`

- [ ] Add a test asserting `hard_blocker_first_v10_json` requires blocker-first behavior, forbids direct-target selection, and rejects `near` as standalone evidence.
- [ ] Add a test asserting the v10 input includes geometry candidates and a V10 reminder.
- [ ] Run `python -m unittest test_utils_output_limit -v` and confirm failures are caused by the missing v10 hook.

### Task 2: Implement The Prompt Hook

**Files:**
- Modify: `utils/utils.py`
- Test: `test_utils_output_limit.py`

- [ ] Add `_get_hard_blocker_first_prompt()` with the existing target-first JSON schema.
- [ ] Register `hard_blocker_first_v10_json` in `get_reasoning_system_prompt()`.
- [ ] Route v10 through spatial, semantic, geometry candidate formatting and ID repair.
- [ ] Add `_format_v10_blocker_first_reminder()` and append it only for v10.
- [ ] Run `python -m unittest test_utils_output_limit -v` and confirm green.

### Task 3: Add Failing Policy And CLI Tests

**Files:**
- Modify: `test_evaluate_all_summary.py`
- Modify: `test_evaluate_entrypoints.py`
- Modify: `test_evaluate_mimo.py`

- [ ] Add a policy test asserting easy uses direct-target, medium uses v9, and hard uses v10 plus `id_repair`.
- [ ] Add entrypoint and MiMo parser tests for both v10 hooks.
- [ ] Run the three test modules and confirm failures are caused by missing registrations.

### Task 4: Implement Policy And CLI Hooks

**Files:**
- Modify: `evaluate_all.py`
- Modify: `evaluate_mimo.py`

- [ ] Add `hard_blocker_first_v10_json` and `hard_blocker_first_v10` to CLI choices.
- [ ] Add the policy to `_subset_config()` validation.
- [ ] Route easy and medium like v9, and hard to v10 with `id_repair` and `point_retry`.
- [ ] Run the targeted tests and confirm green.

### Task 5: Regression And Review

**Files:**
- Review: all changed production and test files

- [ ] Run the full relevant 87-test suite.
- [ ] Run `git diff --check`.
- [ ] Review for cache deletion, paid API calls in tests, key leakage, parser drift, metric drift, and non-hard policy regressions.

### Task 6: Hard Evaluation

**Files:**
- Write: `data/output/freegrasp_codex_v10_blocker_first_hard_*`

- [ ] Run 50 `hard_no_ambi` and 50 `hard_yes_ambi` scenes with `mimo-v2.5`, 1024 output tokens, Molmo reuse, and offline Hugging Face model loading.
- [ ] Confirm no API errors and record API call count.
- [ ] Compare RSR and SSR with v9 id-repair and v9 geometry-repair runs.
- [ ] Audit direct-target decisions, retry reasons, and result reproducibility caveats.
