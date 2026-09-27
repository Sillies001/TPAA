# SDIB-1.2 Change Note

- Parent: SDIB-1.1
- Date: 2026-09-27
- Nature: post-M2 task-level implementation refinement for M3; no Canonical/business semantic change.
- Entry evidence: M2 protected-main Exit GO at `9ed7754fdc5362cd3ea3896a65fc0f5a597c6381`, Run #338 / Actions run `36302102143`.
- M3 is refined from Epic level to 28 implementation Tasks across WS-WORLD, WS-METRIC, WS-OBSERVATION, WS-API, WS-GUI and WS-TEST.
- The 28 Tasks are grouped into four coarse execution batches under the #85 governance policy.
- The frozen M3 Metric delivery set remains exactly `P1_REMAINDER_84`: 84 Catalog metrics with `delivery_milestone=M3` and `delivery_batch=P1_REMAINDER_84`.
- M3 integrates the already-qualified 32 foundation metrics with the 84 remainder metrics for exactly 116 executable P1 metrics.
- Frozen Stage profiles remain BASIC_FLIGHT_V1, WVR_ENGAGEMENT_V1, BVR_KILL_CHAIN_V1 and STRIKE_MISSION_V1; no alternate Stage schema is introduced.
- Family applicability remains Catalog-owned: AIR subject type; TRK/ID product capabilities; PSV IRST/EO; ESM RWR/ESM; DL DATALINK; FUS FUSION.
- M3 publication/API/GUI must preserve immutable Release/historical/replay contracts and may not recompute business metrics in transport or presentation layers.
- M3 Exit requires exact-head Hosted CI plus protected-main evidence, Windows/Linux logical equivalence, SQLite/PostgreSQL logical Release parity, Golden/replay/API/GUI/cold-start evidence and an exact 28/28 task review.
- Added `M3_TASK_BASELINE.json` as the machine-readable mirror of the M3 Task/batch baseline.
- R3.3, CB-1.4.0, the 116 P1 metrics, 661 input bindings, Stage/DTO/Core schema business authority and DB schema 1.6.0 are unchanged.
- M4 remains gated and at Epic/Entry-Gate level until M3 Exit GO.
