# RA-L External Review Triage

Date: 2026-06-30

## Review Inputs

- Gemini-style review: methodological and presentation critique supplied in chat on 2026-06-30.
- Qwen3.7max review: `/home/wyl/.codex/attachments/1af46daf-463a-4ed1-bd91-5cd55d069316/pasted-text.txt`.

## Blocking Risks

| Risk | Source | Why it matters | Resolution |
|---|---|---|---|
| Call-count confound | Gemini + Qwen | EGHC uses 1889 reasoning calls over 900 samples while S0 uses 900; reviewers may attribute gains to more inference budget. | Run S0 budget-control split-0 and add call-budget table. |
| RSR marginality | Gemini + Qwen | +3.00 pp RSR has 95% CI [0.00, 5.95]. | Lead with SSR; describe RSR as positive but cautious. |
| Mask repair reproducibility | Gemini + Qwen | Equation uses lambda weights without values. | Replace or ground equation in actual implementation and report parameters. |

## Major Risks

| Risk | Resolution |
|---|---|
| Missing component ablation | Run single-split EGHC ablations if P0 does not settle the main alternative explanation. |
| Missing Discussion | Add a 200-300 word Discussion subsection before Conclusion. |
| S0 underspecified | Add exact S0 policy details and manifest facts. |
| candidate false negatives and lexical blocker evidence | Add limitation and future-work text. |

## Deferred Items

| Item | Reason |
|---|---|
| Full real-robot validation | Larger study outside current RA-L revision pass; acknowledge benchmark-only boundary. |
| Qwen3.7-plus/max mainline | Would change the story and introduce new inference-path verification risk. |

## Execution Order

1. Call-budget accounting and P0 S0 budget-control split-0.
2. Manuscript claim softening and reproducibility fixes that do not depend on new results.
3. Component ablations if P0 leaves the call-budget objection unresolved.
4. Final LaTeX compile and external-review handoff.
