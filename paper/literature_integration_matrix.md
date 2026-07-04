# Literature Integration Matrix

Date: 2026-07-04
Scope: strong-related papers from the local daily-paper folder. Weak-related notes are kept as backup only.

## Main integration set

| Paper | Citation key | Manuscript role | Evidence from daily note | External metadata status | Claim boundary |
|---|---|---|---|---|---|
| GraspMolmo: Generalizable Task-Oriented Grasping via Large-Scale Synthetic Data Generation | `graspmolmo` | Task-oriented open-vocabulary grasping and synthetic-data contrast. | Daily note highlights PRISM, 379k task-grasp samples, Molmo fine-tuning, RGB-D instruction-conditioned grasp prediction, and real-scene success. | Verified via arXiv 2505.13441 and PMLR/CoRL 2025 page. | Use to motivate task-oriented grasping; do not imply EGHC trains a new grasping foundation model. |
| GraspCoT: Integrating Physical Property Reasoning for 6-DoF Grasping under Flexible Language Instructions | `graspcot` | CoT/physical-property reasoning contrast. | Daily note highlights target parsing, physical property analysis, grasp action selection, IntentGrasp, and real-robot validation. | Verified via arXiv 2503.16013 and official GitHub. | Cite as arXiv unless final ICCV metadata is separately verified. |
| GraspVLA: a Grasping Foundation Model Pre-trained on Billion-scale Synthetic Action Data | `graspvla` | VLA/foundation-model contrast. | Daily note highlights SynGrasp-1B, synthetic pretraining, open-vocabulary generalization, and sim-to-real framing. | Verified via arXiv 2505.03233 and project/GitHub pages. | Use only as contrast to EGHC's modular inference-time routing, not as a direct baseline. |
| MapleGrasp: Mask-guided Feature Pooling for Language-driven Efficient Robotic Grasping | `maplegrasp` | Segmentation-aware language grasping and mask bottleneck context. | Daily note highlights mask-guided feature pooling, RefGraspNet, OCID-VLG gains, and real Franka evaluation. | Verified via arXiv 2506.06535 and GitHub page. | Use to support mask-aware framing; do not compare EGHC SSR directly to MapleGrasp metrics. |
| RealVLG-R1: A Large-Scale Real-World Visual-Language Grounding Benchmark for Robotic Perception and Manipulation | `realvlgr1` | Real-world visual-language grounding benchmark context. | Daily note highlights multi-granularity grounding, masks, contact points, grasp poses, and public data/code. | Verified via arXiv 2603.14880, CVPR 2026 open-access page, and GitHub. | Use to motivate grounding benchmarks; no claim that EGHC was evaluated on RealVLG-R1. |
| VCoT-Grasp: Grasp Foundation Models with Visual Chain-of-Thought Reasoning for Language-driven Grasp Generation | `vcotgrasp` | Visual CoT/foundation-model contrast. | Daily note marks strong relevance through visual chain-of-thought and language-driven grasp generation. | Verified via arXiv 2510.05827. | Use as contrast to end-to-end foundation models; avoid unverified numeric comparisons. |
| DexGraspVLA: A Vision-Language-Action Framework Towards General Dexterous Grasping | `dexgraspvla` | Hierarchical VLA contrast. | Daily note highlights VLM high-level planning plus low-level action policy for dexterous grasping. | Verified via arXiv 2502.20900, AAAI 2026 page, and project page. | Use as modular VLA contrast; not a FreeGraspData baseline. |
| GLOVER++: Unleashing the Potential of Affordance Learning from Human Behaviors for Robotic Manipulation | `gloverpp` | Affordance-learning contrast and future evidence direction. | Daily note highlights global-to-local affordance reasoning and transfer to manipulation tasks. | Verified via arXiv 2505.11865 and project page. | Use only for affordance/grounding context, not as grasp-order baseline. |
| Reasoning Grasping via Multimodal Large Language Model | `rtgrasp` | Reasoning-grasping lineage. | Daily note highlights implicit intention, MLLM reasoning, GraspNet-derived benchmark, and real-world validation. | Verified via arXiv 2402.06798 and project/OpenReview pages. | Use to position reasoning grasping; do not treat as blocker-first method. |
| ThinkGrasp: A Vision-Language System for Strategic Part Grasping in Clutter | `thinkgrasp` | Strategic obstacle-removal and cluttered part-grasping lineage. | Daily note highlights GPT-4o reasoning, obstacle removal, part grasping, and iterative execution. | Already cited; verified via arXiv 2407.11298 and project/GitHub pages. | Do not say it struggles with hard scenes; use as strong related work. |
| GraspClutter6D: A Large-scale Real-world Dataset for Robust Perception and Grasping in Cluttered Scenes | `graspclutter6d` | Clutter/occlusion benchmark context. | Daily note highlights 1,000 real clutter scenes, 14.1 objects/scene, 62.6% occlusion, and segmentation/grasping benchmark failures. | Verified via arXiv 2504.06866 and project/API pages. | Use to motivate cluttered perception bottlenecks; no claim EGHC evaluated on this dataset. |

## Excluded or backup-only notes

| Paper note | Reason |
|---|---|
| InternVLA-M1 | Weak-related general VLA policy; useful only for future spatial-guidance discussion. |
| ORACLE-Grasp | Weak-related zero-shot affordance grasping; no code and less aligned with EGHC evaluation. |
| UAD | Weak-related note; not needed for current RA-L argument. |
| FineVLA | Weak-related VLA fine-tuning context; not needed for current manuscript. |
| GraspMAS | Weak-related multi-agent planning angle; can stay backup. |
| PhyGrasp | Weak-related physics-reasoning context; possible future-work citation, not current core. |
| DAM-VLA | Weak-related action-model VLA; useful only for broad modularity contrast. |
| TwinBrainVLA | Weak-related catastrophic-forgetting contrast; avoid adding unless paper explicitly discusses VLA fine-tuning risks. |
