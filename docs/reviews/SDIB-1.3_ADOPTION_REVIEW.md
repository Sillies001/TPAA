# SDIB-1.3 Adoption / M4 Refinement Review

## Review identity
- **Change class:** C1 — post-M3 backlog refinement.
- **Adopted baseline:** SDIB-1.3; parent SDIB-1.2.
- **Tracking issue:** #121 (completed); program policy #120; semantic blocker/authority closure #122.
- **Core baseline / DB schema:** CB-1.4.0 / 1.6.0.
- **Document SHA-256:** `cf17b1ce7af3b80d81d40fd42d5d0967dda451043bfc1ae24b27662b6cbd098a`.
- **M4 manifest SHA-256:** `31b9450bb3fc9950146e798ad7b4dcbc18ef9332c86327212cca81bacd9e9ef5`.

## Entry evidence
M3 protected-main SHA `53c591adbab1dea0618d0d3a727b0bf4638e00de`, Run #414 / `36380613937` is PASS and `TPAA_M3_EXIT_REVIEW_V1 decision=GO`, 28/28 M3 tasks, 116/116 executable P1 metrics, `failed_acceptance=[]`.

## Adopted refinement
SDIB-1.3 freezes 21 M4 Tasks: GOVERNANCE 2, LONGITUDINAL 5, OBSERVATION 3, API 2, GUI 3, TEST 6; exactly four coarse batches. M4 remains P1-only with exact 104 eligible NUMERIC/MEDIAN longitudinal metrics and exact 12 excluded metrics.

## Protected-main adoption
- PR #123 exact candidate head: `0e1e2a62ab4f93f3098a822bb3b11e8c91dea533`
- candidate Run #415 / `36389239037`: PASS, 12/12 jobs
- actual merge/protected-main SHA: `bf8d7e8a2dae94ea78f3a7f6f859ccb391dd70d8`
- push-main Run #416 / `36392479151`: PASS, 12/12 jobs
- Issue #121: completed

**Adoption decision: ADOPTED.**

## C3 boundary
SDIB-1.3 intentionally did not invent exact trend-profile/comparison-key/DTO semantics. C3 #122 remains fail-closed until its dedicated controlled machine authority is adopted on protected main. Batch 1 tasks affected by #122 may not consume candidate semantics before that adoption.
