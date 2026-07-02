# GroundingDINO Compatibility Patch

Date: 2026-07-03

The FreeGrasp checkout tracks `models/langsam/GroundingDINO` as a gitlink to
the upstream GroundingDINO repository at commit `856dde2`. Local compatibility
edits inside that nested repository cannot be committed safely by the parent
repository unless the nested commit is also pushed to an accessible remote.

To keep the parent repository reproducible without pointing at an unpushed
private nested commit, the local edits are stored as:

`patches/groundingdino-freegrasp-compat.patch`

## What The Patch Does

1. Makes `BertModelWarper.get_extended_attention_mask` compatible with newer
   Transformers signatures that use `dtype` instead of the older positional
   `device` argument.
2. Adds a fallback `get_head_mask` implementation when the wrapped BERT model
   does not expose one.
3. Sets `_C = None` when GroundingDINO custom C++ ops fail to import, then uses
   the custom multi-scale deformable attention op only when `_C` exists and the
   value tensor is on CUDA.

These changes address local LangSAM/GroundingDINO import and CPU-fallback
compatibility failures observed during FreeGrasp real-world demo and ablation
work.

## Apply Command

From the parent repository root:

```bash
cd models/langsam/GroundingDINO
git apply ../../../patches/groundingdino-freegrasp-compat.patch
```

## Cleanup Command

If the nested repository becomes dirty and you want to return to the tracked
upstream commit:

```bash
git -C models/langsam/GroundingDINO reset --hard
```

Do not update the parent gitlink to a local-only GroundingDINO commit unless
that nested commit is also pushed to a remote that collaborators can fetch.
