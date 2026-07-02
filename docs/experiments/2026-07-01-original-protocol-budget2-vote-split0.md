# Original Protocol Budget-2 Vote Split-0 Audit

Date: 2026-07-01

## Hypothesis

If EGHC3_v3 mainly benefits from giving the VLM more reasoning budget, then a
controlled original-protocol run that asks MiMo-v2.5 twice and votes between
the two outputs should improve over the single-call S0 original protocol on the
same split-0 samples.

This audit tests that narrow hypothesis only. It is not a new proposed method.

## Command

```bash
RUN_ROOT=data/output/ablation_matrix/original_protocol_budget2_vote_split0

setsid bash -c '
  set -o pipefail
  RUN_ROOT="data/output/ablation_matrix/original_protocol_budget2_vote_split0"
  date -Is > "$RUN_ROOT/started_at.txt"
  DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-unused-by-evaluate-mimo}" PYTHONUNBUFFERED=1 .venv/bin/python -u evaluate_mimo_full_protocol.py \
    --model-name mimo-v2.5 \
    --max-output-tokens 713 \
    --subset-policy original_protocol_budget2_vote \
    --splits 0 \
    --run-root "$RUN_ROOT" \
    --expected-cache-sha256 705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed \
    --reuse-molmo \
    --resume
  code=$?
  printf "EXIT_CODE=%s\n" "$code" > "$RUN_ROOT/exit_code.txt"
  date -Is > "$RUN_ROOT/ended_at.txt"
  exit "$code"
' > "$RUN_ROOT/run.log" 2>&1 &
```

## Configuration

| Field | Value |
|---|---|
| Run directory | `data/output/ablation_matrix/original_protocol_budget2_vote_split0` |
| Entry point | `evaluate_mimo_full_protocol.py` |
| Model | `mimo-v2.5` |
| Split | `0` |
| Samples | 300 |
| Molmo cache policy | reuse existing |
| Molmo cache SHA-256 | `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed` |
| Prompt/protocol | original FreeGrasp protocol, legacy old |
| Retry/vote mode | `budget2_vote` |
| Routing | none |
| Feature source | none |
| Segmentation | baseline |
| GT features | false |
| Benchmark difficulty label | false |
| Max output tokens | 713 |
| Final exit code | `EXIT_CODE=0` |
| Final run window | 2026-07-01T00:07:19+08:00 to 2026-07-01T00:59:30+08:00 |

## Run Integrity

Two partial starts were explicitly excluded from the final active outputs:

| Backup directory | Rows | Reason |
|---|---:|---|
| `failed_before_ms_deform_attn_compat_fix_20260630_235607` | 8 | LangSAM/GroundingDINO compatibility failure before the `_C` fallback fix |
| `failed_before_reasoning_metadata_fix_20260701_000032` | 12 | success path returned undefined `reasoning_metadata` before the return-value fix |

The final active split output contains 300 rows and zero program-level errors.
The failed partial rows are retained only as debugging provenance and must not
be treated as evaluation samples.

## Result

| Subset | N | RSR | SSR |
|---|---:|---:|---:|
| Easy, no ambiguity | 50 | 84.00% | 70.00% |
| Easy, ambiguity | 50 | 78.00% | 66.00% |
| Medium, no ambiguity | 50 | 60.00% | 50.00% |
| Medium, ambiguity | 50 | 54.00% | 46.00% |
| Hard, no ambiguity | 50 | 28.00% | 24.00% |
| Hard, ambiguity | 50 | 36.00% | 22.00% |
| **Overall** | **300** | **56.67%** | **46.33%** |

Call budget:

| Metric | Value |
|---|---:|
| Reasoning calls | 600 |
| Router calls | 0 |
| Repair calls | 0 |
| Calls per sample | 2.00 |

Artifacts:

- `data/output/ablation_matrix/original_protocol_budget2_vote_split0/full_protocol_summary.json`
- `data/output/ablation_matrix/original_protocol_budget2_vote_split0/run_manifest.json`
- `data/output/ablation_matrix/original_protocol_budget2_vote_split0/run.log`
- `data/output/ablation_matrix/original_protocol_budget2_vote_split0/split_0/details_*.json`

## Split-0 Method Comparison

All rows below use the same split-0 300-sample subset and the same Molmo cache.
The published paper baseline is intentionally omitted because row-level
predictions are unavailable for paired split-0 comparison.

| Method | Role | Routing | Segmentation | Calls/sample | RSR | SSR | Delta vs S0 RSR | Delta vs S0 SSR |
|---|---|---|---|---:|---:|---:|---:|---:|
| S0 original protocol + MiMo-v2.5 | controlled baseline | none | baseline | 1.00 | 58.33% | 47.67% | 0.00 pp | 0.00 pp |
| Original protocol + budget-2 vote | reasoning-budget ablation | none | baseline | 2.00 | 56.67% | 46.33% | -1.67 pp | -1.33 pp |
| EGHC3_v3 main | proposed deployable method | evidence-gated cascade | EGHC mask repair | 2.10 | 61.00% | 56.00% | +2.67 pp | +8.33 pp |
| S1 oracle v10 | oracle diagnostic | oracle/difficulty-assisted | repair path | 1.34 | 69.00% | 62.67% | +10.67 pp | +15.00 pp |

Direct comparison against the budget-2 vote ablation:

| Comparison | RSR delta | SSR delta | Interpretation |
|---|---:|---:|---|
| Budget-2 vote - S0 | -1.67 pp | -1.33 pp | Extra original-protocol reasoning does not improve split-0 performance |
| EGHC3_v3 - budget-2 vote | +4.33 pp | +9.67 pp | EGHC gains are not explained by simply doubling VLM calls |
| S1 oracle - EGHC3_v3 | +8.00 pp | +6.67 pp | Oracle evidence still provides headroom, especially beyond deployable routing |

## Interpretation

The budget-2 vote result rejects the narrow hypothesis that EGHC3_v3's split-0
gain is mainly a consequence of asking the VLM twice. Under the original
FreeGrasp decision contract, doubling the reasoning call budget slightly
reduces both RSR and SSR relative to S0.

This supports the manuscript argument that the useful change is the decision
contract: EGHC separates target resolution, blocker assessment, route-specific
planning, and mask repair. More VLM sampling alone does not repair hard-scene
visibility failures or segmentation-instance ambiguity.

The budget-2 result should therefore be used as a negative ablation or appendix
diagnostic, not as a candidate main method.

## Next

1. Add a compact appendix or ablation paragraph: "Increasing original-protocol
   reasoning budget from one to two calls did not improve split-0 performance."
2. Use the comparison table to defend that EGHC is not merely a multi-call
   prompt-budget effect.
3. Keep EGHC3_v3 frozen as the main RA-L method.
4. Do not spend more API quota on budget-only original-protocol variants unless
   a reviewer specifically requests a repeated-seed robustness check.
