# Hard Blocker-First V10 Design

## Goal

Improve FreeGrasp hard-scene first-grasp selection while preserving all existing
prompt variants and subset policies as rollback hooks.

## Evidence

The v9 hard runs produced 21 direct-target decisions across two evaluations, and
all 21 failed RSR and SSR. Successful hard decisions came from blocker choices.
Unconditional geometry repair also doubled MiMo calls and could replace a valid
answer with a worse one.

## Design

Add a new prompt hook named `hard_blocker_first_v10_json` and a subset-policy
hook named `hard_blocker_first_v10`.

The policy keeps the existing v9 routing outside hard scenes:

- easy subsets: `direct_target` plus `id_repair`
- medium subsets: `target_first_evidence_gate_v9_json` plus
  `geometry_consistency_repair`
- hard subsets: `hard_blocker_first_v10_json` plus `id_repair`

The hard prompt uses the existing target-first JSON schema so current parsing,
mask selection, metadata, and ID repair remain compatible. In hard scenes it
must always set `should_grasp_target_directly` to false and choose one visible
direct blocker. Target localization is context for identifying that blocker,
not permission to return the target.

Blocker ranking is:

1. visible object physically covering or contacting the target region
2. visible object directly above/on top of the target with image support
3. overlap relation supported by the image

`near` alone is insufficient. Axis-aligned bbox relations and semantic labels
are weak hints, not proof. Same-category candidates must be separated by image
position, point ranks, bbox, center, and bottom-edge rank. The selected ID must
be visible and the mask query must remain a short noun phrase.

## Compatibility And Hooks

V10 is opt-in through CLI choices. V9 and all older policies remain unchanged.
The JSON schema stays parser-compatible. The hard policy uses only invalid-ID
repair, avoiding unconditional second MiMo calls.

## Verification

Use TDD for prompt registration, input formatting, CLI hooks, and policy
routing. Run the existing relevant unittest suite, inspect the diff for API,
cache, parser, and metric risks, then run 50 `hard_no_ambi` and 50
`hard_yes_ambi` scenes in the existing FreeGrasp environment with Molmo cache
reuse and Hugging Face offline mode.
