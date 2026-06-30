# RA-L External Review Triage

Date: 2026-06-30

## Review Inputs

- Gemini-style review: methodological and presentation critique supplied in chat on 2026-06-30.
- Qwen3.7max review: `/home/wyl/.codex/attachments/1af46daf-463a-4ed1-bd91-5cd55d069316/pasted-text.txt`.

## Blocking and Near-Blocking Risks

| Risk | Severity | Source | Why it matters | Resolution |
|---|---|---|---|---|
| Call-count confound | Blocking | Gemini + Qwen | EGHC uses 1889 reasoning calls over 900 samples while S0 uses 900; reviewers may attribute gains to more inference budget. | Run S0 budget-control split-0 and add call-budget table. |
| RSR marginality | Blocking | Gemini + Qwen | +3.00 pp RSR has 95% CI [0.00, 5.95]. | Lead with SSR; describe RSR as positive but cautious. |
| Mask repair reproducibility | Near-blocking reproducibility risk | Gemini + Qwen | Equation uses lambda weights without values. | Replace or ground equation in actual implementation and report parameters. |

## Major Risks

| Risk | Resolution |
|---|---|
| Missing component ablation | Run single-split EGHC component ablations after the S0 budget-control run, or in parallel if time allows. |
| Missing Discussion | Add a 200-300 word Discussion subsection before Conclusion. |
| S0 underspecified | Add exact S0 policy details and manifest facts. |
| candidate false negatives and lexical blocker evidence | Add limitation and future-work text. |

## Deferred Items

| Item | Reason |
|---|---|
| Full real-robot validation | Larger study outside current RA-L revision pass; acknowledge benchmark-only boundary. |
| Qwen3.7-plus/max mainline | Would change the story and introduce new inference-path verification risk. |

## Execution Order

1. Call-budget accounting and S0 budget-control split-0 run.
2. Manuscript claim softening and reproducibility fixes that do not depend on new results.
3. Component ablations after the S0 budget-control split-0 run, or in parallel if time allows.
4. Final LaTeX compile and external-review handoff.
