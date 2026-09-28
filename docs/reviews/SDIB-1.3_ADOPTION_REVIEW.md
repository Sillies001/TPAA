# SDIB-1.3 Adoption / M4 Refinement Review

## Review identity
- **Change class:** C1 — post-M3 backlog refinement.
- **Candidate:** SDIB-1.3; parent SDIB-1.2.
- **Tracking issue:** #121; program policy #120; semantic blocker C3 #122.
- **Core baseline / DB schema:** CB-1.4.0 / 1.6.0.
- **Document SHA-256:** `cf17b1ce7af3b80d81d40fd42d5d0967dda451043bfc1ae24b27662b6cbd098a`.
- **M4 manifest SHA-256:** `31b9450bb3fc9950146e798ad7b4dcbc18ef9332c86327212cca81bacd9e9ef5`.

## Entry evidence
M3 protected-main SHA `53c591adbab1dea0618d0d3a727b0bf4638e00de`, Run #414 / `36380613937` is PASS and `TPAA_M3_EXIT_REVIEW_V1 decision=GO`, 28/28 M3 tasks, 116/116 executable P1 metrics, `failed_acceptance=[]`.

## Authority sufficiency
Existing authority freezes exact 104/12 longitudinal membership, P1 subject boundary, DB 1.6.0 longitudinal/debrief tables and Release/history rules. It does not fully freeze exact trend-profile parameters/canonicalization or longitudinal/debrief DTO surfaces. Those gaps are C3 #122 / M4-GOV-001 and fail closed.

## Refinement
21 M4 Tasks: GOVERNANCE 2, LONGITUDINAL 5, OBSERVATION 3, API 2, GUI 3, TEST 6; exactly four batches. M4 remains P1-only.

## Adoption
Candidate decision: **GO_FOR_PR** for C1 refinement only. Adoption requires exact-head Hosted CI, no head drift, protected-main PASS, then #121 may close. M4 product semantics blocked by #122 remain blocked until C3 protected-main adoption.
