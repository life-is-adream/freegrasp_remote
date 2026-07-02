# EGHC Routing Ablation Split-0

Date: 2026-07-02

## Hypothesis

Routing-specific ablations should isolate whether EGHC3_v3's split-0 gain comes
from the evidence-gated routing/consensus contract rather than from extra model
calls or mask repair alone.

Two split-0 ablations are planned:

| Ablation | Changed component | Fixed components |
|---|---|---|
| `eghc_no_consensus_v1` | disables the EGHC consensus route guard | MiMo-v2.5, Molmo cache, evidence-gated cascade, mask repair |
| `eghc_consensus_no_blocker_first_v1` | disables blocker-first routing | MiMo-v2.5, Molmo cache, consensus guard, mask repair |

Both are component ablations only. They are not candidate main methods.

## Required Environment

These ablations still use the EGHC adjudication path when the evidence-gated
route assessment detects an invalid ID, blocker-first route, direct route with
blocking evidence, or low-confidence plan. Therefore a Qwen/DashScope key must
be present in the running process environment:

```bash
test -n "${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-}}" || {
  echo "Missing DASHSCOPE_API_KEY or QWEN_API_KEY"
  exit 1
}
```

Starting without the key produces environment failures that must not be counted
as model errors.

## Aborted Attempt

An initial `eghc_no_consensus_v1` launch was stopped because the current shell
did not contain `DASHSCOPE_API_KEY` or `QWEN_API_KEY`. The partial output was
moved to:

`data/output/ablation_matrix/eghc_no_consensus_v1_split0.failed_missing_qwen_key_20260702_101956`

Observed before stopping:

| Field | Value |
|---|---:|
| Completed active rows | 25 |
| RSR on partial rows | 80.00% |
| SSR on partial rows | 56.00% |
| Missing-key failures in log | 5 |

This run is invalid for analysis because several samples failed for environment
reasons rather than algorithmic reasons.

## Clean Launch Commands

Run these only after exporting a valid Qwen/DashScope key in the same shell.

### No-consensus guard

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
test -n "${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-}}" || {
  echo "Missing DASHSCOPE_API_KEY or QWEN_API_KEY"
  exit 1
}

run="data/output/ablation_matrix/eghc_no_consensus_v1_split0"
mkdir -p "$run"
setsid .venv/bin/python -u evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy eghc_no_consensus_v1 \
  --splits 0 \
  --reuse-molmo \
  --resume \
  --run-root "$run" \
  --skip-mimo-preflight \
  > "$run/nohup.log" 2>&1 < /dev/null &
```

### No-blocker-first route

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
test -n "${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-}}" || {
  echo "Missing DASHSCOPE_API_KEY or QWEN_API_KEY"
  exit 1
}

run="data/output/ablation_matrix/eghc_consensus_no_blocker_first_v1_split0"
mkdir -p "$run"
setsid .venv/bin/python -u evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy eghc_consensus_no_blocker_first_v1 \
  --splits 0 \
  --reuse-molmo \
  --resume \
  --run-root "$run" \
  --skip-mimo-preflight \
  > "$run/nohup.log" 2>&1 < /dev/null &
```

## Completion Check

```bash
run="data/output/ablation_matrix/eghc_no_consensus_v1_split0"
.venv/bin/python - <<'PY'
import json, glob, os
run = "data/output/ablation_matrix/eghc_no_consensus_v1_split0"
total = rsr = ssr = 0
for f in sorted(glob.glob(run + "/split_0/out_*.json")):
    arr = json.load(open(f))
    r = sum(1 for row in arr if len(row) > 4 and row[4] == 1)
    s = sum(1 for row in arr if len(row) > 3 and row[3] == 1)
    total += len(arr)
    rsr += r
    ssr += s
    print(os.path.basename(f), len(arr), f"RSR={r/len(arr)*100:.2f}%", f"SSR={s/len(arr)*100:.2f}%")
print("TOTAL", total, f"RSR={rsr/total*100:.2f}%" if total else "RSR=NA", f"SSR={ssr/total*100:.2f}%" if total else "SSR=NA")
PY
rg -n "Traceback|ERROR|failed:|requires DASHSCOPE|requires QWEN|Exception" "$run/nohup.log" || true
```

## Completed No-Consensus Result

The clean `eghc_no_consensus_v1` run completed after Qwen/DashScope credentials
were added to the process environment.

| Subset | N | RSR | SSR |
|---|---:|---:|---:|
| Easy, no ambiguity | 50 | 76.00% | 60.00% |
| Easy, ambiguity | 50 | 74.00% | 72.00% |
| Medium, no ambiguity | 50 | 64.00% | 66.00% |
| Medium, ambiguity | 50 | 70.00% | 72.00% |
| Hard, no ambiguity | 50 | 34.00% | 30.00% |
| Hard, ambiguity | 50 | 36.00% | 36.00% |
| **Overall** | **300** | **59.00%** | **56.00%** |

Call budget:

| Metric | Value |
|---|---:|
| Reasoning calls | 688 |
| Router calls | 300 |
| Repair calls | 7 |
| Reasoning calls/sample | 2.29 |
| Router calls/sample | 1.00 |
| Repair calls/sample | 0.02 |
| Total recorded calls/sample | 3.32 |

The log does not contain per-sample timestamps, so average wall-clock latency
cannot be reconstructed reliably from this artifact. The run should therefore
be reported as offline call-budget evidence rather than real-time latency
evidence.

## Interpretation

Removing the consensus route guard reduces split-0 RSR from 61.00% to 59.00%
while keeping SSR at 56.00%. This suggests that the consensus guard mostly
protects first-grasp ID selection rather than mask quality on split 0. The
ablation also increases reasoning calls/sample from 2.10 to 2.29 because more
plans require adjudication or repair when the conservative consensus guard is
removed.

## Next

1. Run `eghc_consensus_no_blocker_first_v1` if more routing-specific evidence is
   needed.
2. Add completed routing and call-budget rows to the manuscript's split-0
   ablation table.
