# Submission Readiness Audit

Scope: first-pass local-file audit for citation readiness, internal review, double-blind formatting, and submission package assembly. This audit used repository files only. It did not use the network, did not run paid APIs, did not run experiments, and does not claim that citation verification, internal review, or double-blind review has been completed.

Protected files not edited in this pass: paper/results_main_table.md, paper/failure_analysis.md, paper/ablation_table.md.

## Post-closeout update

After the first-pass readiness inventory, the following files were created and should be treated as the current follow-on audit artifacts:

- paper/results_main_table.md
- paper/main_experiment_provenance_run_log.md
- paper/ablation_table.md
- paper/failure_analysis.md
- paper/citation_claim_audit.md
- paper/internal_review_report.md
- paper/double_blind_package_check.md
- paper/submission_package_manifest.md

The item-level rows below are preserved as the original first-pass inventory. For current T10/T11/T12 status, use the dedicated audit files above.

Current package-fix update: manuscript self-reference wording has been neutralized, the Chain-of-Thought bibliography year has been corrected, the unsupported ThinkGrasp hard-scene wording has been softened, figure PDFs have been regenerated without Type 3 fonts, and `paper/main.pdf` has been rebuilt. The 15 uncited manual bibliography entries were removed from `paper/main.tex`.

## 1. Citation audit TODO / risks

| Status | Item | Local evidence path | Notes / next action |
| --- | --- | --- | --- |
| Needs work | Build a claim-to-citation matrix before T10 can be marked complete. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:67, docs/superpowers/plans/2026-07-04-ral-master-plan.md:221 | Master plan says T10 citation and claim audit is not started and asks for paper/citation_claim_audit.md. That file is currently absent. |
| Needs work | Verify every manual \bibitem against source metadata. | paper/main.tex:41, paper/main.tex:42, paper/main.tex:68 | References are embedded in \thebibliography; no paper/main.bib or paper/references.bib was found. Manual entries need title/year/venue/author checks before submission. |
| Needs work | Remove or justify uncited bibliography entries. | paper/main.tex:44, paper/main.tex:46, paper/main.tex:48, paper/main.tex:49, paper/main.tex:58 | First-pass key scan found many \bibitems not cited by current section files, including gpt4, sam, langsam, graspnet, metagraspnetv2, 
t2, saycan, palme, codeaspolicies, qwenvl, \florence2, kosmos2, structuredoutput, droid, and openx. Confirm whether to cite them or delete them. |
| Done | Confirm current cited keys have matching manual bibliography keys. | paper/sections/introduction.tex:5, paper/sections/related_work.tex:5, paper/sections/related_work.tex:9, paper/sections/related_work.tex:13, paper/sections/related_work.tex:17, paper/sections/experiments.tex:5 | Local scan found no cited key missing from paper/main.tex bibliography. This is only a key-presence check, not bibliographic correctness. |
| Needs work | Audit citation support for baseline and prior-work claims. | paper/sections/experiments.tex:5, paper/sections/experiments.tex:9, paper/sections/experiments.tex:26, paper/sections/related_work.tex:5 | Claims comparing to FreeGrasp/ThinkGrasp and reported GPT-4o baseline should be tied to exact source statements and tables. Do not mark complete without source-level verification. |
| Needs work | Audit claims that rely on experiment artifacts rather than citations. | docs/experiments/2026-07-02-offline-inference-cost-summary.md:41, docs/experiments/ablation_table.md:62, paper/sections/experiments.tex:60 | Call-budget and ablation claims cite local run manifests/statistics, not papers. Submission text should distinguish empirical provenance from literature citations. |

## 2. Internal review checklist

| Status | Item | Local evidence path | Notes / next action |
| --- | --- | --- | --- |
| Needs work | Create strict RA-L reviewer simulation report. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:68, docs/superpowers/plans/2026-07-04-ral-master-plan.md:222 | Master plan says T11 internal review is not started and asks for paper/internal_review_report.md. That file is currently absent. |
| Done | Confirm manuscript draft and compiled PDF exist for review input. | paper/main.tex, paper/main.pdf, paper/sections/introduction.tex, paper/sections/method.tex, paper/sections/experiments.tex, paper/sections/conclusion.tex | Draft is present and compiled PDF exists, so reviewer simulation can operate on a concrete manuscript. |
| Needs work | Review novelty and claim boundaries against evidence level. | paper/sections/introduction.tex:9, paper/sections/experiments.tex:15, docs/superpowers/plans/2026-07-04-ral-master-plan.md:79 | Manuscript positions annotation-assisted analyses as diagnostics and no-GT EGHC3_v3 as central; internal review should check that all claims preserve this boundary. |
| Needs work | Review result validity, denominators, and split/full-protocol separation. | paper/sections/experiments.tex:15, docs/experiments/2026-07-01-original-protocol-budget2-vote-split0.md:84, docs/experiments/2026-07-02-eghc-no-mask-repair-split0.md:73, docs/experiments/2026-07-02-eghc-routing-ablation-split0.md:141 | Full 900-sample headline and split-0 ablations are both present; review must ensure the manuscript never overgeneralizes split-0 ablations. |
| Needs work | Review failure analysis completeness. | paper/sections/experiments.tex:148, docs/superpowers/plans/2026-07-04-ral-master-plan.md:63, docs/superpowers/plans/2026-07-04-ral-master-plan.md:103 | Failure taxonomy table is in manuscript, but master plan says standalone paper/failure_analysis.md is missing. This pass did not create it because T6 target files are protected. |
| Needs work | Review cost/latency wording. | paper/sections/experiments.tex:60, paper/sections/experiments.tex:64, docs/experiments/2026-07-02-offline-inference-cost-summary.md:9, docs/experiments/2026-07-02-offline-inference-cost-summary.md:12 | Current materials correctly frame costs as call budgets and state reliable per-sample timestamps are unavailable; reviewer pass should check every latency-adjacent sentence. |
| Needs work | Review figure/table readability and caption-claim alignment. | paper/figures/system_overview.pdf, paper/figures/eghc_architecture.pdf, paper/figures/main_results.pdf, paper/figures/ablation.pdf, paper/figures/route_distribution.pdf, docs/superpowers/plans/2026-07-04-ral-master-plan.md:65 | Initial PDFs exist, but the master plan says figure readability audit remains after T6/T7 decision. |
| Blocked | Review real-world or real-image validation claims. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:52, docs/superpowers/plans/2026-07-04-ral-master-plan.md:64, docs/superpowers/plans/2026-07-04-ral-master-plan.md:242 | Real-world evidence is explicitly not started; review cannot approve claims depending on UR5/real-image validation until the protocol decision is made. |

## 3. Double-blind format risks

| Status | Item | Local evidence path | Notes / next action |
| --- | --- | --- | --- |
| Needs work | Run formal double-blind/package check. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:69, docs/superpowers/plans/2026-07-04-ral-master-plan.md:223, docs/superpowers/plans/2026-07-04-ral-master-plan.md:244 | Master plan says T12 is not started. This file is only first-pass risk inventory. |
| Done | Current visible author block is anonymized. | paper/main.tex:19, paper/main.tex:20, paper/main.tex:21 | The manuscript uses Anonymous Authors and Under Review. |
| Needs work | Check PDF metadata and embedded source paths before submission. | paper/main.pdf, paper/main.log:9, paper/main.log:12 | Build log contains local TeX paths and class URL; PDF metadata was not inspected in this pass. Submission package should sanitize metadata and avoid source path leakage. |
| Needs work | Audit repository/source links if added to paper or supplementary material. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:224, docs/superpowers/plans/2026-07-04-ral-master-plan.md:225, docs/experiments/2026-07-03-groundingdino-compatibility-patch.md:6 | Plan explicitly calls out anonymizing repository links. Compatibility notes mention an upstream repository/commit; ensure such details are not blindly copied into anonymous supplement. |
| Needs work | Check self-reference wording. | paper/sections/introduction.tex:9, paper/sections/experiments.tex:9, paper/sections/experiments.tex:19 | Text says  our previous annotation-assisted… and compares with the prior FreeGrasp paper. Double-blind review should decide whether this self-reference is acceptable or needs neutral phrasing. |
| Needs work | Check acknowledgments, funding, affiliations, and emails remain absent. | paper/main.tex:19, paper/main.tex:68 | No obvious acknowledgment/funding block appears in the inspected main file, but a formal full-source scan is still needed before T12. |
| Needs work | Check generated figures do not reveal author identity or local paths. | paper/create_figures.py, paper/figures/system_overview.pdf, paper/figures/eghc_architecture.pdf, paper/figures/main_results.pdf, paper/figures/ablation.pdf, paper/figures/route_distribution.pdf | Figure files exist, but metadata/embedded-font/path inspection was not performed. |

## 4. Submission package file checklist

| Status | Item | Local evidence path | Notes / next action |
| --- | --- | --- | --- |
| Done | Main LaTeX source exists. | paper/main.tex | Source uses IEEEtran journal class and includes section files. |
| Done | Section sources exist. | paper/sections/introduction.tex, paper/sections/related_work.tex, paper/sections/method.tex, paper/sections/experiments.tex, paper/sections/conclusion.tex | These are the current manuscript body inputs. |
| Done | Main compiled PDF exists. | paper/main.pdf | Existing PDF can be used for first internal review; final package still needs rebuild and metadata check. |
| Done | Initial figure PDFs exist. | paper/figures/system_overview.pdf, paper/figures/eghc_architecture.pdf, paper/figures/main_results.pdf, paper/figures/ablation.pdf, paper/figures/route_distribution.pdf | Figure readability and embedded-font checks remain open. |
| Needs work | Bibliography source file is absent because references are manual. | paper/main.tex:41, paper/main.tex:68 | Decide whether final package should keep manual bibliography or move to .bib for auditability. |
| Needs work | Citation-claim audit report missing. | paper/citation_claim_audit.md, docs/superpowers/plans/2026-07-04-ral-master-plan.md:221 | Required by master plan P5. |
| Needs work | Internal review report missing. | paper/internal_review_report.md, docs/superpowers/plans/2026-07-04-ral-master-plan.md:222 | Required by master plan P5. |
| Needs work | Failure analysis standalone file missing. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:63, docs/superpowers/plans/2026-07-04-ral-master-plan.md:103 | T6 output is protected in this task and was not created. |
| Needs work | Results/ablation paper-facing standalone sources need final ownership decision. | docs/experiments/ablation_table.md, docs/experiments/2026-07-02-offline-inference-cost-summary.md, paper/sections/experiments.tex | docs/experiments/ablation_table.md exists; protected paper/results_main_table.md and paper/ablation_table.md were not edited/created in this pass. |
| Needs work | Supplementary/video/readme package not found in inspected paper folder. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:69, docs/superpowers/plans/2026-07-04-ral-master-plan.md:244 | T12 asks for double-blind PDF, source, references, video/readme, and metadata. |
| Blocked | Final submission package cannot be marked ready. | docs/superpowers/plans/2026-07-04-ral-master-plan.md:70, docs/superpowers/plans/2026-07-04-ral-master-plan.md:234 | T10/T11/T12 are not started, real validation decision is pending, and final source/metadata checks are incomplete. |

## 2026-07-07 readiness update

This update supersedes the stale "not started" status in the original first-pass inventory while preserving the historical checklist above.

### Completed or materially improved

- Citation/claim audit now exists at `paper/citation_claim_audit.md`.
- Internal review report now exists at `paper/internal_review_report.md` and includes the post-no-verifier re-review.
- Failure analysis now exists at `paper/failure_analysis.md`.
- The metric-level failure denominator is reproducible with `scripts/audit_failure_outcomes.py`, which verifies 900 total rows and 431 non-joint-success cases from saved detail JSON.
- No-verifier split-0 evidence is documented in `paper/no_verifier_ablation_run_log.md` and written into the manuscript as bounded split-0 mechanism evidence.
- Bibliography now has 22 cited keys and 22 bibitems with no missing or uncited keys.
- Proceedings/page/DOI metadata has been improved for FreeGrasp, Molmo, MOKA, Grounding DINO, SpatialVLM, RoboPoint, VMRN, and occlusion-aware ally references.
- The current manuscript compiles to a 6-page `paper/main.pdf`; the latest check found no Type 3 fonts in the compiled PDF.
- Double-blind self-reference search did not find remaining "our previous" or equivalent self-identifying manuscript wording in the current source.

### Still not final

- Real-robot, real-image, UR5, and video/supplement readiness remain unsupported unless a new validation artifact is produced.
- Main-run clean-checkout reproducibility remains limited by the dirty-worktree provenance and missing original raw console log.
- Semantic failure categories such as wrong blocker versus direct-when-blocker-needed remain manuscript-authoritative labels; only the metric denominator is script-regenerated.
- Internal provenance files contain absolute server paths and should not be copied into an anonymous package without sanitization.
- Final PaperCept/source package is not approved until a fresh post-freeze package inventory, PDF metadata check, figure metadata/font check, and source sanitization pass are run.

## 2026-07-07 package ownership note

Two new evidence/reproducibility artifacts are intentionally part of the working paper evidence set and should not remain ambiguous before final handoff:

- `paper/no_verifier_ablation_run_log.md`: evidence note supporting the split-0 no-verifier ablation row. Recommendation: version-control with the internal paper evidence set; do not include in anonymous supplement unless paths and run metadata are sanitized.
- `scripts/audit_failure_outcomes.py`: read-only script that regenerates the metric-level failure outcome table from saved detail JSON. Recommendation: version-control as a reproducibility script; safe for a source/supplement package only after confirming it uses relative paths and contains no server/user identity.

The package manifest now records these ownership decisions. Final upload remains blocked until post-freeze source/PDF/package checks are run.

## 2026-07-07 PDF/source metadata check

Current draft status after a fresh local check:

- Main PDF metadata: no Author/Title/Subject/Keywords fields; empty XMP metadata; Creator/Producer are TeX/pdfTeX.
- Figure PDF metadata: no Author/Title/Subject/Keywords fields; empty XMP metadata; Matplotlib Creator/Producer and creation dates only.
- Figure fonts: no Type 3 fonts found.
- Extracted manuscript text: expected anonymous header only; no GitHub/repository/absolute-path/email hits.
- Source scan: no `/home/`, Windows drive path, repository-name, GitHub URL, email, or API-key-like hits in `paper/main.tex`, section files, `paper/create_figures.py`, or `scripts/audit_failure_outcomes.py`.

This resolves the current-draft metadata check item, but not the final upload gate: after the manuscript is frozen, rebuild the exact upload PDF/source archive and rerun the same checks.

## 2026-07-07 reproducible package-audit script

Added `scripts/audit_submission_package.py` as a read-only gate for the current manuscript package. The script checks:

- required manuscript/source/figure/evidence files exist;
- cite keys and manual bibitems match;
- main and figure PDFs have no author/title/subject/keyword fields;
- XMP metadata has no identity/path hints;
- PDFs do not use Type 3 fonts;
- extracted main-PDF text has no unexpected identity/path hits;
- manuscript source, figure-generation source, and the failure-outcome script have no obvious absolute path, repository, email, or API-key-like hits.

Current command:

```bash
python scripts/audit_submission_package.py --root .
```

Current result: `AUDIT_OK`.

This gives the final package process a repeatable local gate, but it does not replace the required post-freeze rebuild, source archive inventory, or real-robot/video decision.
