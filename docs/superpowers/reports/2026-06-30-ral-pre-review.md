# RA-L Pre-Review: EGHC3 Draft

Date: 2026-06-30

## Overall Assessment

Provisional recommendation: revise before submission, but the paper now has a
coherent mainline. The strongest contribution is not a larger model result. It
is the deployable decision contract: target resolution, blocker assessment,
route consensus, and mask repair are separated and audited under a fixed
900-sample protocol.

## Major Strengths

1. The main method is now cleanly separated from oracle diagnostics.
2. The controlled S0 comparison uses the same 900 samples and reused Molmo cache.
3. The SSR gain is meaningful and statistically supported by scene-clustered
   paired bootstrap.
4. The failure taxonomy gives the discussion a concrete explanation: easy
   failures are mask/instance issues, while medium/hard failures are
   blocker/visibility issues.
5. The S1 oracle table is useful because it quantifies headroom without being
   claimed as deployable performance.

## Blocking Or Near-Blocking Risks

1. The original FreeGrasp GPT-4o row is not paired with EGHC. The manuscript must
   keep this comparison descriptive unless row-level original predictions are
   recovered.
2. The RSR gain over S0 is modest. The CI lower bound reaches 0.00 pp, so the
   safest phrasing is that EGHC improves SSR robustly and improves RSR
   directionally under the controlled run.
3. Absolute hard-scene performance remains low: 32.00-34.00% RSR. The discussion
   should frame hard-scene blocker visibility as an open bottleneck, not a solved
   capability.
4. Reviewers may ask whether added calls and routing complexity are worth the
   gain. The paper should state call counts and argue that the value is an
   auditable decision contract plus SSR improvement, not only raw RSR.
5. The real-robot implication must stay bounded. Current evidence is benchmark
   reasoning plus mask IoU, not execution success.

## Minor Revision Targets

1. Ensure all captions state whether a row is deployable, controlled, reported,
   or oracle.
2. Consider moving one or more unused result figures into the main paper if page
   space permits; otherwise keep tables as the primary evidence.
3. Keep method terminology stable: use EGHC / EGHC3_v3 / S0 / S1 consistently.
4. Avoid saying "significant" unless the text explicitly points to the bootstrap
   interval and metric.
5. Add examples only if space allows; the taxonomy table may be enough for RA-L.

## Reviewer Questions To Anticipate

1. Why does SSR improve more than RSR?
2. Is the improvement caused by routing, mask repair, or more calls?
3. What prevents EGHC from using hidden ground-truth difficulty information?
4. Why is hard-scene performance still low?
5. Would a stronger VLM replace the need for EGHC?
6. How expensive is EGHC compared with direct FreeGrasp?

## Recommended Response Strategy

Lead with the decision-contract contribution and the SSR gain. Treat RSR as a
secondary, bounded improvement. Use the oracle table to show that remaining
errors are not merely prompt failures; better visibility and blocker evidence
still matter. Keep Qwen3.7-plus out of the central story until the model path is
fully verified.
