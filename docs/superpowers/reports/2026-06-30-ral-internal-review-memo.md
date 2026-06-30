# RA-L Internal Review Memo: EGHC3 Revision

Date: 2026-06-30

Purpose: one-page review package for advisor, Gemini, and GLM5.2 checks before
final manuscript polishing.

## One-Sentence Argument

In free-form language-guided grasping in clutter, EGHC converts a direct VLM
answer into an evidence-gated target/blocker routing process, improving
FreeGraspData reasoning and segmentation under a no-ground-truth 900-sample
protocol while exposing blocker visibility and instance ambiguity as the main
remaining bottlenecks.

## Frozen Mainline

| Item | Value |
|---|---|
| Main method | EGHC3_v3 / Evidence-Gated Hierarchical Consensus Routing |
| Frozen run | `data/output/ablation_matrix/EGHC3_v3_qwen35_full` |
| Model path | MiMo-v2.5 main VLM with recorded Qwen adjudication path |
| Samples | 900, splits 0/1/2 |
| Molmo cache | reused, SHA-256 prefix `705d0883` |
| GT features used at inference | No |
| Benchmark difficulty label used at inference | No |
| Main result | 60.89% RSR / 55.22% SSR |

Qwen3.7-plus runs are not part of the paper mainline. They should remain model
sensitivity/debugging material until the exact inference path is verified.

## Evidence Summary

| Comparison | Metric | Delta | 95% CI | Interpretation |
|---|---:|---:|---:|---|
| EGHC3_v3 - S0 | RSR | +3.00 pp | [0.00, 5.95] pp | positive but cautious |
| EGHC3_v3 - S0 | SSR | +7.67 pp | [4.19, 11.33] pp | strongest controlled gain |
| S1 - EGHC3_v3 | RSR | +6.56 pp | [3.41, 9.80] pp | oracle headroom |
| S1 - EGHC3_v3 | SSR | +4.89 pp | [1.86, 7.95] pp | oracle headroom |

Bootstrap protocol: paired, scene-clustered resampling over 900 aligned rows
and 291 scene clusters. The original FreeGrasp GPT-4o comparison remains
descriptive because row-level original predictions are not available.

## Failure Taxonomy

| Error type | Easy | Medium | Hard | Total |
|---|---:|---:|---:|---:|
| Correct ID, failed mask | 7 | 8 | 10 | 25 |
| Wrong target instance | 36 | 0 | 0 | 36 |
| Wrong blocker | 0 | 38 | 125 | 163 |
| Direct, blocker needed | 0 | 77 | 76 | 153 |
| Blocker, direct possible | 0 | 0 | 0 | 0 |
| No usable mask | 33 | 8 | 13 | 54 |

Main interpretation: easy failures are mostly mask or instance ambiguity;
medium and hard failures are dominated by blocker selection and missing
blocker-needed cases.

## Claim-Evidence Map

| Claim | Evidence | Status |
|---|---|---|
| EGHC improves FreeGraspData SSR over same-cache S0 | +7.67 pp SSR, 95% CI [4.19, 11.33] | Supported |
| EGHC improves RSR over same-cache S0 | +3.00 pp RSR, 95% CI [0.00, 5.95] | Supported but cautious |
| EGHC uses deployable evidence only | Run manifest: `deployable_predicted`, no GT features, no difficulty labels | Supported |
| S1 is not deployable but measures headroom | S1 uses GT features and difficulty labels; +6.56 pp RSR, +4.89 pp SSR over EGHC | Supported |
| EGHC solves occlusion/blocker reasoning | Hard-scene failures remain high | Not supported; avoid |
| RSR/SSR gains imply real-robot success | No real-robot sequence evaluation yet | Not supported; avoid |

## Manuscript Status

- Title and abstract now center EGHC rather than FreeGrasp++ or S1.
- Experiments contain main comparison, oracle headroom, per-stratum analysis,
  failure taxonomy, and paired bootstrap table.
- Method section states the no-GT/no-difficulty boundary.
- Conclusion now states the bootstrap-supported SSR gain and the cautious RSR
  interpretation.
- PDF compiles as `paper/main.pdf`.

## External Review Prompt

Please review the RA-L draft with a skeptical reviewer stance. Focus on:

1. Whether any abstract/introduction claim exceeds the evidence.
2. Whether the original FreeGrasp GPT-4o baseline is clearly marked as
   descriptive and unpaired.
3. Whether the no-GT boundary is clear enough to prevent oracle leakage
   concerns.
4. Whether the RSR gain should be softened because its CI lower bound is 0.00 pp.
5. Whether the failure taxonomy supports the discussion, or needs more examples.
6. Whether the remaining hard-scene performance is too low for the claimed
   contribution, and how to frame that limitation.
7. Whether any missing baseline, ablation, or real-robot evidence is likely to
   block RA-L acceptance.

Preferred output from reviewers: list blocking issues first, then minor writing
edits, then suggested table/figure changes.
