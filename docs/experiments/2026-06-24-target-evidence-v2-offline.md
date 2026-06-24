# Target Evidence V2 Offline Audit

## Command

```bash
CUDA_VISIBLE_DEVICES=0 .venv/bin/python audit_target_evidence_v2.py --pilot-manifest data/output/overlap_blocker_pilot_v1_artifacts/pilot_manifest.json --pilot-source-run data/output/conservative_router_pilot_v1_20260624 --full-source-run data/output/ablation_matrix/S4 --molmo-root data/output/molmo_output --output-dir data/output/target_evidence_v2_offline_20260624 --report docs/experiments/2026-06-24-target-evidence-v2-offline.md
```

## Provenance

- Molmo cache SHA-256: `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed`
- Paid inference: none
- Geometry source: point-prompted SAM masks

## Pilot Recall

- Target accuracy: 24/25
- Top-1 blocker recall: 10/25
- Top-3 blocker recall: 14/25
- Medium top-3 recall: 13/17
- Hard top-3 recall: 1/8
- Samples with duplicate-mask warnings: 0
- Samples using nearest fallback: 0

## Full S4 Coverage

- Rows: 900
- Unique samples: 900
- Samples with risk candidates: 897
- Samples with duplicate masks: 7
- Route transitions: `{"blocker_first->blocker_first": 30, "blocker_first->target_first": 2, "direct->target_first": 601, "target_first->target_first": 267}`

## Gate

- Passed: `false`
- exact_25_unique: `true`
- target_24_of_25: `true`
- top3_17_of_25: `false`
- hard_4_of_8: `false`

## Interpretation

This audit measures only whether predicted evidence contains acceptable first-grasp candidates. It does not estimate new RSR or SSR.

## Next Action

Stop RGB-only development and design depth-aware occlusion.
