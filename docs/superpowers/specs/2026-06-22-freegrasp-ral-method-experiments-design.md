# FreeGrasp RA-L Method and Experiments Design

## Scope

This specification defines the Method, Experiments, and Ablation Study for a
FreeGrasp extension targeting IEEE Robotics and Automation Letters (RA-L). It
does not cover the Introduction, Related Work, or final manuscript prose.

The design extends FreeGrasp without modifying the original project directory.
Implementation and experiments must remain on the `freegrasp_codex` branch.

## Core Argument

The proposed system addresses two coupled failure modes in zero-shot,
language-conditioned bin picking: a single reasoning strategy does not fit all
scene complexities, and the object selected by reasoning can be inconsistent
with the instance mask returned by semantic segmentation. The method therefore
combines evidence-adaptive first-grasp reasoning with cross-stage geometric
consistency between the selected object point and its segmentation mask.

Existing results from
`freegrasp_codex_v10_full_20260618_165628` establish an oracle-routed reference
of 67.67% RSR and 60.33% SSR on 900 samples. They do not validate the automatic
router or the proposed mask consistency score. The run also derives semantic
labels and geometry from benchmark instance annotations, so it is an
oracle-feature upper bound and must not be presented as the final
automatic-system result.

## Terminology

| Canonical term | Definition and use |
| --- | --- |
| first-grasp object | The visible object that should be grasped at the current step |
| target object | The object requested by the language instruction |
| blocker evidence | Image-supported contact, coverage, on-top, or overlap evidence |
| evidence-adaptive routing | Automatic selection of a reasoning mode from predicted scene evidence |
| point-consistent mask | A candidate mask containing the Molmo point of the selected ID |
| RSR | Reasoning Success Rate |
| SSR | Segmentation Success Rate at IoU >= 0.5 |
| oracle routing | Routing based on benchmark difficulty labels |

Avoid using `point-guided segmentation` as a novelty claim. Original FreeGrasp
already uses Molmo points to select among same-class LangSAM masks. The new
contribution is a robust, auditable cross-stage consistency and recovery
mechanism.

## Contributions

### 1. Evidence-Adaptive First-Grasp Reasoning

The system automatically routes each observation to one of three structured
reasoning modes rather than reading the Easy, Medium, or Hard benchmark label:

- `direct`: resolve and return a visible, unobstructed target.
- `target-first`: resolve the target before deciding whether direct blocker
  evidence justifies a different first-grasp object.
- `blocker-first`: select one visible, immediately graspable direct blocker
  when the target is not visible or strong blocker evidence is present.

The routing decision combines clutter, ambiguity, and occlusion evidence.
Object count is a clutter prior, not a decisive difficulty label. A scene with
many objects can still use direct reasoning when its target is visible and
unobstructed. The deployable route uses geometry predicted from Molmo-point SAM
masks. A pure image-and-text VLM router is retained as an ablation.

### 2. Reasoning-Segmentation Geometric Consistency

The original first-containing-point rule is extended with multiple semantic
queries, explicit point consistency, candidate confidence, instance area, and
auditable fallback behavior. This component is evaluated with fixed reasoning
outputs so that segmentation gains cannot be attributed to a different object
decision.

## Method Design

### Task Formulation

Given an RGB image `I` and language instruction `q`, Molmo produces visible
candidates. Each Molmo point prompts SAM to produce a coarse candidate mask,
from which the system derives

`C = {(i, p_i, b_i, s_i)} for i = 1...N`,

where `i` is an object ID, `p_i` is a pointing coordinate, `b_i` is a predicted
candidate box, and `s_i` is an optional VLM-derived semantic label. The system
predicts the object ID `i*` to grasp now and an instance mask `M*` for that
object.

### Data Provenance Constraint

The automatic method may consume only the RGB image, language instruction,
Molmo IDs and points, model outputs, and masks or boxes predicted from those
inputs. `instances_objects`, `instances_semantic`, ground-truth object IDs, and
benchmark difficulty labels are prohibited from prompt construction, routing,
repair, and segmentation selection. They are used only after inference to
calculate RSR, IoU, and SSR. Any configuration that reads these annotations
during inference must be labeled `oracle_feature` in its metadata and tables.

### Evidence-Adaptive Scene Router

The router estimates scene complexity from three terms:

`D = alpha * D_clutter + beta * D_ambiguity + gamma * D_occlusion`.

- `D_clutter` uses the number of visible candidates. Suggested bins are fewer
  than 4, 4-5, and at least 6 visible objects.
- `D_ambiguity` measures target-resolution uncertainty and same-class instance
  ambiguity.
- `D_occlusion` measures direct blocker evidence derived from predicted masks
  and boxes. `near` alone is insufficient.

Routing follows these rules:

- A credible visible target with no blocker evidence uses `direct`.
- An uncertain target or weak/conflicting geometry uses `target-first`.
- A missing target ID or strong direct blocker evidence uses `blocker-first`.

Low router confidence defaults to `target-first`; it must not force a blocker.
Every routing decision records its evidence and confidence for error analysis.

### Scene-Conditioned First-Grasp Reasoning

All modes return one parser-compatible structured object containing:

- `target_resolution`
- `blocker_evidence`
- `first_grasp_decision`

The `target-first` path may invoke geometry consistency repair to check whether
the target ID, blocker ID, and spatial evidence agree. The `blocker-first` path
requires direct physical evidence and rejects nearby distractors. Invalid-ID
repair only restores output validity; it does not replace a valid decision.
When a repair returns an invalid ID, the system retains the initial valid
result.

### Reasoning-Segmentation Geometric Consistency

For a reasoning-selected ID `i*`, LangSAM produces masks from a sequence of
semantic queries derived from the model label, a simplified category phrase,
and the original instruction. Candidate selection follows the score

`score(M_k) = point(i*, M_k) + lambda_c * confidence(M_k) - lambda_a * area(M_k)`.

`point(i*, M_k)` is a dominant term indicating whether the candidate contains
`p_i*`. A point-consistent mask is preferred over a higher-confidence
point-inconsistent mask. When multiple masks contain the point, confidence and
normalized area resolve the instance. If no candidate contains the point, the
nearest usable candidate is returned with an explicit consistency-failure flag.
If no query yields a mask, the sample is reported as a segmentation failure.

### Inference Flow

`Molmo candidates -> automatic routing -> structured first-grasp reasoning ->`
`decision repair -> LangSAM candidates -> geometric consistency selection ->`
`final instance mask`.

## Experimental Design

### Dataset and Metrics

Use all six FreeGraspData strata with 150 samples each, for 900 samples total.
Report:

- overall and per-stratum RSR;
- overall and per-stratum SSR at IoU >= 0.5;
- mean and standard deviation over the three annotation splits;
- mean IoU and same-class mask-swap rate for segmentation ablations;
- API calls per sample, repair frequency, and inference latency;
- scene-clustered paired bootstrap confidence intervals.

### Baseline Hierarchy

1. `FreeGrasp + GPT-4o` from the original paper is the primary published
   baseline. Label these values as reported results, not same-environment
   reproduction.
2. `Original FreeGrasp protocol + MiMo-v2.5` is the controlled internal
   baseline for causal protocol ablations. It must cover 900 samples and match
   the proposed method's token limit, Molmo cache, and segmentation setting.
3. `Ours + MiMo-v2.5` is the principal proposed-system result.
4. Oracle-routed, oracle-feature v10 is an upper-bound diagnostic, not the
   deployed method.

The existing meaningful original-protocol MiMo run contains only 300 samples
and reports 56.33% RSR and 49.33% SSR. Zero-score MiMo and MiMo-pro runs are
invalid runs and must not be used as model-performance evidence.

If GPT-4o becomes available, run both the original and proposed protocols with
the same cache and token settings. Until then, comparisons between the proposed
MiMo system and published GPT-4o values are descriptive rather than controlled.

### Stage 1: Fixed-Cache Screening

Use one preserved Molmo cache and screen:

| ID | Configuration | Purpose |
| --- | --- | --- |
| S0 | Original protocol, matched MiMo settings | Controlled baseline |
| S1 | Oracle-routed, oracle-feature full protocol | Diagnostic upper bound |
| S2 | Count-only router | Isolate clutter prior |
| S3 | Pure VLM two-stage router | Test image-and-text routing without geometry |
| S4 | Predicted-geometry hybrid router | Test the proposed router |
| S5 | S4 without blocker-first | Isolate hard-scene reasoning |
| S6 | S4 without geometry repair | Isolate consistency repair |
| S7 | S4 without invalid-ID repair | Measure the format safety net |

Select the router with the highest RSR subject to a small oracle regret and an
acceptable number of additional model calls.

### Segmentation Replay Ablation

Freeze first-grasp IDs and replay segmentation:

| ID | Segmentation rule |
| --- | --- |
| G0 | Original first-containing-point selection |
| G1 | G0 plus multiple semantic query recovery |
| G2 | G1 plus explicit point-consistency filtering |
| G3 | G2 plus confidence and area consistency scoring |

RSR must remain identical across G0-G3. Compare SSR, mean IoU, same-class mask
swaps, and recovery success. Any RSR change indicates that reasoning was not
properly frozen and invalidates the replay comparison.

### Stage 2: Full Confirmation

Run only the retained designs on all 900 samples:

- F0: original protocol with MiMo-v2.5 and a fresh, preserved Molmo cache.
- F1: complete automatic method using the same cache and token settings.
- F2: oracle-routed, oracle-feature upper bound using the same cache.
- F3: fixed F1 reasoning replayed with G0 and G3.

An existing `fresh_once` run may be reused only after verifying that its exact
Molmo outputs are preserved and available to every compared configuration.

## Paper Presentation

- Table I: published GPT-4o baseline, controlled MiMo baseline, and proposed
  automatic method.
- Table II: count-only, pure VLM, predicted-geometry hybrid, and oracle routing.
- Table III: blocker-first, geometry repair, and invalid-ID repair ablations.
- Table IV: fixed-reasoning segmentation replay.
- Figure: representative direct-target, target-first, blocker-first, mask-swap,
  and recovered-mask cases.
- Failure analysis: target-resolution error, wrong blocker, routing error,
  same-class mask swap, and no-mask failure.

Other Qwen and MiMo-pro runs belong in supplementary model-sensitivity analysis
only after their protocol, cache, token limit, and sample coverage are matched.

## Claim Boundaries

- Do not claim that point-guided segmentation is newly introduced.
- Do not treat the existing oracle-routed v10 result as an automatic-system
  result.
- Do not use ground-truth instance masks, semantic maps, object IDs, or
  difficulty labels as automatic-method inputs.
- Do not attribute the v10 gain solely to prompting while token and cache
  settings differ.
- Do not describe published GPT-4o values as same-environment reproduction.
- Do not claim model-agnostic generalization without matched experiments on a
  second reasoning model.
- Do not claim real-robot improvement without new physical experiments.
