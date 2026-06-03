# AGENT.md

This file gives coding agents working in this folder practical project guidance.
Follow the repository README for user-facing setup details, and use these notes for
day-to-day edits, tests, and experiment safety.

## Project Overview

FreeGrasp is a research codebase for free-form language-based robotic reasoning
and grasping. The top-level scripts run synthetic dataset evaluation, real-world
demo/pipeline code, and metric tests.

Important top-level files:

- `evaluate_all.py`: runs all six synthetic evaluation subsets and writes a
  timestamped summary under `data/output/`.
- `evaluate1.py` ... `evaluate6.py`: small entrypoints for individual subsets.
- `evaluate_common.py`: shared dataset loading, Molmo preprocessing, reasoning,
  segmentation, and metric orchestration.
- `molmo_eval.py`: Molmo object-point detection and labeled-image generation.
- `reasoning_eval.py`: Qwen/GPT-style reasoning plus segmentation evaluation.
- `calculate_SR.py` and `rsr_metrics.py`: SSR/RSR metric calculation.
- `test_evaluate_entrypoints.py`, `test_rsr_metrics.py`: lightweight regression
  tests for subset wiring and reasoning metrics.
- `models/FGC_graspnet/`: grasp model, training/test scripts, pointnet2/knn CUDA
  extensions, and generated grasp utilities.
- `models/langsam/`: LangSAM, SAM, and GroundingDINO integration.
- `models/graspnetAPI/`: GraspNet API vendored/installed code.

## Environment And Dependencies

- Expected environment from README: Python 3.10, PyTorch 2.4.1, torchvision
  0.19.1, CUDA 12.4.
- Full pipeline work is GPU-heavy. Synthetic reasoning needs roughly 18 GB GPU
  memory; complete real-world pipeline may need 24 GB.
- GraspNet dependencies include compiled `pointnet2` and `knn` extensions under
  `models/FGC_graspnet/`.
- LangSAM/GroundingDINO and GraspNetAPI have their own dependency constraints.
  Keep dependency edits localized and document any version changes clearly.

## Data And Outputs

Expected synthetic data layout:

```text
data/
  npz_file/
  train-00000-of-00002.parquet
  train-00001-of-00002.parquet
```

Runtime outputs are written under `data/output/`.

- `data/output/molmo_output/` is the Molmo cache used by downstream reasoning.
- `evaluate_all.py` currently clears `data/output/molmo_output/` before running
  all subsets, which forces Molmo to re-process every scene.
- Individual subset entrypoints call `evaluate_subset()` and can reuse existing
  Molmo scene folders when present.
- Do not delete generated data, model checkpoints, or output directories unless
  the user explicitly asks.

## Evaluation Entrypoints

The subset mapping is intentionally tested. Preserve it unless the user asks for
a behavior change:

- `evaluate1.py` -> `easy_no_ambi`
- `evaluate2.py` -> `easy_yes_ambi`
- `evaluate3.py` -> `medium_no_ambi`
- `evaluate4.py` -> `medium_yes_ambi`
- `evaluate5.py` -> `hard_no_ambi`
- `evaluate6.py` -> `hard_yes_ambi`

`evaluate_all.py` should list those six subsets in the same order.

## API And Cost Safety

- Qwen/DashScope and OpenAI-style calls can cost money. Do not run
  `test_qwen_api.py`, `reasoning_eval.py`, `evaluate.py`, `evaluate_all.py`, or
  full pipeline scripts just to verify small code edits.
- Prefer environment variables for API keys. Do not add new hardcoded secrets,
  print keys, or include credentials in logs, docs, tests, or commits.
- If a change may trigger paid inference or large Molmo reruns, tell the user
  before running it and explain what will be executed.
- Preserve cached Molmo outputs when possible. Reusing `data/output/molmo_output`
  helps avoid repeated GPU/model work.

## Testing Guidance

Use lightweight tests first:

```bash
python -m unittest test_evaluate_entrypoints.py test_rsr_metrics.py
```

Run narrower tests for focused changes:

```bash
python -m unittest test_rsr_metrics.py
python -m unittest test_evaluate_entrypoints.py
```

Only run full evaluation scripts when the user requests experiment execution or
when the change specifically requires end-to-end validation.

## Coding Guidelines

- Keep changes scoped. This is research code with heavy dependencies, so avoid
  broad refactors while fixing a narrow issue.
- Prefer shared helpers in `evaluate_common.py` for evaluation orchestration
  instead of duplicating logic across `evaluate*.py`.
- When changing RSR/SSR behavior, update or add tests near `test_rsr_metrics.py`.
- When changing subset entrypoints or subset names, update
  `test_evaluate_entrypoints.py`.
- Use explicit paths relative to the project root for data and outputs, matching
  the existing scripts.
- Be careful with ID conventions: dataset object IDs can be zero-based while
  Molmo/object labels are often one-based.
- Avoid introducing network calls, dataset downloads, checkpoint downloads, or
  model loading during import-time tests.

## Review Checklist

Before finishing work in this folder:

- Confirm whether the edit touches lightweight code, GPU-heavy inference, or
  paid API behavior.
- Run the relevant lightweight unittest command when possible.
- Note any tests not run because data, GPU, compiled extensions, or API keys are
  unavailable.
- Mention any changed output/cache behavior, especially anything involving
  `data/output/molmo_output/`.
