# FreeGrasp experiment publication manifest

This branch publishes recent B1 method code, protocol documents, and lightweight
results for review and reproducibility. It is based on the remote
`experiment/routing-v2` branch and is intentionally separate from the frozen
checkout.

## Included

- `b1_route_correction_20261002_v1`: selective route-correction implementation,
  frozen protocol, reachability/plan metadata, score, and the completed
  exploratory report.
- `b1_v6_failure_audit_20261002`: failure-attribution report, paired audit
  table, controls, and the derived audit summary.
- `b1_v6_repair_20261002`: repair policy, execution wrapper, backend, tests,
  contract, and offline validation manifests.
- `b1_adaptive_20260930_v5`: frozen protocol/method scripts, replay score,
  preparation metadata, and the paid-batch seal. The paid batch is explicitly
  recorded as stopped at 27/72 cases and is not presented as a result.
- The current selective-routing design and handoff document.

## Evidence boundary

The route-correction result is split0 exploratory evidence: 300 exposed cases,
not an unseen full-900 confirmation. Its report records `not_demonstrated` for
the primary SSR improvement (+0.33 percentage points; bootstrap CI crosses 0).
The v5 paid batch is incomplete because of an API transport timeout.

## Deliberate exclusions

Raw images, masks, mask caches, replay payloads, API responses, Python cache
files, and credentials are not committed. They remain on the experiment
server under the recorded artifact roots. The frozen repository itself is not
modified by this publication.
