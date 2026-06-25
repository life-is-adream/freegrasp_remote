# EGHC-v1 Historical Run Audit

Date: 2026-06-26

## Pre-Paid Gate Status

All local pre-paid gates passed.

No paid reasoning experiment has been launched.

Separate user approval is required for:
- MiMo preflight
- Qwen preflight
- Phase B smoke
- Phase C split-0 pilot

## Test Results

### EGHC Focused Test Suite
- test_eghc_historical_audit: 3/3 PASS
- test_eghc_gt_isolation: 3/3 PASS
- test_eghc_evidence_builder: 2/2 PASS
- test_eghc_router: 4/4 PASS
- test_eghc_adjudicator: 3/3 PASS
- test_eghc_segmentation: 4/4 PASS
- test_eghc_artifacts: 2/2 PASS
- test_eghc_challenger: 3/3 PASS
- **Total: 24/24 PASS**

### Regression Suite
- test_scene_router: 20/20 PASS
- test_evaluate_all_summary: PASS
- test_evaluate_mimo: PASS
- **Total: 56 tests PASS**

## Frozen Artifacts

- `data/output/eghc_v1/frozen_policy.json` - Frozen policy configuration
- `data/output/eghc_v1/historical_run_registry.json` - Historical run provenance
- `data/output/eghc_v1/clean_s0_manifest.json` - Clean S0 baseline
- `data/output/eghc_v1/offline_router_audit.json` - Router decision audit
- `data/output/eghc_v1/offline_segmentation_audit.json` - Segmentation audit

## Implementation Summary

### New Modules Created
- `utils/gt_access_guard.py` - GT field scanner and runtime guard
- `utils/deployable_evidence.py` - No-GT evidence packet builder
- `utils/eghc_schemas.py` - Dataclasses for Call 1, Call 2, Route Decision, Sealed Prediction
- `utils/eghc_router.py` - Deterministic guard router with route state machine
- `utils/eghc_adjudicator.py` - Conditional Qwen trigger policy
- `utils/eghc_segmentation.py` - No-GT mask repair and ranked-candidate fallback
- `utils/eghc_artifacts.py` - Sealed prediction artifacts and scorer handoff
- `audit_historical_runs.py` - Historical run provenance audit
- `audit_eghc_offline.py` - Fixed-cache offline audit
- `train_eghc_challenger.py` - Scene-disjoint challenger eligibility

### Modified Entry Points
- `utils/utils.py` - Added `evidence_gated_cascade` routing variant
- `evaluate_all.py` - Added `eghc_guard_only_v1` subset policy
- `evaluate_mimo.py` - Added `eghc_guard_only_v1` to CLI choices
- `evaluate_mimo_full_protocol.py` - Added `eghc_guard_only_v1` to CLI choices

## Next Steps (Requires User Approval)

1. **MiMo Preflight**: Verify MiMo can accept image inputs
2. **Qwen Preflight**: Verify Qwen adjudication works
3. **Phase B Smoke**: Run hard-only smoke on split 0
4. **Phase C Split-0 Pilot**: Run full split 0 with eghc_guard_only_v1
