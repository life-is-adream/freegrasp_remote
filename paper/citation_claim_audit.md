# Citation and Claim Audit

Date: 2026-07-04
Status: T10 first-pass claim-to-support audit. This file maps manuscript claims to local citations and experiment artifacts. It is not yet an external metadata verification of every reference.

## Scope and boundary

Inputs inspected:

- paper/main.tex
- paper/sections/introduction.tex
- paper/sections/related_work.tex
- paper/sections/method.tex
- paper/sections/experiments.tex
- paper/sections/conclusion.tex
- paper/results_main_table.md
- paper/main_experiment_provenance_run_log.md
- paper/ablation_table.md
- paper/failure_analysis.md

Local citation-key check:

- Cited keys present in bibliography: chainofthought, freegrasp, groundingdino, moka, molmo, occlusion, relationship, robopoint, setofmark, spatialvlm, thinkgrasp.
- No cited key was missing from paper/main.tex in the local scan.
- Bibliography cleanup: 15 previously uncited manual bibliography entries were removed from paper/main.tex; all remaining bibitems are cited by the manuscript body.

## Claim-to-support matrix

| Status | Manuscript claim | Current support | Evidence path | Audit judgment / action |
|---|---|---|---|---|
| Supported by local artifacts | EGHC3_v3 uses no ground-truth features or benchmark difficulty labels. | Run manifest and summary provenance. | paper/main_experiment_provenance_run_log.md; EGHC3_v3 run_manifest.json; full_protocol_summary.json | Keep. This is one of the central defensible claims. |
| Supported by local artifacts | EGHC3_v3 achieves 548/900 RSR = 60.89% and 497/900 SSR = 55.22% on 900 FreeGraspData instructions. | Recomputed from sample-level out files. | paper/results_main_table.md; EGHC3_v3 split output JSON files | Keep. Counts and denominators are auditable. |
| Supported by local artifacts | Against controlled S0, EGHC3_v3 improves SSR by +7.67 pp and RSR by +3.00 pp. | S0 and EGHC3_v3 full 900-sample rows under same reused Molmo cache. | paper/results_main_table.md; S0 outputs; eghc3_bootstrap_ci.json | Keep, but phrase RSR cautiously because its lower CI reaches 0.00 pp. |
| Supported with caution | Scene-clustered bootstrap supports SSR more strongly than RSR. | Bootstrap CI file. | data/output/statistics/eghc3_bootstrap_ci.json; paper/results_main_table.md | Keep. Avoid implying RSR is as strong as SSR. |
| Supported with boundary | S1 oracle upper bound reaches 607/900 RSR = 67.44% and 541/900 SSR = 60.11%. | S1 sample-level output and summary. | paper/results_main_table.md; data/output/ablation_matrix/S1/ | Keep only as diagnostic/oracle, not deployable result. |
| Supported with boundary | Original FreeGrasp GPT-4o baseline is 47.3% RSR and 38.2% SSR. | Cited prior paper row, not locally re-audited sample-level JSON. | paper/sections/experiments.tex; paper/results_main_table.md; citation key freegrasp | Keep as descriptive-only comparison. Before final submission, verify exact source table and wording in the FreeGrasp paper. |
| Supported by local artifacts | Split-0 ablations show extra original-protocol VLM calls alone do not explain EGHC gains. | Budget-2 vote split-0 audit. | paper/ablation_table.md; docs/experiments/2026-07-01-original-protocol-budget2-vote-split0.md | Keep as split-0 mechanism check; do not generalize to full 900-sample ablation. |
| Supported by local artifacts | Mask repair mainly supports SSR rather than RSR. | No-mask-repair split-0 row and failure analysis. | paper/ablation_table.md; docs/experiments/2026-07-02-eghc-no-mask-repair-split0.md; paper/failure_analysis.md | Keep. Label as split-0 ablation plus failure-mode interpretation. |
| Supported by local artifacts | Hard-scene failures are dominated by blocker/visibility errors. | Failure taxonomy in manuscript and standalone failure analysis. | paper/failure_analysis.md; paper/sections/experiments.tex | Keep with caveat: semantic taxonomy currently lacks a standalone regeneration script. |
| Needs source-level verification | ThinkGrasp uses GPT-4o for strategic part grasping and struggles with hard occluded scenes. | Citation key thinkgrasp; local text only. | paper/sections/related_work.tex | Verify the exact paper claim before final submission or soften to avoid overclaiming. |
| Needs source-level verification | FreeGrasp introduced mark-based visual prompting with Molmo and GPT-4o. | Citation keys freegrasp and molmo. | paper/sections/related_work.tex | Verify paper wording and whether Molmo/GPT-4o attribution is exactly correct. |
| Needs source-level verification | MOKA proposes mark-based prompting for open-world robotic manipulation. | Citation key moka. | paper/sections/related_work.tex | Verify metadata and scope. |
| Needs source-level verification | Chain-of-thought prompting improves reasoning by decomposing complex tasks. | Citation key chainofthought. | paper/sections/related_work.tex | Broadly plausible, but still verify citation metadata and wording. |
| Needs source-level verification | Set-of-Mark prompting improves visual grounding through marked identifiers. | Citation key setofmark. | paper/sections/related_work.tex | Verify citation metadata and exact claim. |
| Needs source-level verification | SpatialVLM, RoboPoint, and Grounding DINO provide relevant spatial/affordance/open-set detection context. | Citation keys spatialvlm, robopoint, groundingdino. | paper/sections/related_work.tex | Verify that each cited work supports the specific sentence. |
| Needs source-level verification | Occlusion-aware grasp planning and visual manipulation relationship networks require or use explicit 3D/relation modeling. | Citation keys occlusion and relationship. | paper/sections/related_work.tex | Verify exact scope; soften if these papers do not require explicit 3D reconstruction. |
| Not yet established | Any real-robot, UR5, real-image, or closed-loop success claim. | No completed validation artifact in current materials. | paper/failure_analysis.md; paper/submission_readiness_audit.md | Do not claim. Current evidence is offline benchmark RSR/SSR and call budget. |
| Done | Manual bibliography no longer contains uncited entries after cleanup. | bibitem/cite scan. | paper/main.tex | Keep monitoring if new references are added. |

## Reference metadata audit queue

Manual bibliography entries must be checked against source metadata before final submission. Priority order:

1. freegrasp - central baseline, dataset, and prior reported GPT-4o numbers.
2. thinkgrasp - related-work comparison and hard-scene claim.
3. molmo, groundingdino, setofmark, moka - key method context.
4. spatialvlm, robopoint, relationship, occlusion - spatial/occlusion positioning.
5. Uncited entries - completed for the current draft; previously uncited entries were removed.

## External metadata/source spot-check

Source lookup date: 2026-07-04. Sources used were public paper pages, arXiv pages, project pages, IEEE/CVF/PMLR pages, and publisher-style pages found during this audit. This is a core-reference spot-check, not a full bibliographic export.

| Key | Local bibliography status | External check | Audit action |
|---|---|---|---|
| freegrasp | Title and 2025 year align with the arXiv/project page for  Free-form language-based robotic reasoning and grasping. | arXiv page confirms FreeGraspData and the free-form language robotic grasping task; project page confirms dataset framing. IROS 2025 venue should still be checked against final proceedings. | Keep but verify final venue/proceedings metadata before submission. |
| thinkgrasp | Title/authors/year broadly align with arXiv 2407.11298. | External abstract says ThinkGrasp uses GPT-4o for heavy clutter and reports strong performance in heavily obstructed/nearly invisible cases. | Manuscript wording was softened to avoid the unsupported claim that ThinkGrasp struggles with hard scenes. |
| molmo | Local entry says arXiv 2024. | arXiv confirms 2409.17146; CVF page indicates the paper appears as CVPR 2025. | Prefer final CVPR 2025 metadata if RA-L style allows citing the published version; otherwise keep arXiv with arXiv ID. |
| groundingdino | Local entry says ECCV 2024. | arXiv 2303.05499 and ECCV/CVF-style source align with open-set object detection and referring-expression grounding. | Keep; add DOI/proceedings details if available. |
| moka | Local entry says RSS 2024. | arXiv/project/RSS PDF align with mark-based visual prompting for open-world robotic manipulation. | Keep. |
| setofmark | Local entry says arXiv 2023. | arXiv 2310.11441 aligns with marked images improving GPT-4V visual grounding. | Keep unless a peer-reviewed venue version is preferred. |
| spatialvlm | Local entry says CVPR 2024. | arXiv/CVF/IEEE pages align with spatial reasoning and robotics downstream applications. | Keep. |
| robopoint | Local entry says CoRL 2024. | arXiv 2406.10721 and PMLR page align with spatial affordance prediction for robotics; PMLR publication page may carry 2025 proceedings metadata. | Verify exact CoRL/PMLR citation format and year. |
| relationship | Local entry says Humanoids 2018. | IEEE/arXiv-style sources align with Visual Manipulation Relationship Network for predicting manipulation relationships. | Keep. |
| occlusion | Local entry says IEEE T-ASE 2024. | Publisher/repository snippets align with GOAL method, binocular stereo vision, occlusion relationships, segmentation/localization, and EPSON arm validation. | Keep, but verify exact author list, volume, issue, pages, DOI. |
| chainofthought | Local entry previously said NeurIPS 2023; paper/main.tex now says NeurIPS 2022. | arXiv/OpenReview/Semantic Scholar identify Chain-of-Thought Prompting Elicits Reasoning in Large Language Models as 2022-era work and NeurIPS 2022, not NeurIPS 2023. | Fixed local bibliography year to NeurIPS 2022; still add DOI/proceedings metadata if desired. |

External source URLs consulted:

- FreeGrasp project: https://tev-fbk.github.io/FreeGrasp/
- FreeGrasp arXiv: https://arxiv.org/abs/2503.13082
- ThinkGrasp arXiv: https://arxiv.org/abs/2407.11298
- Molmo arXiv: https://arxiv.org/abs/2409.17146
- Molmo CVF PDF: https://openaccess.thecvf.com/content/CVPR2025/papers/Deitke_Molmo_and_PixMo_Open_Weights_and_Open_Data_for_State-of-the-Art_CVPR_2025_paper.pdf
- Grounding DINO arXiv: https://arxiv.org/abs/2303.05499
- MOKA arXiv: https://arxiv.org/abs/2403.03174
- Set-of-Mark arXiv: https://arxiv.org/abs/2310.11441
- SpatialVLM arXiv: https://arxiv.org/abs/2401.12168
- RoboPoint arXiv: https://arxiv.org/abs/2406.10721
- RoboPoint PMLR: https://proceedings.mlr.press/v270/yuan25c.html
- VMRN IEEE: https://ieeexplore.ieee.org/document/8625071
- VMRN arXiv: https://arxiv.org/abs/1802.08857
- GOAL/occlusion-aware ally: https://research.buaa.edu.cn/en/publications/grasping-with-occlusion-aware-ally-method-in-complex-scenes/
- Chain-of-thought arXiv: https://arxiv.org/abs/2201.11903

## Literature integration metadata checks

| Key | Status | Source checked | Manuscript claim supported | Remaining caveat |
|---|---|---|---|---|
| `graspmolmo` | verified | arXiv 2505.13441; PMLR/CoRL 2025 page; project page | Task-oriented Molmo fine-tuning with PRISM synthetic data. | CoRL citation kept compact; page range available in PMLR if final formatting needs it. |
| `graspcot` | verified | arXiv 2503.16013; official GitHub | Physical-property CoT reasoning for flexible 6-DoF grasp instructions. | Venue left as arXiv to avoid unverified proceedings claim. |
| `graspvla` | verified | arXiv 2505.03233; project/GitHub pages | VLA grasping foundation model pretrained on large synthetic action data. | Used only as design-space contrast, not as a direct baseline. |
| `maplegrasp` | verified | arXiv 2506.06535; GitHub | Mask-guided feature pooling for language-driven efficient robotic grasping. | Metrics not compared directly with EGHC. |
| `realvlgr1` | verified | arXiv 2603.14880; CVPR 2026 open-access page; GitHub | Visual-language grounding benchmark with masks, grasp poses, and contact points. | No claim that EGHC evaluates on this benchmark. |
| `vcotgrasp` | verified | arXiv 2510.05827; project page | Visual CoT/foundation-model contrast for language-driven grasp generation. | Used as literature contrast only. |
| `dexgraspvla` | verified | arXiv 2502.20900; AAAI 2026 page; project page | Hierarchical VLA contrast for dexterous grasping. | Not a FreeGraspData baseline. |
| `gloverpp` | verified | arXiv 2505.11865; project page | Affordance learning and global-to-local representation context. | Used for affordance/grounding context only. |
| `rtgrasp` | verified | arXiv 2402.06798; project/OpenReview pages | Reasoning grasping from indirect verbal instructions. | Bibkey retained as `rtgrasp` for manuscript brevity. |
| `graspclutter6d` | verified | arXiv 2504.06866; project/API pages | Real clutter benchmark motivating segmentation and occlusion bottlenecks. | No claim that EGHC uses this dataset. |


## T10 closeout status

- Claim-to-support matrix: Done for local manuscript and local artifacts.
- Citation key presence: Done after literature integration edits; current check reports 21 cites, 21 bibitems, missing [], and uncited [].
- External metadata/source verification: Core cited references spot-checked; CoT year and uncited bibliography cleanup were applied. Remaining work is exact BibTeX/DOI/page metadata cleanup and ongoing checks if references change.
- Final decision: T10 has local claim mapping, core external spot-checks, CoT year correction, and uncited-entry cleanup. It is not fully submission-ready only in the sense that exact DOI/page/proceedings metadata should still be polished before upload.
