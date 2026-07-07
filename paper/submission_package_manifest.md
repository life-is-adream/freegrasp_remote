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

## 2026-07-07 package-ownership update

This update records the current package state after the no-verifier ablation, citation metadata polish, and failure-denominator reproducibility pass. It does not assemble a final upload bundle.

### Current source/artifact ownership

| Artifact | Current path | Package role | Current decision |
|---|---|---|---|
| Review manuscript source | `paper/main.tex`, `paper/sections/*.tex` | Required source package input | Include after final freeze and source sanitization. |
| Review PDF | `paper/main.pdf` | Required review PDF | Rebuild from frozen source before upload; latest local check is 6 pages and no Type 3 fonts. |
| Figure PDFs | `paper/figures/*.pdf` | Required source/PDF inputs | Include after final metadata/font recheck. |
| Main results provenance | `paper/results_main_table.md` | Internal/paper-facing evidence note | Keep in repo; include in supplement only if anonymized and explicitly selected. |
| Main run provenance | `paper/main_experiment_provenance_run_log.md` | Internal provenance note | Keep internal by default because it can contain absolute server paths. |
| Ablation evidence | `paper/ablation_table.md` | Internal/paper-facing evidence note | Keep in repo; include in supplement only if anonymized and selected. |
| No-verifier audit | `paper/no_verifier_ablation_run_log.md` | Internal/paper-facing evidence note for Table II no-verifier row | Should be version-controlled with the paper evidence set; not automatically included in anonymous supplement. |
| Failure analysis | `paper/failure_analysis.md` | Internal/paper-facing evidence note | Keep in repo; supplement inclusion requires anonymization review. |
| Failure-denominator script | `scripts/audit_failure_outcomes.py` | Reproducibility script for metric outcome counts | Should be version-controlled; safe for source supplement only if paths remain relative and no server identity is embedded. |
| Submission-package audit script | `scripts/audit_submission_package.py` | Read-only gate for current PDF/source/package metadata checks | Should be version-controlled; run after final freeze before assembling the anonymous package. |
| Citation audit | `paper/citation_claim_audit.md` | Internal audit record | Keep internal unless converted to an anonymized supplement note. |
| Internal review | `paper/internal_review_report.md` | Internal review/revision record | Keep internal; do not submit. |
| Double-blind/package check | `paper/double_blind_package_check.md` | Internal package QA | Keep internal; do not submit. |
| Submission readiness audit | `paper/submission_readiness_audit.md` | Internal package QA | Keep internal; do not submit. |

### Exclude from anonymous upload unless explicitly sanitized

- Build byproducts: `paper/main.aux`, `paper/main.log`, `paper/missfont.log`, and `paper/__pycache__/`.
- Internal audit/review files: `paper/internal_review_report.md`, `paper/double_blind_package_check.md`, `paper/submission_readiness_audit.md`, and this manifest.
- Raw provenance notes containing absolute server paths, especially `paper/main_experiment_provenance_run_log.md`.
- Any file under `data/output/` unless transformed into an anonymized, minimal supplement artifact.

### Current blockers before final upload

1. Final freeze has not happened; source and PDF must be rechecked after the last manuscript edit.
2. Real-robot/video supplement remains unsupported unless a new validation artifact is produced.
3. Main-run reproducibility still carries the dirty-worktree and missing raw-console-log caveat.
4. Semantic failure taxonomy labels remain manuscript-authoritative; only metric outcome denominators are regenerated by script.
5. The working tree still contains uncommitted paper/code changes and new evidence files, so final version-control ownership is not settled.

### 2026-07-07 metadata check status

The current draft passed a fresh local PDF/source metadata check:

- `paper/main.pdf`: no Author/Title/Subject/Keywords fields; empty XMP metadata; 6 pages.
- `paper/figures/*.pdf`: no Author/Title/Subject/Keywords fields; empty XMP metadata; Matplotlib Creator/Producer only; no Type 3 fonts.
- Current manuscript source and `scripts/audit_failure_outcomes.py`: no absolute path, repository URL/name, email, or API-key-like hits in the checked files.

This does not replace the final post-freeze package check; it records that the current draft has no detected identity/path metadata blocker.

### 2026-07-07 reproducible package audit command

The current manual package checks are now backed by a read-only script:

```bash
python scripts/audit_submission_package.py --root .
```

Current result: `AUDIT_OK`.

This script checks required manuscript/source/figure files, cite/bibitem consistency, PDF metadata, XMP metadata, Type 3 fonts, extracted PDF text identity/path hits, and source identity/path/API-key-like hits. It does not rebuild LaTeX, call models, modify files, or inspect raw experiment outputs. Run it together with the LaTeX rebuild and `scripts/audit_failure_outcomes.py` after the final manuscript freeze.
