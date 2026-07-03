# RA-L Literature Integration Design

Date: 2026-07-04

## Goal

Use the strong-related papers collected under
`C:\Users\lenovo\Desktop\研究生生涯记录\论文\qoder_paper\daily`
to improve the current FreeGrasp/EGHC RA-L manuscript without diluting the main
claim or overloading the paper with weakly related VLA work.

## Approved approach

Use the "strengthened narrative" approach:

- revise the abstract and introduction so the paper is framed as an auditable
  target/blocker decision contract for cluttered language-guided grasping;
- rebuild related work around literature families rather than a flat citation
  list;
- add or revise references for strong-related papers only;
- update tables or figure captions only when they clarify method positioning or
  claim boundaries;
- keep weak-related papers in audit/backup notes unless they directly support a
  necessary contrast.

## Source material

Primary local source folder:

- `C:\Users\lenovo\Desktop\研究生生涯记录\论文\qoder_paper\daily`

Strong-related papers to prioritize:

- GraspMolmo
- GraspCoT
- GraspVLA
- MapleGrasp
- RealVLG-R1
- VCoT-Grasp
- DexGraspVLA
- GLOVER++
- RT-Grasp
- ThinkGrasp
- GraspClutter6D

Weak-related papers may be used only for boundary notes or future-work context:

- InternVLA-M1
- ORACLE-Grasp
- UAD
- FineVLA
- GraspMAS
- PhyGrasp
- DAM-VLA
- TwinBrainVLA

## Manuscript targets

Primary edit targets:

- `paper/main.tex`
- `paper/sections/introduction.tex`
- `paper/sections/related_work.tex`
- `paper/sections/experiments.tex`
- `paper/sections/conclusion.tex`
- `paper/citation_claim_audit.md`

Potential edit targets:

- `paper/create_figures.py`
- `paper/figures/*.pdf`
- `paper/submission_package_manifest.md`
- `paper/double_blind_package_check.md`

Do not edit experiment outputs or regenerate evaluation results.

## Narrative design

The revised manuscript should position EGHC against four literature clusters.

1. Language-conditioned and task-oriented grasping.
   Use GraspMolmo, GraspCoT, RT-Grasp, ThinkGrasp, and FreeGrasp to show that
   recent systems increasingly rely on language and VLM reasoning, but often
   conflate target identity, obstruction reasoning, and mask quality.

2. Clutter and occlusion benchmarks.
   Use GraspClutter6D and RealVLG-R1 to motivate why cluttered real scenes need
   stronger grounding and explicit failure localization.

3. Mask-guided and segmentation-aware grasping.
   Use MapleGrasp plus the current EGHC no-mask-repair ablation to explain why
   segmentation quality is not a secondary detail. It affects SSR even when the
   first-grasp ID is reasonable.

4. VLA and foundation-model contrast.
   Use GraspVLA, DexGraspVLA, GLOVER++, and selected VLA notes only as contrast:
   EGHC is not an end-to-end action foundation model. It is a deployable
   inference-time routing contract layered over a marked-candidate FreeGrasp
   pipeline.

## Claim boundaries

Preserve these boundaries:

- Main evidence is offline FreeGraspData RSR/SSR, not real-robot success.
- Strongest controlled gain is SSR, not broad reasoning superiority.
- S1 remains oracle diagnostic only.
- Split-0 ablations remain mechanism checks, not full 900-sample claims.
- New literature must not create unsupported claims about unverified papers.

## Citation rules

- Verify external metadata for every new citation before inserting it.
- Prefer arXiv/project/publisher pages over secondary summaries.
- If metadata is uncertain, mark the citation in `paper/citation_claim_audit.md`
  as manual-needed rather than inventing venue, DOI, or pages.
- Keep bibliography clean: every `bibitem` must be cited, and every citation
  must have a `bibitem`.

## Figure/table policy

Do not add large new result figures unless needed for clarity.

Allowed low-risk figure/table changes:

- improve captions to state full-protocol vs split-0 vs oracle vs descriptive;
- add a compact related-work positioning table only if it fits page budget;
- regenerate figure PDFs only after source changes, using non-Type-3 fonts.

## Verification plan

Before committing implementation:

1. compile `paper/main.tex`;
2. verify citation key integrity;
3. verify no uncited bibliography entries;
4. verify PDF has no author metadata;
5. verify figure PDFs have no Type 3 fonts if regenerated;
6. update citation audit with new references and unresolved metadata caveats;
7. confirm `git status --short` is clean after commit.

## Out of scope

- New experiments or API calls.
- Recomputing results.
- Claiming real-robot validation.
- Rewriting the paper as an end-to-end VLA paper.
- Adding weak-related papers just to increase reference count.
