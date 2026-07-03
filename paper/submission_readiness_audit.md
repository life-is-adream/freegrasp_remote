# Submission Readiness Audit

Scope: first-pass local-file audit for citation readiness, internal review, double-blind formatting, and submission package assembly. This audit used repository files only. It did not use the network, did not run paid APIs, did not run experiments, and does not claim that citation verification, internal review, or double-blind review has been completed.

Protected files not edited in this pass: paper/results_main_table.md, paper/failure_analysis.md, paper/ablation_table.md.

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
