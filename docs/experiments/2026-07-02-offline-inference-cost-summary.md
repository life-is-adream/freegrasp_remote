# Offline Inference Cost Summary

Date: 2026-07-02

## Purpose

This note records the offline inference-cost evidence used to address the
hidden-computational-overhead concern. The values come from
`full_protocol_summary.json` run manifests and count recorded calls rather than
real-robot latency.

The available logs do not contain reliable per-sample timestamps. Therefore
average wall-clock latency is not reconstructed from these artifacts.

## Call-Budget Table

| Method | N | Reasoning/sample | Router/sample | Repair/sample | Total calls/sample | Wall-clock/sample | RSR | SSR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 original protocol | 900 | 1.00 | 0.00 | 0.00 | 1.00 | N/A | 57.89 | 47.56 |
| Original + budget-2 vote | 300 | 2.00 | 0.00 | 0.00 | 2.00 | N/A | 56.67 | 46.33 |
| EGHC3_v3 no consensus | 300 | 2.29 | 1.00 | 0.02 | 3.32 | N/A | 59.00 | 56.00 |
| EGHC3_v3 no mask repair | 300 | 2.13 | 1.00 | 0.07 | 3.19 | N/A | 61.67 | 50.67 |
| EGHC3_v3 full | 900 | 2.10 | 1.00 | 0.07 | 3.16 | N/A | 60.89 | 55.22 |
| S1 oracle | 900 | 1.34 | 0.00 | 0.34 | 1.67 | N/A | 67.44 | 60.11 |

## Interpretation

EGHC3_v3 increases offline call budget from S0's 1.00 recorded call/sample to
3.16 recorded calls/sample. The added cost consists mainly of one router call
per sample plus route-specific reasoning and a small number of repair calls.

The original-protocol budget-2 vote ablation shows that simply doubling
reasoning calls does not reproduce EGHC3_v3's controlled SSR gain. On split 0,
budget-2 reaches 56.67% RSR and 46.33% SSR, below the S0 split-0 baseline,
while EGHC3_v3 reaches 61.00% RSR and 56.00% SSR. This supports the claim that
the benefit comes from the evidence-gated decision contract and mask repair,
not only from extra inference budget.

## Artifacts

- `data/output/statistics/ral_ablation_call_budget_with_routing.md`
- `data/output/statistics/ral_ablation_call_budget_with_routing.csv`
- `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json`
- `data/output/ablation_matrix/eghc_no_consensus_v1_split0/full_protocol_summary.json`
- `data/output/ablation_matrix/eghc_consensus_no_mask_repair_v1_split0/full_protocol_summary.json`
- `data/output/ablation_matrix/original_protocol_budget2_vote_split0/full_protocol_summary.json`
