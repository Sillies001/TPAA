# SDIB-1.3 Change Note

- Parent: SDIB-1.2
- Date: 2026-09-28
- Nature: post-M3 task-level implementation refinement for M4; no Canonical/business semantic change in this C1 revision.
- Entry evidence: M3 protected-main Exit GO at `53c591adbab1dea0618d0d3a727b0bf4638e00de`, Run #414 / Actions run `36380613937`.
- M4 is refined to 21 Tasks across WS-LONGITUDINAL, WS-OBSERVATION, WS-GUI, WS-API, WS-TEST and WS-GOVERNANCE, grouped into four batches under #120.
- Catalog longitudinal membership is exact 104 eligible NUMERIC/MEDIAN + 12 excluded.
- Existing DB schema 1.6.0 longitudinal/debrief tables are reused; no shadow schema.
- Historical semantics remain Release-bound; current/latest fallback forbidden.
- M4 remains P1-only; no P4/P5 assessment and no M5 qualification claim.
- Missing exact trend-profile/canonicalization and longitudinal/debrief DTO semantics are not invented here; C3 #122 / M4-GOV-001 is a hard dependency.
- M4 Exit requires exact 21/21 evidence, 104/12 qualification, cross-platform/storage parity, history/replay/API/GUI/debrief/cold-start and protected-main GO.
