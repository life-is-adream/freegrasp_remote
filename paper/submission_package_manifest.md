# Submission Package Manifest

Date: 2026-07-04
Status: draft manifest for RA-L submission assembly. This manifest identifies current package inputs and blockers; it is not a final upload bundle.

## Current manuscript inputs

| Package role | Current path | Status | Notes |
|---|---|---|---|
| Main LaTeX source | paper/main.tex | Present | Uses IEEEtran journal class and manual thebibliography. |
| Section sources | paper/sections/*.tex | Present | Introduction, related work, method, experiments, conclusion. |
| Current compiled PDF | paper/main.pdf | Present | Six pages in current pdfinfo; rebuild after final edits. |
| Figures | paper/figures/*.pdf | Present, font check passed | Regenerated with Matplotlib PDF fonttype 42; current pdffonts check reports no Type 3 fonts. |
| Main result evidence | paper/results_main_table.md | Present internal/paper-facing note | Good for provenance; decide whether to include as supplement. |
| Main run provenance | paper/main_experiment_provenance_run_log.md | Present internal note | Contains absolute server path; sanitize before anonymous supplement. |
| Ablation evidence | paper/ablation_table.md | Present | Paper-facing copy of detailed experiment log. |
| Failure analysis | paper/failure_analysis.md | Present | Includes taxonomy caveats and paper insertion block. |
| Citation audit | paper/citation_claim_audit.md | Present first pass | External metadata verification still needed. |
| Internal review | paper/internal_review_report.md | Present first pass | Use as revision checklist, not submission artifact. |
| Double-blind/package check | paper/double_blind_package_check.md | Present first pass | Lists blockers for final package. |

## Files not ready for final package

| Needed artifact | Current status | Blocker |
|---|---|---|
| Clean anonymous PDF | Current draft passes local identity/font metadata checks | Final rebuild and exact bibliography metadata cleanup and supplement decisions still pending before upload. |
| Clean source archive | Closer, not final | Uncited bibliography entries were removed; internal path/provenance documents still need supplement-sanitization decisions. |
| Supplementary README | Missing | Need decide what evidence artifacts are included and how paths are anonymized. |
| Video/multimedia | Blocked | Real-image/UR5 validation path not decided/completed. |
| External citation verification record | Not final | Manual bibliography metadata and cited-claim support need source-level verification. |

## Draft package assembly rule

Do not assemble or upload a final PaperCept package until these gates pass:

1. paper/citation_claim_audit.md has no unresolved central citation/source checks.
2. paper/internal_review_report.md major concerns are addressed or explicitly deferred.
3. paper/double_blind_package_check.md has no open identity/path/font blockers for the review PDF/source archive.
4. The final PDF is rebuilt from the exact source archive intended for upload.
5. Any supplement is anonymous and does not include absolute local/server paths.
