# RA-L Submission Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the EGHC3 RA-L internal-review package by polishing the manuscript, auditing claim integrity, and separating paper deliverables from Qwen debugging changes.

**Architecture:** Treat the work as a paper-readiness pipeline: manuscript polishing first, claim/integrity audit second, Git/package hygiene third, verification last. The invariant is that every manuscript claim must trace to frozen EGHC3_v3 evidence, controlled S0 comparison, paired bootstrap, or S1 oracle headroom.

**Tech Stack:** LaTeX/IEEEtran, local Markdown design and report files, Python bootstrap script, Git staging/commit hygiene.

---

### Task 1: Plan And Scope Lock

**Files:**
- Read: `docs/superpowers/specs/2026-06-30-ral-submission-readiness-design.md`
- Create: `docs/superpowers/plans/2026-06-30-ral-submission-readiness.md`

- [ ] **Step 1: Confirm design scope**

Run:

```bash
sed -n '1,220p' docs/superpowers/specs/2026-06-30-ral-submission-readiness-design.md
```

Expected: the design states that Qwen3.7-plus debugging, paid inference reruns, and model inference code edits are out of scope.

- [ ] **Step 2: Save this implementation plan**

Create `docs/superpowers/plans/2026-06-30-ral-submission-readiness.md` with this plan content.

- [ ] **Step 3: Self-review plan**

Run:

```bash
python - <<'PY'
from pathlib import Path
path = Path("docs/superpowers/plans/2026-06-30-ral-submission-readiness.md")
needles = ["TBD", "PLACEHOLDER", "NEEDS_DECISION", "<fill", "<insert"]
in_code_block = False
for line_no, line in enumerate(path.read_text().splitlines(), 1):
    if line.startswith("```"):
        in_code_block = not in_code_block
        continue
    if in_code_block:
        continue
    if any(needle in line for needle in needles):
        print(f"{line_no}:{line}")
PY
```

Expected: no matches.

- [ ] **Step 4: Commit the plan only**

Run:

```bash
git add docs/superpowers/plans/2026-06-30-ral-submission-readiness.md
git diff --cached --name-only
git commit -m "docs: add RAL submission readiness plan"
```

Expected: only the plan file is staged and committed.

### Task 2: Manuscript Polish Pass

**Files:**
- Modify: `paper/main.tex`
- Modify: `paper/sections/introduction.tex`
- Modify: `paper/sections/method.tex`
- Modify: `paper/sections/experiments.tex`
- Modify: `paper/sections/conclusion.tex`

- [ ] **Step 1: Inspect manuscript sections**

Run:

```bash
sed -n '1,220p' paper/main.tex
sed -n '1,220p' paper/sections/introduction.tex
sed -n '1,220p' paper/sections/method.tex
sed -n '1,260p' paper/sections/experiments.tex
sed -n '1,180p' paper/sections/conclusion.tex
```

Expected: all sections load without missing files.

- [ ] **Step 2: Apply claim-bound polishing**

Edit only claims that need evidence calibration. Keep these constraints:

```text
1. SSR over S0 is the strongest controlled gain.
2. RSR over S0 is positive but cautious because its CI lower bound is 0.00 pp.
3. Original FreeGrasp GPT-4o comparison is descriptive/reported, not paired.
4. S1 is oracle headroom only.
5. Hard-scene blocker/visibility remains unsolved.
6. RSR/SSR are benchmark reasoning and mask metrics, not real-robot execution.
```

- [ ] **Step 3: Remove severe table overflow risks**

Use compact table labels when needed:

```latex
\begin{tabular}{@{}lcccc@{}}
Method & GT & Diff. & RSR & SSR \\
```

Expected: main/oracle/bootstrap tables fit the IEEE column width or only emit non-severe warnings.

- [ ] **Step 4: Compile manuscript**

Run:

```bash
cd paper
/home/wyl/.local/bin/pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Expected: exit code 0 and `paper/main.pdf` is produced.

### Task 3: Integrity And Claim Audit

**Files:**
- Modify: `docs/superpowers/reports/2026-06-30-ral-internal-review-memo.md`
- Modify: `docs/superpowers/reports/2026-06-30-ral-pre-review.md`
- Create: `docs/superpowers/reports/2026-06-30-ral-readiness-execution-report.md`

- [ ] **Step 1: Search for stale or overclaiming language**

Run:

```bash
rg -n "significant|solve|solves|real-robot|paired|unpaired|oracle|ground-truth|difficulty|to compute|still need" paper docs/superpowers/reports docs/superpowers/specs
```

Expected: any risky claim has surrounding text that bounds it correctly.

- [ ] **Step 2: Update review reports**

Ensure the internal memo and pre-review report include:

```text
1. Claim-evidence-status map.
2. Blocking risks first.
3. Explicit original-baseline unpaired warning.
4. Explicit S1 oracle warning.
5. SSR-strong / RSR-cautious statistical interpretation.
6. External review prompt for Gemini/GLM5.2.
```

- [ ] **Step 3: Write execution report**

Create `docs/superpowers/reports/2026-06-30-ral-readiness-execution-report.md` with:

```text
1. What was changed.
2. Which checks were run.
3. Remaining manuscript risks.
4. Which dirty files belong to paper, stats, review docs, specs, and Qwen debugging.
5. Recommended commit grouping.
```

### Task 4: Git And Package Hygiene

**Files:**
- Read: current Git status
- Stage/commit only paper-readiness files

- [ ] **Step 1: Inspect dirty files**

Run:

```bash
git status --short
```

Expected: dirty files are visible and can be grouped.

- [ ] **Step 2: Stage paper-readiness files only**

Run a targeted `git add` command for:

```bash
git add \
  paper/main.tex \
  paper/sections/introduction.tex \
  paper/sections/method.tex \
  paper/sections/experiments.tex \
  paper/sections/conclusion.tex \
  docs/superpowers/specs/2026-06-29-eghc3-ral-paper-revision-design.md \
  docs/superpowers/reports/2026-06-30-ral-internal-review-memo.md \
  docs/superpowers/reports/2026-06-30-ral-pre-review.md \
  docs/superpowers/reports/2026-06-30-ral-readiness-execution-report.md \
  scripts/paired_bootstrap_ci.py
```

Expected: Qwen debugging files such as `evaluate_all.py`, `evaluate_common.py`, `reasoning_eval.py`, and `test_reasoning_resume.py` are not staged by this command.

- [ ] **Step 3: Verify staged scope**

Run:

```bash
git diff --cached --name-only
```

Expected: only paper-readiness files appear.

- [ ] **Step 4: Commit paper-readiness package**

Run:

```bash
git commit -m "docs: finalize RAL internal review package"
```

Expected: commit succeeds without staging Qwen debugging files.

### Task 5: Final Verification

**Files:**
- Verify: `scripts/paired_bootstrap_ci.py`
- Verify: `paper/main.pdf`
- Verify: Git status after paper package commit

- [ ] **Step 1: Verify bootstrap script syntax**

Run:

```bash
python -m py_compile scripts/paired_bootstrap_ci.py
```

Expected: exit code 0.

- [ ] **Step 2: Reproduce bootstrap summary**

Run:

```bash
python scripts/paired_bootstrap_ci.py --iterations 20000 --seed 20260630
```

Expected: deltas match the manuscript table:

```text
EGHC3_v3 - S0 RSR +3.00, CI [+0.00, +5.95]
EGHC3_v3 - S0 SSR +7.67, CI [+4.19, +11.33]
S1 - EGHC3_v3 RSR +6.56, CI [+3.41, +9.80]
S1 - EGHC3_v3 SSR +4.89, CI [+1.86, +7.95]
```

- [ ] **Step 3: Compile LaTeX twice**

Run:

```bash
cd paper
/home/wyl/.local/bin/pdflatex -interaction=nonstopmode -halt-on-error main.tex
/home/wyl/.local/bin/pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Expected: both runs exit code 0 and generate `paper/main.pdf`.

- [ ] **Step 4: Search for stale placeholders**

Run:

```bash
rg -n "TBD|TODO|to compute|still need|need to be added|Do not claim significance until" paper docs/superpowers || true
```

Expected: no stale manuscript-readiness placeholders remain in paper or reports.

- [ ] **Step 5: Report final status**

Run:

```bash
git status --short
git log --oneline -3
```

Expected: paper-readiness changes are committed. Remaining dirty files, if any,
are Qwen/debugging or generated artifacts and are explicitly listed in the final
answer.
