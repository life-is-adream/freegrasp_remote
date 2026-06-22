# Two-Stage FreeGrasp Ablation Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide reproducible, approval-gated Stage 1 screening and Stage 2 confirmation for the RA-L method, with fixed caches, matched settings, provenance audits, and paper-ready summaries.

**Architecture:** Introduce immutable run manifests and a dry-run-first experiment registry. Extend aggregation with call/provenance audits and scene-clustered bootstrap intervals. Paid commands are generated but cannot run unless both `--execute` and `--confirm-paid-inference RUN_PAID_INFERENCE` are supplied.

**Tech Stack:** Python 3.10, JSON, SHA-256, pandas, NumPy, existing full-protocol evaluator, `unittest`.

---

## File Structure

- Create `experiment_manifest.py`: cache hashing, run contracts, and provenance validation.
- Create `run_ablation_matrix.py`: Stage 1/Stage 2 registry, dry-run command generation, explicit execution gate.
- Create `summarize_ablation_matrix.py`: coverage, paired metrics, bootstrap confidence intervals, call audit, and CSV/LaTeX export.
- Create `test_experiment_manifest.py`, `test_run_ablation_matrix.py`, and `test_summarize_ablation_matrix.py`.
- Modify `evaluate_mimo_full_protocol.py`: attach manifest IDs and call/provenance fields.

### Task 1: Immutable Cache and Run Manifest

**Files:**
- Create: `experiment_manifest.py`
- Create: `test_experiment_manifest.py`

- [ ] **Step 1: Write failing deterministic-hash tests**

Create two temporary Molmo cache directories with identical files in different
creation orders and assert equal SHA-256 manifests. Change one byte and assert
the hash changes.

- [ ] **Step 2: Verify missing-module failure**

Run: `.venv/bin/python -m unittest test_experiment_manifest -v`

Expected: `ModuleNotFoundError: No module named 'experiment_manifest'`.

- [ ] **Step 3: Implement deterministic directory hashing**

```python
def hash_directory(root):
    digest = hashlib.sha256()
    root = Path(root)
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()
```

- [ ] **Step 4: Implement the run contract**

Persist model, token limit, split list, subset list, prompt/policy, routing
variant, segmentation variant, feature source, cache hash, git commit, dirty
worktree flag, command, and UTC timestamp. Reject automatic runs with
`uses_gt_features=true` or `uses_benchmark_difficulty=true`.

- [ ] **Step 5: Run tests and commit**

Run: `.venv/bin/python -m unittest test_experiment_manifest -v`

Expected: all tests pass.

```bash
git add experiment_manifest.py test_experiment_manifest.py
git commit -m "feat: record immutable experiment manifests"
```

### Task 2: Dry-Run-First Ablation Registry

**Files:**
- Create: `run_ablation_matrix.py`
- Create: `test_run_ablation_matrix.py`

- [ ] **Step 1: Write failing registry tests**

Require Stage 1 IDs `S0` through `S7` and Stage 2 IDs `F0` through `F3`.
Require S1/F2 to be labeled `oracle_feature`; require S4/F1 to use
`predicted_geometry`; require F3 to call `replay_segmentation.py`.

- [ ] **Step 2: Verify failure**

Run: `.venv/bin/python -m unittest test_run_ablation_matrix -v`

Expected: missing-module failure.

- [ ] **Step 3: Implement typed experiment specifications**

```python
@dataclass(frozen=True)
class ExperimentSpec:
    run_id: str
    stage: int
    subset_policy: str
    routing_variant: str
    segmentation_variant: str
    feature_source: str
    max_output_tokens: int = 1024
    replay_source: str | None = None
```

Populate every accepted S/F configuration exactly as specified in the design
document.

- [ ] **Step 4: Implement the paid-execution gate**

Default behavior prints shell-escaped commands and writes no output directory.
Execution requires both flags:

```python
if args.execute and args.confirm_paid_inference != "RUN_PAID_INFERENCE":
    parser.error("--execute requires --confirm-paid-inference RUN_PAID_INFERENCE")
```

- [ ] **Step 5: Generate matched commands**

Reasoning experiments call `evaluate_mimo_full_protocol.py` with all three
splits, `--reuse-molmo`, a fixed cache hash, `mimo-v2.5`, and 1024 tokens.
Replay experiments call `replay_segmentation.py` and never request an API key.

- [ ] **Step 6: Run tests and commit**

Run: `.venv/bin/python -m unittest test_run_ablation_matrix -v`

Expected: dry run succeeds; incomplete execution confirmation exits nonzero.

```bash
git add run_ablation_matrix.py test_run_ablation_matrix.py
git commit -m "feat: define approval-gated ablation matrix"
```

### Task 3: Full-Protocol Manifest and Call Audit

**Files:**
- Modify: `evaluate_mimo_full_protocol.py:58-196`
- Modify: `test_evaluate_mimo_full_protocol.py`

- [ ] **Step 1: Write failing summary-audit tests**

Require summary fields `manifest_id`, `cache_sha256`, `feature_source`,
`routing_variant`, `uses_gt_features`, `uses_benchmark_difficulty`,
`reasoning_calls`, `router_calls`, `repair_calls`, and `calls_per_sample`.

- [ ] **Step 2: Verify failure**

Run: `.venv/bin/python -m unittest test_evaluate_mimo_full_protocol.EvaluateMimoFullProtocolTest.test_summary_records_provenance_and_calls -v`

Expected: missing-key failure.

- [ ] **Step 3: Aggregate call metadata from details files**

Count `len(reasoning.raw_outputs)`, `router_call_count`, and `retry_count` for
every completed detail row. Fail summary generation when any subset has fewer
than 150 rows in a requested three-split full run.

- [ ] **Step 4: Write `run_manifest.json` before inference**

Use `O_EXCL` semantics or refuse to overwrite a manifest whose cache hash or
configuration differs. Resume is allowed only when the existing manifest
matches exactly.

- [ ] **Step 5: Run tests and commit**

Run: `.venv/bin/python -m unittest test_evaluate_mimo_full_protocol -v`

Expected: all manifest, resume, fresh-cache, and aggregation tests pass.

```bash
git add evaluate_mimo_full_protocol.py test_evaluate_mimo_full_protocol.py
git commit -m "feat: audit full-protocol provenance and calls"
```

### Task 4: Paired Statistics and Failure Summary

**Files:**
- Create: `summarize_ablation_matrix.py`
- Create: `test_summarize_ablation_matrix.py`

- [ ] **Step 1: Write failing paired-summary tests**

Use synthetic rows with repeated scene IDs across three annotations. Assert
that resampling occurs by scene, not by row, and that mismatched scene keys are
reported instead of silently dropped.

- [ ] **Step 2: Verify failure**

Run: `.venv/bin/python -m unittest test_summarize_ablation_matrix -v`

Expected: missing-module failure.

- [ ] **Step 3: Implement scene-clustered bootstrap**

```python
def clustered_delta_ci(rows_a, rows_b, metric, seed=0, draws=10000):
    paired = pair_by_sample_key(rows_a, rows_b)
    scenes = sorted({row["scene_id"] for row in paired})
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(draws):
        sampled = rng.choice(scenes, size=len(scenes), replace=True)
        chosen = [row for scene in sampled for row in paired if row["scene_id"] == scene]
        deltas.append(np.mean([row[f"b_{metric}"] - row[f"a_{metric}"] for row in chosen]))
    return np.quantile(deltas, [0.025, 0.975]).tolist()
```

- [ ] **Step 4: Add required failure categories**

Aggregate target-resolution error, wrong blocker, routing error, RSR-only
segmentation error, same-class mask swap, no-mask failure, invalid ID, and API
error. Report invalid or incomplete rows separately.

- [ ] **Step 5: Run tests and commit**

Run: `.venv/bin/python -m unittest test_summarize_ablation_matrix -v`

Expected: all pairing, bootstrap, and failure-category tests pass.

```bash
git add summarize_ablation_matrix.py test_summarize_ablation_matrix.py
git commit -m "feat: summarize paired FreeGrasp ablations"
```

### Task 5: Paper-Ready CSV and LaTeX Export

**Files:**
- Modify: `summarize_ablation_matrix.py`
- Modify: `test_summarize_ablation_matrix.py`

- [ ] **Step 1: Write failing export tests**

Require fixed subset order, percentage precision to two decimals, `mean ± std`
for the three annotation splits, and labels `(reported)` for original-paper
GPT-4o values and `(oracle feature)` for S1/F2.

- [ ] **Step 2: Verify failure**

Run: `.venv/bin/python -m unittest test_summarize_ablation_matrix.AblationSummaryTest.test_latex_labels_reported_and_oracle_rows -v`

Expected: export function missing.

- [ ] **Step 3: Implement exports**

Write `main_results.csv`, `routing_ablation.csv`,
`reasoning_ablation.csv`, `segmentation_ablation.csv`, and corresponding
booktabs `.tex` fragments. Published GPT-4o values are constants copied from
the verified original paper and are never included in paired statistical tests.

- [ ] **Step 4: Run tests and commit**

Run: `.venv/bin/python -m unittest test_summarize_ablation_matrix -v`

Expected: all CSV and LaTeX snapshots pass.

```bash
git add summarize_ablation_matrix.py test_summarize_ablation_matrix.py
git commit -m "feat: export RA-L ablation tables"
```

### Task 6: Stage 1 Readiness Gate

**Files:**
- No file changes.

- [ ] **Step 1: Run all non-paid experiment tests**

Run: `.venv/bin/python -m unittest test_experiment_manifest test_run_ablation_matrix test_summarize_ablation_matrix test_evaluate_mimo_full_protocol -v`

Expected: all tests pass.

- [ ] **Step 2: Generate Stage 1 commands only**

Run: `.venv/bin/python run_ablation_matrix.py --stage 1 --dry-run`

Expected: commands S0-S7 are printed; no run directory is created and no API
request occurs.

- [ ] **Step 3: Audit the cache before requesting approval**

Run: `.venv/bin/python experiment_manifest.py hash-cache data/output/molmo_output`

Expected: one SHA-256 value and the number of cached scene image/ID pairs.

- [ ] **Step 4: Present cost estimate and wait for explicit approval**

Compute expected reasoning calls from 900 initial calls plus route and repair
calls for each selected configuration. Do not execute Stage 1 in this task.

### Task 7: Stage 2 Gate After Stage 1 Review

**Files:**
- No file changes.

- [ ] **Step 1: Validate Stage 1 coverage**

Run: `.venv/bin/python summarize_ablation_matrix.py validate --stage 1 --expected-n 900`

Expected: every retained reasoning run has 900 unique sample keys and matching
cache/token/model manifests.

- [ ] **Step 2: Select F1 from predeclared criteria**

F1 must maximize RSR while keeping its lower 95% clustered-bootstrap bound
above S0, minimizing oracle regret, and reporting calls per sample. Do not alter
selection criteria after viewing Stage 1 results.

- [ ] **Step 3: Generate Stage 2 commands only**

Run: `.venv/bin/python run_ablation_matrix.py --stage 2 --dry-run`

Expected: F0-F3 commands are printed; no API request occurs.

- [ ] **Step 4: Request separate approval for fresh Molmo and paid reasoning**

Do not execute F0-F3 until the user approves the exact cache policy, expected
MiMo call count, output directory, and environment.

