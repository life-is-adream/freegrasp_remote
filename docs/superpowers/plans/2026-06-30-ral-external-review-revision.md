# RA-L External Review Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the Gemini and Qwen3.7max external pre-review feedback into a focused RA-L revision package that resolves the highest review risks without changing the frozen EGHC3_v3 mainline.

**Architecture:** The revision is split into an experiment lane and a manuscript lane. The experiment lane tests whether EGHC's gain survives the strongest alternative explanation: higher inference budget rather than routing structure. The manuscript lane adds reproducibility details, cost accounting, discussion, related-work positioning, and limitations while keeping the central claim bounded to benchmark RSR/SSR.

**Tech Stack:** FreeGrasp Python evaluation scripts, MiMo-v2.5, reused Molmo cache, JSON run manifests, paired bootstrap statistics, IEEEtran LaTeX, `pdflatex`, `pytest`, shell/JQ inspection commands.

---

## Scope Decisions

### In Scope

- Address both external-review clusters: Gemini-style methodological critique and Qwen3.7max-style RA-L reviewer critique.
- Keep `EGHC3_v3_qwen35_full` as the frozen main result.
- Run only targeted controls that answer reviewer objections:
  - S0 with approximately matched reasoning-call budget on split 0.
  - Single-split EGHC component ablations if P0 does not already resolve the main risk.
- Update manuscript text, tables, and limitations to match the new evidence.
- Preserve all no-ground-truth and no-benchmark-difficulty boundaries.

### Out of Scope

- New Qwen3.7-plus/max mainline experiments.
- Replacing MiMo-v2.5 as the paper's main VLM.
- Full real-robot trials before the current RA-L submission pass.
- Changing the frozen 900-sample EGHC3_v3 main result unless a reproducibility failure is discovered.

## External Review Synthesis

| ID | Source | Concern | Severity | Planned action |
|---|---|---|---|---|
| G1/Q1 | Both | RSR gain is marginal because CI lower bound is 0.00 pp. | Near-blocking | Lead with SSR as the stronger controlled gain; describe RSR as positive but secondary/cautious. |
| G2/Q2 | Both, stronger in Qwen | EGHC uses more calls than S0; gains may reflect inference budget. | Blocking | Add call-budget table and run S0 budget-control split-0. |
| Q3 | Qwen | EGHC is monolithic; no component ablation. | Major | Add single-split component ablations after P0 or in parallel if time allows. |
| G3/Q5 | Both | Mask repair equation lacks lambda values or sensitivity details. | Major | Align method text with actual implementation; either report exact weights or replace equation with implementation-faithful priority rule. |
| G4/Q6 | Both | S0 configuration is underspecified. | Major | Add S0 prompt, retry, routing, segmentation, token, model, and cache configuration details. |
| G5/Q10 | Both | Discussion is too thin for cost, SSR-vs-RSR, limitations, and oracle leakage. | Major | Add a Discussion subsection before Conclusion. |
| G6/Q4 | Qwen plus Gemini limitation remarks | Blocker evidence relies on marked candidates and lexical relation triggers. | Major | Add limitation and future-work text; optionally report blocker-evidence detection counts if scriptable from existing details. |
| G7/Q8 | Qwen | Hierarchical consensus lacks pseudocode. | Moderate | Add one compact algorithm block or numbered procedure. |
| G8/Q9 | Qwen | Per-stratum improvement over S0 is not visible. | Moderate | Add a compact S0-vs-EGHC split or full per-stratum delta table if it fits. |
| G9/Q12 | Both | VLA and manipulation planning related work is incomplete. | Moderate | Add RT-2, OpenVLA, VoxPoser, and optionally Inner Monologue/DIAL-style iterative planning positioning if references are verified. |
| G10 | Gemini | Minor text artifact and table scannability issue. | Minor | Scan/fix isolated words and shorten table labels without losing readability. |
| G11/Q7 | Both | No real-robot validation. | Major but not required for this pass | State benchmark-only boundary; defer real-robot execution as future work. |

## File Map

| File | Responsibility in this revision |
|---|---|
| `docs/superpowers/reports/2026-06-30-ral-external-review-triage.md` | Durable synthesis of Gemini and Qwen3.7max review comments, priorities, and decisions. |
| `scripts/summarize_call_budget.py` | Deterministic report of reasoning/router/repair calls for S0, EGHC, and new controls. |
| `scripts/compare_split0_runs.py` | Split-0 comparison table for S0, S0 budget control, EGHC full, and EGHC ablations. |
| `evaluate_all.py` | Add explicit policy names only if the budget-control or ablation runs cannot be expressed with existing policies. |
| `evaluate_mimo_full_protocol.py` | Preferred launcher for split-0 full-protocol runs because it records manifests and supports `--splits 0`. |
| `test_evaluate_all_summary.py` | Unit tests for any new policy mapping or call-budget metadata behavior. |
| `paper/main.tex` | Abstract claim softening and bibliography entries if needed. |
| `paper/sections/related_work.tex` | VLA/planning positioning. |
| `paper/sections/method.tex` | S0/EGHC reproducibility details, pseudocode, mask repair implementation detail. |
| `paper/sections/experiments.tex` | Call-budget table, P0/P1 result table, per-stratum delta table if compact enough. |
| `paper/sections/conclusion.tex` | Bounded conclusion after revised evidence and limitations. |

## Task 1: Preserve External Review Triage

**Files:**
- Create: `docs/superpowers/reports/2026-06-30-ral-external-review-triage.md`

- [ ] **Step 1: Write the triage report**

Create a Markdown report with these sections:

```markdown
# RA-L External Review Triage

Date: 2026-06-30

## Review Inputs

- Gemini-style review: methodological and presentation critique supplied in chat on 2026-06-30.
- Qwen3.7max review: `/home/wyl/.codex/attachments/1af46daf-463a-4ed1-bd91-5cd55d069316/pasted-text.txt`.

## Blocking Risks

| Risk | Source | Why it matters | Resolution |
|---|---|---|---|
| Call-count confound | Gemini + Qwen | EGHC uses 1889 reasoning calls over 900 samples while S0 uses 900; reviewers may attribute gains to more inference budget. | Run S0 budget-control split-0 and add call-budget table. |
| RSR marginality | Gemini + Qwen | +3.00 pp RSR has 95% CI [0.00, 5.95]. | Lead with SSR; describe RSR as positive but cautious. |
| Mask repair reproducibility | Gemini + Qwen | Equation uses lambda weights without values. | Replace or ground equation in actual implementation and report parameters. |

## Major Risks

| Risk | Resolution |
|---|---|
| Missing component ablation | Run single-split EGHC ablations if P0 does not settle the main alternative explanation. |
| Missing Discussion | Add a 200-300 word Discussion subsection before Conclusion. |
| S0 underspecified | Add exact S0 policy details and manifest facts. |
| Candidate false negatives and lexical blocker evidence | Add limitation and future-work text. |

## Deferred Items

| Item | Reason |
|---|---|
| Full real-robot validation | Larger study outside current RA-L revision pass; acknowledge benchmark-only boundary. |
| Qwen3.7-plus/max mainline | Would change the story and introduce new inference-path verification risk. |

## Execution Order

1. Call-budget accounting and P0 S0 budget-control split-0.
2. Manuscript claim softening and reproducibility fixes that do not depend on new results.
3. Component ablations if P0 leaves the call-budget objection unresolved.
4. Final LaTeX compile and external-review handoff.
```

- [ ] **Step 2: Verify no review issue is dropped**

Run:

```bash
rg -n "Call-count|RSR|Mask repair|component|Discussion|S0|candidate|real-robot|Qwen3.7" docs/superpowers/reports/2026-06-30-ral-external-review-triage.md
```

Expected: every major issue from the two external reviews appears at least once.

- [ ] **Step 3: Commit the triage report**

```bash
git add docs/superpowers/reports/2026-06-30-ral-external-review-triage.md
git commit -m "docs: triage external RAL review feedback"
```

## Task 2: Add Deterministic Call-Budget Accounting

**Files:**
- Create: `scripts/summarize_call_budget.py`
- Test: `python -m py_compile scripts/summarize_call_budget.py`
- Report artifact: `data/output/statistics/ral_call_budget_summary.md`

- [ ] **Step 1: Write the script**

Create `scripts/summarize_call_budget.py` with this behavior:

- Input: one or more run directories containing `full_protocol_summary.json`.
- Output: Markdown and CSV rows with `run`, `n`, `rsr`, `ssr`, `reasoning_calls`, `router_calls`, `repair_calls`, `reasoning_calls_per_sample`, and `total_recorded_calls_per_sample`.
- Definition:
  - `reasoning_calls_per_sample = reasoning_calls / n`.
  - `total_recorded_calls_per_sample = (reasoning_calls + router_calls + repair_calls) / n`.
- Do not infer wall-clock latency from call counts.

- [ ] **Step 2: Run syntax verification**

```bash
python -m py_compile scripts/summarize_call_budget.py
```

Expected: exit code 0.

- [ ] **Step 3: Generate the current S0-vs-EGHC call table**

```bash
python scripts/summarize_call_budget.py \
  --runs \
    data/output/ablation_matrix/S0 \
    data/output/ablation_matrix/EGHC3_v3_qwen35_full \
  --output-prefix data/output/statistics/ral_call_budget_summary
```

Expected current values:

```text
S0: n=900, RSR=57.89, SSR=47.56, reasoning_calls=900, router_calls=0, repair_calls=0, reasoning_calls/sample=1.00
EGHC3_v3_qwen35_full: n=900, RSR=60.89, SSR=55.22, reasoning_calls=1889, router_calls=900, repair_calls=59, reasoning_calls/sample=2.10
```

- [ ] **Step 4: Commit the accounting script**

```bash
git add scripts/summarize_call_budget.py data/output/statistics/ral_call_budget_summary.md data/output/statistics/ral_call_budget_summary.csv
git commit -m "analysis: add RAL call-budget accounting"
```

## Task 3: Run P0 S0 Budget-Control Split-0

**Files:**
- Modify only if needed: `evaluate_all.py`
- Modify only if needed: `test_evaluate_all_summary.py`
- Output run: `data/output/ablation_matrix/S0_budget2_vote_split0`
- Output log: `data/output/ablation_matrix/S0_budget2_vote_split0/run.log`

**Experiment hypothesis:** If EGHC still outperforms a budget-matched S0 control on split 0, then the gain is not explained only by extra reasoning calls.

**Primary metric:** SSR.  
**Secondary metric:** RSR.  
**Success criterion:** EGHC split-0 remains higher than S0 budget-control in SSR, or the manuscript explicitly downgrades the claim if the control closes the gap.

- [ ] **Step 1: Confirm whether a pure S0 two-call policy already exists**

Run:

```bash
rg -n "budget|vote|majority|two_call|repeat|retry" evaluate_all.py evaluate_mimo_full_protocol.py test_evaluate_all_summary.py utils reasoning_eval.py
```

Expected: no existing pure S0 two-call majority-vote policy is currently available. If a matching policy is found, record the exact policy name in the triage report and skip Step 2.

- [ ] **Step 2: Add a minimal S0 budget policy only if Step 1 finds no existing policy**

Add one policy name to `evaluate_all.py`:

```python
"original_protocol_budget2_vote",
```

Map it to:

```python
{
    "prompt_variant": "legacy_old",
    "mimo_retry_mode": "budget2_vote",
    "segmentation_variant": "baseline",
    "routing_variant": "none",
    "feature_source": "none",
    "uses_benchmark_difficulty": False,
    "uses_gt_features": False,
    "protocol_ablation": "budget2_vote",
}
```

If `budget2_vote` is not implemented in the prediction layer, add the smallest explicit implementation that performs two independent S0 reasoning calls, parses both answers with the existing parser, and resolves ties deterministically using the first valid parsed answer. Record both raw outputs in `reasoning.raw_outputs`.

- [ ] **Step 3: Add policy tests**

Add tests to `test_evaluate_all_summary.py`:

```python
def test_original_protocol_budget2_vote_policy_is_no_gt_no_routing(self):
    config = evaluate_all._subset_config(
        "easy_no_ambi",
        prompt_variant="legacy",
        mimo_retry_mode="none",
        segmentation_variant="baseline",
        subset_policy="original_protocol_budget2_vote",
    )
    self.assertEqual(config["prompt_variant"], "legacy_old")
    self.assertEqual(config["mimo_retry_mode"], "budget2_vote")
    self.assertEqual(config["segmentation_variant"], "baseline")
    self.assertEqual(config["routing_variant"], "none")
    self.assertEqual(config["feature_source"], "none")
    self.assertFalse(config["uses_gt_features"])
    self.assertFalse(config["uses_benchmark_difficulty"])
```

Run:

```bash
pytest test_evaluate_all_summary.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run a 6-sample smoke test before paid split-0 execution**

Use the official full-protocol runner so split directories and manifests are produced:

```bash
mkdir -p data/output/ablation_matrix/S0_budget2_vote_smoke
nohup .venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy original_protocol_budget2_vote \
  --segmentation-variant baseline \
  --routing-variant none \
  --feature-source none \
  --splits 0 \
  --reuse-molmo \
  --resume \
  --run-root data/output/ablation_matrix/S0_budget2_vote_smoke \
  --skip-mimo-preflight \
  > data/output/ablation_matrix/S0_budget2_vote_smoke/run.log 2>&1 &
```

Expected: smoke output starts writing `split_0/details_*.json` without router calls. If the smoke cannot be constrained to a few samples with the existing runner, stop it after confirming the first subset starts correctly and inspect the partial details before launching the full split.

- [ ] **Step 5: Run split-0 budget-control experiment**

```bash
mkdir -p data/output/ablation_matrix/S0_budget2_vote_split0
nohup .venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy original_protocol_budget2_vote \
  --segmentation-variant baseline \
  --routing-variant none \
  --feature-source none \
  --splits 0 \
  --reuse-molmo \
  --resume \
  --run-root data/output/ablation_matrix/S0_budget2_vote_split0 \
  --skip-mimo-preflight \
  > data/output/ablation_matrix/S0_budget2_vote_split0/run.log 2>&1 &
```

Expected artifacts:

```text
data/output/ablation_matrix/S0_budget2_vote_split0/run_manifest.json
data/output/ablation_matrix/S0_budget2_vote_split0/full_protocol_summary.json
data/output/ablation_matrix/S0_budget2_vote_split0/split_0/details_easy_no_ambi.json
data/output/ablation_matrix/S0_budget2_vote_split0/split_0/details_easy_yes_ambi.json
data/output/ablation_matrix/S0_budget2_vote_split0/split_0/details_medium_no_ambi.json
data/output/ablation_matrix/S0_budget2_vote_split0/split_0/details_medium_yes_ambi.json
data/output/ablation_matrix/S0_budget2_vote_split0/split_0/details_hard_no_ambi.json
data/output/ablation_matrix/S0_budget2_vote_split0/split_0/details_hard_yes_ambi.json
```

- [ ] **Step 6: Monitor without risking duplicate paid inference**

```bash
tail -f data/output/ablation_matrix/S0_budget2_vote_split0/run.log
```

If SSH disconnects, reconnect and run:

```bash
pgrep -af "evaluate_mimo_full_protocol.py.*S0_budget2_vote_split0"
tail -n 80 data/output/ablation_matrix/S0_budget2_vote_split0/run.log
```

Do not start a second run unless `pgrep` shows no matching process.

- [ ] **Step 7: Commit policy code and tests after the split-0 run is complete**

```bash
git add evaluate_all.py test_evaluate_all_summary.py data/output/ablation_matrix/S0_budget2_vote_split0/full_protocol_summary.json
git commit -m "experiment: add S0 split0 budget-control run"
```

## Task 4: Compare Split-0 Controls

**Files:**
- Create: `scripts/compare_split0_runs.py`
- Output: `data/output/statistics/ral_split0_control_comparison.md`

- [ ] **Step 1: Create comparison script**

The script must read these run directories:

```text
data/output/ablation_matrix/S0
data/output/ablation_matrix/S0_budget2_vote_split0
data/output/ablation_matrix/EGHC3_v3
```

It must output:

- Overall split-0 RSR and SSR for each run.
- Per-stratum split-0 RSR and SSR.
- Delta table:
  - `EGHC3_v3 split0 - S0 split0`
  - `EGHC3_v3 split0 - S0_budget2_vote_split0`

- [ ] **Step 2: Verify script syntax**

```bash
python -m py_compile scripts/compare_split0_runs.py
```

Expected: exit code 0.

- [ ] **Step 3: Generate split-0 comparison**

```bash
python scripts/compare_split0_runs.py \
  --runs \
    S0=data/output/ablation_matrix/S0 \
    S0_budget2=data/output/ablation_matrix/S0_budget2_vote_split0 \
    EGHC=data/output/ablation_matrix/EGHC3_v3 \
  --split 0 \
  --output data/output/statistics/ral_split0_control_comparison.md
```

Expected: Markdown table with no missing strata and exactly 300 samples per complete split-0 run.

- [ ] **Step 4: Interpret P0 result**

Use this decision rule:

| Result pattern | Manuscript consequence |
|---|---|
| EGHC SSR remains clearly above S0_budget2 | State that SSR gain is not explained solely by extra reasoning-call budget on split 0. |
| S0_budget2 closes SSR gap but not RSR | Present EGHC as improving segmentation consistency differently from direct retry; soften routing-structure claim. |
| S0_budget2 matches or exceeds EGHC in SSR and RSR | Remove any claim that EGHC beats budget-matched direct inference; keep EGHC as auditability/failure-taxonomy contribution only. |

- [ ] **Step 5: Commit comparison script and output**

```bash
git add scripts/compare_split0_runs.py data/output/statistics/ral_split0_control_comparison.md
git commit -m "analysis: compare split0 budget-control runs"
```

## Task 5: Run P1 Component Ablations If Needed

**Files:**
- Modify if needed: `evaluate_all.py`
- Modify if needed: `test_evaluate_all_summary.py`
- Outputs:
  - `data/output/ablation_matrix/EGHC3_v3_no_mask_repair_split0`
  - `data/output/ablation_matrix/EGHC3_v3_no_consensus_split0`
  - `data/output/ablation_matrix/EGHC3_v3_no_blocker_first_split0`

**Activation condition:** Run this task if P0 does not convincingly address the call-budget objection, or if the advisor asks for component attribution.

- [ ] **Step 1: Add explicit EGHC ablation policies**

Add policy names:

```python
"eghc_consensus_no_mask_repair_v1",
"eghc_no_consensus_v1",
"eghc_consensus_no_blocker_first_v1",
```

Expected configuration intent:

| Policy | Routing | Guard | Segmentation | Ablation |
|---|---|---|---|---|
| `eghc_consensus_v1` | `evidence_gated_cascade` | `eghc_consensus_v1` | `eghc_mask_repair_v1` | `full` |
| `eghc_consensus_no_mask_repair_v1` | `evidence_gated_cascade` | `eghc_consensus_v1` | `baseline` | `no_mask_repair` |
| `eghc_no_consensus_v1` | `evidence_gated_cascade` | `none` | `eghc_mask_repair_v1` | `no_consensus` |
| `eghc_consensus_no_blocker_first_v1` | `evidence_gated_cascade` | `eghc_consensus_v1` | `eghc_mask_repair_v1` | `no_blocker_first` |

- [ ] **Step 2: Add policy mapping tests**

Add one test per policy in `test_evaluate_all_summary.py`, asserting:

- `uses_gt_features` is `False`.
- `uses_benchmark_difficulty` is `False`.
- `routing_variant` remains `evidence_gated_cascade`.
- Only the intended component differs from full EGHC.

Run:

```bash
pytest test_evaluate_all_summary.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run split-0 ablations**

Run one command per policy:

```bash
for policy in \
  eghc_consensus_no_mask_repair_v1 \
  eghc_no_consensus_v1 \
  eghc_consensus_no_blocker_first_v1
do
  run="data/output/ablation_matrix/${policy}_split0"
  mkdir -p "$run"
  nohup .venv/bin/python evaluate_mimo_full_protocol.py \
    --model-name mimo-v2.5 \
    --max-output-tokens 1024 \
    --subset-policy "$policy" \
    --splits 0 \
    --reuse-molmo \
    --resume \
    --run-root "$run" \
    --skip-mimo-preflight \
    > "$run/run.log" 2>&1 &
done
```

Expected: three split-0 runs complete with `full_protocol_summary.json`.

- [ ] **Step 4: Add ablation table to comparison output**

Extend `scripts/compare_split0_runs.py` so it also accepts:

```text
EGHC_no_mask=data/output/ablation_matrix/eghc_consensus_no_mask_repair_v1_split0
EGHC_no_consensus=data/output/ablation_matrix/eghc_no_consensus_v1_split0
EGHC_no_blocker=data/output/ablation_matrix/eghc_consensus_no_blocker_first_v1_split0
```

Expected output: one compact table with RSR, SSR, reasoning calls/sample, and total recorded calls/sample.

- [ ] **Step 5: Commit ablation policies and outputs**

```bash
git add evaluate_all.py test_evaluate_all_summary.py scripts/compare_split0_runs.py data/output/statistics/ral_split0_control_comparison.md
git commit -m "experiment: add split0 EGHC component ablations"
```

## Task 6: Manuscript Revision Independent Of New Results

**Files:**
- Modify: `paper/main.tex`
- Modify: `paper/sections/related_work.tex`
- Modify: `paper/sections/method.tex`
- Modify: `paper/sections/experiments.tex`
- Modify: `paper/sections/conclusion.tex`

- [ ] **Step 1: Soften abstract and conclusion around RSR**

Required wording intent:

```text
SSR is the stronger controlled empirical gain, while the RSR shift is positive but secondary because its confidence interval lower bound reaches 0.00 percentage points.
```

Apply this idea in:

- `paper/main.tex` abstract.
- `paper/sections/conclusion.tex`.

- [ ] **Step 2: Add S0 configuration details**

Add to `paper/sections/experiments.tex` Implementation paragraph:

```text
S0 uses the original FreeGrasp direct-answer protocol with MiMo-v2.5, the same 1024-token output cap, the same reused Molmo cache, no route guard, no predicted evidence packet, no retry repair, and baseline segmentation.
```

If the actual manifest differs, use the manifest instead of this sentence.

- [ ] **Step 3: Fix mask repair reproducibility**

Inspect the actual `eghc_mask_repair_v1` implementation. Then choose one of two manuscript treatments:

| Implementation reality | Manuscript treatment |
|---|---|
| Explicit numeric weights exist | Report `lambda_p`, `lambda_c`, and `lambda_a`, including normalization of `s(M)` and `A(M)`. |
| No explicit weights exist | Replace Eq. (2) with an implementation-faithful priority rule and remove unreported lambda parameters. |

Do not leave unreported lambda symbols in the final manuscript.

- [ ] **Step 4: Add hierarchical consensus pseudocode**

Add a compact numbered procedure in `paper/sections/method.tex`:

```text
1. Build evidence packet from marked candidates and predicted spatial/mask relations.
2. Propose route from direct, target_first, blocker_first.
3. Reject direct route if blocker evidence conflicts with target graspability.
4. Reject blocker_first route unless physical blocker evidence is present.
5. Fall back to target_first when evidence is inconsistent.
6. Run route-specific planner and validate selected ID.
7. Trigger adjudication or repair only on invalid ID, route conflict, or parser failure.
8. Pass selected ID and query to point-constrained mask repair.
```

- [ ] **Step 5: Add Discussion subsection**

Insert before Conclusion or as the last Experiments subsection:

```text
\subsection{Discussion}
```

Cover four points in 200-300 words:

1. Why SSR improves more than RSR.
2. Why extra calls are an auditability cost and not a real-time control claim.
3. Why EGHC is not only prompt length or model scale.
4. Why single-view marked-candidate reasoning still fails under occlusion and missing candidates.

- [ ] **Step 6: Add VLA and planning related work**

Update `paper/sections/related_work.tex` with a paragraph contrasting EGHC against:

- RT-2.
- OpenVLA.
- VoxPoser, if a verified citation is added.
- Optional iterative planning work only if citation metadata is verified.

Required positioning:

```text
VLA systems learn or generate actions directly, whereas EGHC studies the FreeGraspData target/blocker/mask decision contract and exposes intermediate evidence for audit.
```

- [ ] **Step 7: Add candidate-false-negative and lexical-evidence limitations**

Add to Discussion or Conclusion:

```text
EGHC routes only over marked visible candidates. If the marking stage misses a critical blocker, the downstream evidence packet cannot recover that object. Current blocker evidence is also derived from predicted relation text and geometric cues, so future work should replace lexical triggers with calibrated semantic or learned relation classifiers.
```

- [ ] **Step 8: Fix presentation artifacts**

Run:

```bash
rg -n "^\s*and\s*$|EGHC3_v3SO|TO""DO|TB""D|place""holder|significant" paper
```

Expected:

- No isolated `and`.
- No unreadable compressed labels such as `EGHC3_v3SO`.
- No unbounded use of `significant` unless tied to a metric and interval.

- [ ] **Step 9: Compile**

```bash
cd paper
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Expected: `paper/main.pdf` is regenerated without LaTeX errors. Investigate any overfull table warnings that affect readability.

- [ ] **Step 10: Commit manuscript-only revision**

```bash
git add paper/main.tex paper/sections/related_work.tex paper/sections/method.tex paper/sections/experiments.tex paper/sections/conclusion.tex
git commit -m "paper: address external review reproducibility concerns"
```

## Task 7: Manuscript Revision Dependent On New Results

**Files:**
- Modify: `paper/sections/experiments.tex`
- Modify: `paper/sections/conclusion.tex`
- Modify: `docs/superpowers/reports/2026-06-30-ral-external-review-triage.md`

- [ ] **Step 1: Add call-budget table**

Add a table with at least these columns:

```text
Method | N | RSR | SSR | Reasoning calls/sample | Total recorded calls/sample | Role
```

Rows:

- S0.
- S0 budget-control split-0, if complete.
- EGHC3_v3 full or split-0 as appropriate.

- [ ] **Step 2: Add P0 interpretation**

Use one of the decision-rule outcomes from Task 4. Do not write that EGHC beats a budget-matched baseline unless the split-0 comparison supports it.

- [ ] **Step 3: Add P1 ablation table only if ablations ran**

If Task 5 ran, add a compact table:

```text
Variant | N | RSR | SSR | Interpretation
```

Rows:

- Full EGHC.
- No mask repair.
- No consensus.
- No blocker-first.

- [ ] **Step 4: Re-run bootstrap only if a full 900-row comparison is added**

If only split-0 P0/P1 runs are added, do not present them as full 900-row paired significance. Label them as split-0 controls.

- [ ] **Step 5: Compile and commit**

```bash
cd paper
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
cd ..
git add paper/sections/experiments.tex paper/sections/conclusion.tex docs/superpowers/reports/2026-06-30-ral-external-review-triage.md
git commit -m "paper: add split0 review-risk controls"
```

## Task 8: Final Verification And Handoff

**Files:**
- Modify: `docs/superpowers/reports/2026-06-30-ral-readiness-execution-report.md`
- Output: `paper/main.pdf`

- [ ] **Step 1: Run Python checks**

```bash
python -m py_compile scripts/summarize_call_budget.py scripts/compare_split0_runs.py
pytest test_evaluate_all_summary.py -q
```

Expected: all commands exit 0.

- [ ] **Step 2: Recompute statistics that remain in the paper**

```bash
python scripts/paired_bootstrap_ci.py --iterations 20000 --seed 20260630
```

Expected: existing 900-row EGHC/S0/S1 intervals remain reproducible unless a new full-run comparison has been intentionally added.

- [ ] **Step 3: Compile manuscript**

```bash
cd paper
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Expected: `paper/main.pdf` compiles successfully.

- [ ] **Step 4: Run stale-risk scan**

```bash
rg -n "TB""D|TO""DO|place""holder|significant|same-environment|real-robot success|oracle routing is deployable|Qwen3.7" paper docs/superpowers/reports docs/superpowers/specs
```

Expected:

- No stale unresolved markers.
- No claim that original FreeGrasp GPT-4o is paired.
- No claim that S1 is deployable.
- No Qwen3.7 model-sensitivity result in the paper mainline.

- [ ] **Step 5: Update readiness report**

Add:

```markdown
## External Review v2 Response

- Addressed call-budget concern with [result summary].
- Addressed mask repair reproducibility by [implementation-faithful description].
- Added Discussion, VLA positioning, S0 details, and candidate-false-negative limitations.
- Remaining limitation: benchmark-only evidence; no full real-robot sequence evaluation.
```

- [ ] **Step 6: Commit final readiness update**

```bash
git add docs/superpowers/reports/2026-06-30-ral-readiness-execution-report.md paper/main.pdf
git commit -m "docs: update RAL readiness after external review revision"
```

If `paper/main.pdf` is ignored by `.gitignore`, confirm that the source files compile and do not force-add the PDF unless the submission workflow requires it.

## Execution Recommendation

Execute in this order:

1. Task 1.
2. Task 2.
3. Task 3.
4. Task 4.
5. Task 6 while Task 3 is running if no code conflicts exist.
6. Task 5 only if P0 does not neutralize the call-budget objection or the advisor requests component attribution.
7. Task 7.
8. Task 8.

## Stop Conditions

Stop and ask for a decision if any of these occurs:

- S0 budget-control equals or exceeds EGHC on split-0 SSR and RSR.
- Implementing `budget2_vote` requires changing core parsing behavior shared by EGHC.
- A component ablation requires a new paid full 900-sample run.
- The manuscript exceeds RA-L length after adding Discussion and tables.
- Existing dirty Qwen/debug files conflict with the P0/P1 implementation files.

## Notes For Execution

- Current unrelated dirty files are `evaluate_all.py`, `evaluate_common.py`, `reasoning_eval.py`, `test_reasoning_resume.py`, and `models/langsam/GroundingDINO`. Read diffs before editing any of these files.
- Do not revert unrelated dirty changes.
- `evaluate_all.py --help` may fail without API credentials because imports initialize the OpenAI-compatible client. Use source inspection for argument discovery unless credentials are configured.
- Do not start duplicate paid runs. Always check `pgrep` and the target run directory first.
