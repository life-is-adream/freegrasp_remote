# Double-Blind and Submission Package Check

Date: 2026-07-04
Status: T12 first formal local check. This is a file/source/PDF metadata audit, not a final PaperCept-ready package approval.

## Commands and local evidence checked

- pdfinfo paper/main.pdf
- grep -RInE 'author|affiliation|acknowledg|funding|email|@|/home/|FreeGrasp_code|github|anonymous|Under Review|previous' paper/main.tex paper/sections paper/*.md
- pdfinfo and pdffonts over paper/figures/*.pdf
- Local source package inventory under paper/

## Double-blind findings

| Status | Item | Evidence | Action |
|---|---|---|---|
| Done | Main manuscript visible author block is anonymous. | paper/main.tex:19-21 shows Anonymous Authors and Under Review. | Keep for review version. |
| Done | paper/main.pdf metadata does not expose an author field in pdfinfo. | pdfinfo paper/main.pdf reports Creator TeX, Producer pdfTeX-1.40.29, no Author field. | Recheck after final rebuild. |
| Done | Self-reference wording was neutralized in the manuscript source. | paper/sections/introduction.tex now uses earlier annotation-assisted v10/S1 diagnostic variants; paper/sections/method.tex now uses earlier v10/S1 diagnostic experiments. | Recheck after any future manuscript rewrite. |
| Needs work | Provenance notes include absolute server path. | paper/main_experiment_provenance_run_log.md includes /home/public/zb/FreeGrasp_code-freegrasp_codex. | Keep for internal provenance; do not include raw internal provenance note in anonymous submission package without sanitizing. |
| Done | Figure PDFs no longer use Type 3 fonts after regeneration. | pdffonts over paper/figures/*.pdf reports type3=False for ablation, eghc_architecture, main_results, route_distribution, and system_overview. | Recheck after any future figure regeneration. |
| Needs work | Figure metadata includes Matplotlib creator/producer and creation dates. | pdfinfo paper/figures/*.pdf. | Usually acceptable, but recheck after final figure regeneration and anonymization. |
| Done | Manual bibliography has no uncited entries in the current draft. | cite/bibitem scan after cleanup. | Recheck if references change. |
| Blocked | Real-world/UR5/video supplement readiness. | No current validation artifact or video/readme found in paper/. | Decide whether final submission includes a video; do not promise real-robot validation unless completed. |

## Package-readiness verdict

- Anonymous PDF: Mostly ready for the current draft. Visible author block, PDF metadata, self-reference wording, and figure fonts passed the current local checks; recheck after final rebuild.
- Source package: Started, not final. Main source, section files, and figure PDFs exist; bibliography cleanup and internal provenance sanitization remain.
- Supplement/multimedia: Blocked pending real-image/UR5/video decision.
- Final PaperCept package: Not ready.

## Recommended next edits before final package

1. Replace self-referential our previous annotation-assisted… phrasing with neutral diagnostic-variant language.
2. Regenerate figure PDFs with non-Type-3 fonts and re-run pdffonts.
3. Remove or cite unused \bibitem entries.
4. Decide whether paper/main_experiment_provenance_run_log.md remains internal only or gets sanitized into an anonymous supplement.
5. Rebuild paper/main.pdf and repeat PDF metadata/font checks.

## 2026-07-07 follow-up check

The original recommended edits above have been partially resolved:

- Self-referential manuscript wording has been neutralized in the current source; a fresh source search did not find remaining "our previous" wording.
- The current bibliography has 22 cited keys and 22 bibitems, with missing `[]` and uncited `[]`.
- The current `paper/main.pdf` rebuild succeeds and remains 6 pages.
- The latest compiled-PDF font check found no Type 3 fonts.
- Citation metadata has been strengthened for several core references, including FreeGrasp, Molmo, MOKA, Grounding DINO, SpatialVLM, RoboPoint, VMRN, and occlusion-aware ally.

Remaining double-blind/package risks:

- Internal provenance and audit files still contain absolute server paths and should remain internal unless sanitized.
- Supplement/video readiness is still unresolved because no real-robot/real-image validation artifact is currently available.
- A final post-freeze package check is still required after no more manuscript edits are expected.

## 2026-07-07 PDF/figure metadata follow-up

Commands used:

- `pdfinfo paper/main.pdf`
- `pdfinfo -meta paper/main.pdf`
- `pdfinfo paper/figures/*.pdf`
- `pdfinfo -meta paper/figures/*.pdf`
- `pdffonts paper/figures/*.pdf`
- `pdftotext paper/main.pdf -` with identity/path grep
- Source scan over `paper/main.tex`, `paper/sections/*.tex`, `paper/create_figures.py`, and `scripts/audit_failure_outcomes.py`

Findings:

- `paper/main.pdf` has no Author/Title/Subject/Keywords fields in `pdfinfo`; Creator/Producer are TeX/pdfTeX only.
- `pdfinfo -meta` returns empty XMP metadata for `paper/main.pdf` and all checked figure PDFs.
- Figure PDFs expose only Matplotlib Creator/Producer and creation dates; no Author/Title/Subject/Keywords fields were present.
- Figure font check found no Type 3 fonts.
- Extracted manuscript text contains the expected anonymous header, `Anonymous Authors Under Review`, and no GitHub/repository/absolute-path/email hits.
- Source scan found no `/home/`, Windows drive path, repository-name, GitHub URL, or email hits in manuscript source, figure-generation source, or the failure-outcome audit script. The only `@` hits were LaTeX `tabular` column specifiers.

Updated risk status:

- Main PDF metadata: passed for current draft; recheck after final rebuild.
- Figure metadata/font status: passed for current draft; recheck if figures are regenerated.
- Source identity/path scan: passed for current manuscript source and new reproducibility script.
- Final package approval remains blocked only because the manuscript is not frozen and supplement/video/provenance decisions remain open.

## 2026-07-07 repeatable package-audit gate

The current PDF/source metadata checks are now captured by:

```bash
python scripts/audit_submission_package.py --root .
```

Current result: `AUDIT_OK`.

This script is read-only and does not rebuild the paper. It should be run after the final rebuild, alongside `pdflatex` and the failure-outcome audit, before approving an anonymous source/PDF package.
