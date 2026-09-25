# SDIB-1.1 Change Note

- Parent: SDIB-1.0.1
- Date: 2026-09-25
- Nature: post-M1 task-level implementation refinement for M2; no Canonical/business semantic change.
- Entry evidence: M1 protected-main Exit GO at `e96358c1060aa176d784bbaa291c999b7a859a7d`, Run #172 / Actions run `36097766180`.
- M2 is refined from Epic level to 27 implementation Tasks across WS-DATA, WS-WORLD, WS-METRIC, WS-OBSERVATION, WS-GUI and WS-TEST.
- The 27 Tasks are grouped into four coarse execution batches under the #85 governance policy.
- The frozen M2 Metric delivery set remains exactly `P1_FOUNDATION_32`: 32 Catalog metrics with `delivery_milestone=M2` and `delivery_batch=P1_FOUNDATION_32`.
- M1 early implementations of `P1-AIR-001/002/003` are reusable but do not by themselves satisfy M2 formal delivery acceptance.
- SNS family applicability remains RADAR-only per the frozen family applicability contract; this revision does not broaden SNS to IRST/EO.
- M2 publication must preserve frozen publication routes/observation lanes and existing immutable Release/historical/replay contracts.
- M2 Exit requires exact-head Hosted CI plus protected-main evidence, Windows/Linux logical equivalence, SQLite/PostgreSQL logical Release parity, Golden/replay/cold-start evidence and an exact 27/27 task review.
- Added `M2_TASK_BASELINE.json` as the machine-readable mirror of the M2 Task/batch baseline.
- R3.3, CB-1.4.0, the 116 P1 metrics, 661 input bindings, Stage authority, DTO authority and DB schema 1.6.0 are unchanged.
- M3 remains gated and at Epic/Entry-Gate level until M2 Exit GO.
