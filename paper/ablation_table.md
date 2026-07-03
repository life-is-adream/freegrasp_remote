# EGHC RA-L Ablation Table

Date: 2026-07-03

Source: synced from `docs/experiments/ablation_table.md` for the paper-facing ablation material.
Sync date: 2026-07-04.
Repository HEAD at sync: `5b5dd3fcee860f4aa56e35b34b6110882479068b`.
Provenance note: numerical rows and interpretations are copied from the source experiment log without changing results; source artifacts remain listed below.

Purpose: collect the current ablation evidence for the RA-L revision and pin
down the meaning of the historical S2-S7 labels. All rows below are no-GT
unless explicitly marked oracle.

## Naming Disambiguation

- Current EGHC split-0 "no point-constrained segmentation" means
  `eghc_consensus_no_mask_repair_v1`: EGHC routing and consensus are kept, but
  `eghc_mask_repair_v1` is disabled and segmentation falls back to `baseline`.
- Historical S6 means `automatic_no_geometry_repair`: this is the old automatic
  predicted-geometry line with geometry/point-evidence repair disabled. It is
  not the current EGHC no-mask-repair row.
- Historical S7 means `automatic_no_id_repair`: this is the old automatic
  predicted-geometry line with ID repair disabled.
- Current EGHC split-0 "no consensus" means `eghc_no_consensus_v1`: the
  evidence-gated cascade is kept, but the `eghc_consensus_v1` route guard is
  removed.

## Current Split-0 Ablation Table

All rows use split 0 only (`N=300`) except the frozen full-run row noted in the
source artifact. Split-0 rows reuse the same Molmo cache and MiMo-v2.5.

| Label | Run / policy | Changed factor | Routing | Guard | Segmentation | N | RSR | SSR | Calls/sample | Main interpretation |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| A0 | `S0` split 0 | Controlled baseline | none | none | baseline | 300 | 58.33 | 47.67 | 1.00 | Original FreeGrasp decision contract under same cache/protocol control. |
| A1 | `original_protocol_budget2_vote_split0` | Doubles original-protocol reasoning budget | none | none | baseline | 300 | 56.67 | 46.33 | 2.00 | Extra VLM calls alone do not explain EGHC gains. |
| A2 | `eghc_no_consensus_v1_split0` | Removes hierarchical consensus guard | evidence-gated cascade | none | `eghc_mask_repair_v1` | 300 | 59.00 | 56.00 | 3.32 | Consensus mainly protects first-grasp ID selection on split 0. |
| A3 | `eghc_consensus_no_mask_repair_v1_split0` | Removes point-constrained mask repair | evidence-gated cascade | `eghc_consensus_v1` | baseline | 300 | 61.67 | 50.67 | 3.19 | Mask repair primarily contributes SSR; RSR is essentially unchanged. |
| A4 | `EGHC3_v3_qwen35_full` split 0 | Proposed deployable method | evidence-gated cascade | `eghc_consensus_v1` | `eghc_mask_repair_v1` | 300 | 61.00 | 56.00 | 3.16 | Combined routing, consensus, and mask repair gives the best deployable split-0 SSR. |
| A5 | `S1` split 0 | Oracle diagnostic upper bound | oracle/difficulty-assisted | n/a | repair path | 300 | 69.00 | 62.67 | 1.67 | Oracle evidence shows remaining headroom; not deployable. |

Key split-0 deltas:

| Comparison | Delta RSR | Delta SSR | Interpretation |
|---|---:|---:|---|
| A1 - A0 | -1.67 pp | -1.33 pp | Budget-only voting is not beneficial under the original direct-answer contract. |
| A4 - A1 | +4.33 pp | +9.67 pp | EGHC is not merely a two-call prompt-budget effect. |
| A4 - A2 | +2.00 pp | +0.00 pp | Consensus improves RSR in this split while SSR is similar. |
| A4 - A3 | -0.67 pp | +5.33 pp | Point-constrained mask repair is the clearest segmentation component. |
| A5 - A4 | +8.00 pp | +6.67 pp | Oracle evidence still improves both reasoning and segmentation. |

## Historical S2-S7 Mapping

These rows are retained for provenance and diagnosis. They belong to the older
automatic routing line, not to the final EGHC3_v3 method name. They should not
replace the current split-0 EGHC component table above.

| Label | Subset policy | Routing | Segmentation | Disabled component | N | RSR | SSR | Calls/sample | Paper role |
|---|---|---|---|---|---:|---:|---:|---:|---|
| S2 | `automatic_evidence_v1` | count-only | `point_retry` | none | 900 | 49.33 | 45.22 | 1.37 | Historical automatic evidence baseline. |
| S3 | `automatic_evidence_v1` | VLM two-stage | `point_retry` | none | 900 | 43.11 | 38.89 | 1.46 | Historical VLM-router diagnostic. |
| S4 | `automatic_evidence_v1` | predicted geometry | geometric consistency | none | 900 | 45.33 | 40.56 | 1.63 | Historical predicted-geometry router. |
| S5 | `automatic_no_blocker_first` | predicted geometry | geometric consistency | blocker-first route | 900 | 44.78 | 40.44 | 1.68 | Historical no-blocker-first ablation. |
| S6 | `automatic_no_geometry_repair` | predicted geometry | geometric consistency | geometry/point-evidence repair | 900 | 45.11 | 40.11 | 1.34 | Historical "no geometry/point repair" ablation. |
| S7 | `automatic_no_id_repair` | predicted geometry | geometric consistency | ID repair | 900 | 44.67 | 40.33 | 1.62 | Historical no-ID-repair ablation. |

## Source Artifacts

- Current budget-control audit:
  `docs/experiments/2026-07-01-original-protocol-budget2-vote-split0.md`
- Current mask-repair ablation audit:
  `docs/experiments/2026-07-02-eghc-no-mask-repair-split0.md`
- Current routing ablation audit:
  `docs/experiments/2026-07-02-eghc-routing-ablation-split0.md`
- Offline call-budget table:
  `data/output/statistics/ral_ablation_call_budget_with_routing.md`
- Historical run summaries:
  `data/output/ablation_matrix/S2/full_protocol_summary.json` through
  `data/output/ablation_matrix/S7/full_protocol_summary.json`

## Manuscript Use

Use the current split-0 table to answer the reviewer concern that EGHC is a
monolithic or merely higher-budget method. Use S2-S7 only as historical
diagnostics or appendix provenance. The strongest controlled component claim is
that mask repair improves SSR, while consensus contributes mainly to RSR on
split 0.
