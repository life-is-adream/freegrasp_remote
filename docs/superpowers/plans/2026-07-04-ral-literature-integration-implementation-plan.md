# RA-L Literature Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the approved strong-related literature into the EGHC RA-L manuscript while preserving offline-result claim boundaries and submission-package hygiene.

**Architecture:** Build a source-backed literature matrix first, verify metadata for each new citation, then revise manuscript sections in one bounded pass. Keep experiment artifacts immutable and validate the final paper with compile, citation, metadata, and figure-font checks.

**Tech Stack:** Remote Linux repository, LaTeX/IEEEtran manuscript, local `.docx` literature notes, Python `python-docx` for extraction, web/arXiv/CrossRef-style metadata checks, `latexmk`, `pdfinfo`, `pdffonts`, `git`.

---

## File Structure

- Create: `paper/literature_integration_matrix.md`
  - Responsibility: source-backed matrix linking each strong-related paper to manuscript role, citation key, evidence, and claim boundary.
- Modify: `paper/main.tex`
  - Responsibility: add verified `\bibitem` entries for cited strong-related papers only and keep citation set clean.
- Modify: `paper/sections/introduction.tex`
  - Responsibility: sharpen the motivation around cluttered language-guided grasping, target/blocker decisions, and failure localization.
- Modify: `paper/sections/related_work.tex`
  - Responsibility: rebuild related work into literature clusters: task-oriented reasoning grasping, clutter/occlusion benchmarks, mask/segmentation-aware grasping, and VLA/foundation-model contrast.
- Modify: `paper/sections/experiments.tex`
  - Responsibility: adjust captions or bridge sentences only when needed to clarify full-protocol, split-0, oracle, or descriptive evidence.
- Modify: `paper/sections/conclusion.tex`
  - Responsibility: align future-work language with literature-backed limitations without adding real-robot claims.
- Modify: `paper/citation_claim_audit.md`
  - Responsibility: record new reference metadata checks, claim-to-reference support, and any unresolved metadata caveats.
- Modify if figures are regenerated: `paper/create_figures.py`, `paper/figures/*.pdf`
  - Responsibility: preserve non-Type-3 font output and existing result values.
- Modify if package status changes: `paper/double_blind_package_check.md`, `paper/submission_package_manifest.md`
  - Responsibility: reflect final citation, PDF metadata, and figure-font status.

---

### Task 1: Extract and classify strong-related literature notes

**Files:**
- Create: `paper/literature_integration_matrix.md`
- Read: `C:\Users\lenovo\Desktop\研究生生涯记录\论文\qoder_paper\daily\*.docx`

- [ ] **Step 1: Extract `.docx` contents into a temporary local summary**

Run locally from `E:\freegrasp_project`:

```powershell
$py='C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
@'
from pathlib import Path
from docx import Document
base = Path(r"C:\Users\lenovo\Desktop\研究生生涯记录\论文\qoder_paper\daily")
strong_names = ["强相关"]
for path in sorted(base.glob("*.docx")):
    doc = Document(str(path))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " / ") for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts)
    if any(mark in path.name or mark in text[:500] for mark in strong_names):
        print(f"--- {path.name} ---")
        print(text[:2500])
        print()
'@ | & $py -
```

Expected: prints only strong-related note summaries, including GraspMolmo, GraspCoT, GraspVLA, MapleGrasp, RealVLG-R1, VCoT-Grasp, DexGraspVLA, GLOVER++, RT-Grasp, ThinkGrasp, and GraspClutter6D if their note files contain `强相关`.

- [ ] **Step 2: Create `paper/literature_integration_matrix.md`**

Write a matrix with these columns:

```markdown
| Paper | Citation key | Manuscript role | Evidence from daily note | External metadata status | Claim boundary |
|---|---|---|---|---|---|
```

Include only strong-related papers in the main matrix. Put weak-related papers in a final section titled `Excluded or backup-only notes` with one-line rationale.

- [ ] **Step 3: Transfer matrix to remote repo**

Run:

```powershell
scp -i $env:USERPROFILE\.ssh\id_ed25519_freegrasp -o BatchMode=yes -o StrictHostKeyChecking=accept-new E:\freegrasp_project\literature_integration_matrix.md wyl@10.99.16.20:/home/public/zb/FreeGrasp_code-freegrasp_codex/paper/literature_integration_matrix.md
```

Expected: file exists remotely and contains no empty rows.

---

### Task 2: Verify metadata for candidate references

**Files:**
- Modify: `paper/literature_integration_matrix.md`
- Modify: `paper/citation_claim_audit.md`

- [ ] **Step 1: Search authoritative metadata for each candidate**

Use arXiv, project pages, publisher pages, or CrossRef-style metadata. For each strong-related paper, record:

```text
title
authors
year
venue or arXiv status
arXiv/DOI/project URL when available
verification status: verified | manual-needed | excluded
```

Do not cite a paper in `main.tex` unless at least title and arXiv/publisher URL are verified.

- [ ] **Step 2: Decide citation set**

Use these default citation keys if verified:

```text
graspmolmo
graspcot
graspvla
maplegrasp
realvlgr1
vcotgrasp
dexgraspvla
gloverpp
rtgrasp
thinkgrasp
graspclutter6d
```

Keep already cited `thinkgrasp` unchanged if metadata matches.

- [ ] **Step 3: Update `paper/citation_claim_audit.md`**

Add a section titled `Literature integration metadata checks` with:

```markdown
| Key | Status | Source checked | Manuscript claim supported | Remaining caveat |
|---|---|---|---|---|
```

Every new citation key must appear in this table.

---

### Task 3: Revise abstract and introduction

**Files:**
- Modify: `paper/main.tex`
- Modify: `paper/sections/introduction.tex`

- [ ] **Step 1: Revise abstract**

Replace the current abstract with a tighter version that follows:

```text
context/problem -> gap/objective -> approach -> key results -> implication
```

Required content:

- target/blocker decision in cluttered free-form language grasping;
- existing systems often conflate target identity, obstruction reasoning, and mask quality;
- EGHC as inference-time evidence-gated routing, not an end-to-end VLA;
- 900-sample EGHC3_v3 result: 60.89% RSR and 55.22% SSR;
- controlled S0 delta: +7.67 pp SSR and +3.00 pp RSR with cautious RSR wording;
- hard-scene blocker/visibility bottleneck.

- [ ] **Step 2: Revise introduction structure**

Use four paragraphs:

1. problem: language-guided grasping in clutter needs target identity, obstruction reasoning, and first-grasp choice;
2. literature gap: task-oriented/VLM grasping advances exist, but their evaluation often hides which subdecision failed;
3. EGHC contribution: evidence packet, route selection, route-specific first-grasp planning, mask repair;
4. result and boundary: no-GT EGHC3_v3, controlled SSR gain strongest, RSR cautious, S1 oracle separated.

- [ ] **Step 3: Update contribution bullets**

Keep four bullets. Ensure each bullet maps to one manuscript artifact:

1. auditable target/blocker decision contract;
2. deployable predicted-evidence EGHC3_v3;
3. 900-sample controlled evaluation plus uncertainty;
4. failure analysis and mask/blocker limitation.

---

### Task 4: Rebuild related work around literature clusters

**Files:**
- Modify: `paper/sections/related_work.tex`
- Modify: `paper/main.tex`
- Modify: `paper/citation_claim_audit.md`

- [ ] **Step 1: Replace flat related-work text with four subsections**

Use these subsection headings:

```latex
\subsection{Language-Conditioned and Task-Oriented Grasping}
\subsection{Reasoning Protocols and Visual Grounding}
\subsection{Clutter, Occlusion, and Segmentation Bottlenecks}
\subsection{Vision-Language-Action Models and Modular Alternatives}
```

- [ ] **Step 2: Insert cluster-specific comparisons**

Required comparisons:

- GraspMolmo and GraspCoT: training/fine-tuning and task/physical reasoning contrast with EGHC's inference-time routing.
- RT-Grasp and ThinkGrasp: reasoning and obstacle-removal lineage; EGHC differs by auditing first-grasp ID and mask success separately.
- MapleGrasp: mask-guided language grasping; connect to EGHC no-mask-repair ablation and SSR.
- GraspClutter6D and RealVLG-R1: clutter/grounding benchmarks motivate failure localization.
- GraspVLA, DexGraspVLA, GLOVER++: end-to-end or foundation-model contrast; EGHC remains modular and deployable over marked candidates.

- [ ] **Step 3: Add `\bibitem` entries**

For every new citation inserted in `related_work.tex`, add exactly one `\bibitem` in `paper/main.tex`.

Use conservative entries when only arXiv metadata is verified:

```latex
\bibitem{key} A. Author et al., ``Exact verified title,'' arXiv:XXXX.XXXXX, YEAR.
```

Use venue entries only when verified:

```latex
\bibitem{key} A. Author et al., ``Exact verified title,'' in \emph{VENUE}, YEAR.
```

Do not add bibliography entries for weak-related papers unless cited.

---

### Task 5: Align experiments and conclusion with new positioning

**Files:**
- Modify: `paper/sections/experiments.tex`
- Modify: `paper/sections/conclusion.tex`

- [ ] **Step 1: Check experiment captions for claim boundaries**

Ensure captions distinguish:

- full 900-sample rows;
- split-0 ablations;
- descriptive prior-paper baseline;
- oracle diagnostic S1.

If a caption already does this, leave it unchanged.

- [ ] **Step 2: Add one bridge sentence to failure analysis if needed**

Only add a sentence if it improves connection to the new literature:

```latex
This pattern is consistent with recent cluttered-scene benchmarks that identify segmentation and occlusion reasoning as coupled bottlenecks, but EGHC localizes the failure to the first-grasp decision, mask quality, or blocker choice.
```

Add citation keys only if verified in Task 2.

- [ ] **Step 3: Refine conclusion future work**

Keep offline evidence boundary. Mention:

- predicted blocker-relation evidence;
- robust segmentation under clutter;
- real-image or real-robot validation as future work, not completed evidence.

---

### Task 6: Compile and package-check

**Files:**
- Modify if needed: `paper/double_blind_package_check.md`
- Modify if needed: `paper/submission_package_manifest.md`

- [ ] **Step 1: Compile manuscript**

Run remotely:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_freegrasp -o BatchMode=yes -o StrictHostKeyChecking=accept-new wyl@10.99.16.20 "cd /home/public/zb/FreeGrasp_code-freegrasp_codex/paper && latexmk -pdf -interaction=nonstopmode main.tex"
```

Expected: `Output written on main.pdf`, 6 or 7 pages acceptable, no fatal LaTeX error.

- [ ] **Step 2: Verify citations**

Run:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_freegrasp -o BatchMode=yes -o StrictHostKeyChecking=accept-new wyl@10.99.16.20 "cd /home/public/zb/FreeGrasp_code-freegrasp_codex && python3 - <<'PY'
from pathlib import Path
import re
tex='\n'.join(Path(p).read_text(encoding='utf-8') for p in ['paper/main.tex'] + [str(x) for x in sorted(Path('paper/sections').glob('*.tex'))])
cites=sorted(set(k.strip() for m in re.finditer(r'\\cite\{([^}]*)\}', tex) for k in m.group(1).split(',')))
bibs=sorted(re.findall(r'\\bibitem\{([^}]*)\}', Path('paper/main.tex').read_text(encoding='utf-8')))
missing=sorted(set(cites)-set(bibs))
uncited=sorted(set(bibs)-set(cites))
print('cites', len(cites), 'bibs', len(bibs), 'missing', missing, 'uncited', uncited)
assert not missing
assert not uncited
PY"
```

Expected: `missing [] uncited []`.

- [ ] **Step 3: Verify PDF and figure metadata**

Run:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_freegrasp -o BatchMode=yes -o StrictHostKeyChecking=accept-new wyl@10.99.16.20 "cd /home/public/zb/FreeGrasp_code-freegrasp_codex && pdfinfo paper/main.pdf | sed -n '1,20p' && python3 - <<'PY'
from pathlib import Path
import subprocess
info=subprocess.run(['pdfinfo','paper/main.pdf'], text=True, capture_output=True, check=True).stdout
assert 'Author:' not in info
for fig in sorted(Path('paper/figures').glob('*.pdf')):
    out=subprocess.run(['pdffonts', str(fig)], text=True, capture_output=True, check=True).stdout
    assert 'Type 3' not in out, fig
print('metadata_ok')
PY"
```

Expected: `metadata_ok`.

- [ ] **Step 4: Update package audit files**

If page count, reference count, or package caveats changed, update:

- `paper/double_blind_package_check.md`
- `paper/submission_package_manifest.md`

Record exact verification date and remaining caveats.

---

### Task 7: Final commit

**Files:**
- All modified manuscript, audit, matrix, and generated PDF files.

- [ ] **Step 1: Check diff**

Run:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_freegrasp -o BatchMode=yes -o StrictHostKeyChecking=accept-new wyl@10.99.16.20 "cd /home/public/zb/FreeGrasp_code-freegrasp_codex && git status --short && git diff --stat"
```

Expected: only `paper/` manuscript/audit/matrix files changed. No `data/output/` changes.

- [ ] **Step 2: Commit**

Run:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_freegrasp -o BatchMode=yes -o StrictHostKeyChecking=accept-new wyl@10.99.16.20 "cd /home/public/zb/FreeGrasp_code-freegrasp_codex && git add paper docs/superpowers/plans/2026-07-04-ral-literature-integration-implementation-plan.md && git commit -m 'docs: integrate grasping literature into ral draft' && git status --short"
```

Expected: commit succeeds and `git status --short` prints nothing.

---

## Self-Review

- Spec coverage: all approved source, narrative, citation, figure/table, and verification requirements are covered by Tasks 1-7.
- Placeholder scan: no placeholder work items remain; every task names exact files and verification commands.
- Scope check: plan modifies manuscript and audit materials only; no experiment outputs or evaluation commands are touched.
- Boundary check: plan preserves offline evidence, cautious RSR wording, S1 oracle separation, and split-0 ablation limits.
