# M4 C3 Longitudinal / Debrief Authority Review

## Change identity
- Issue: #122
- Change class: C3 Semantic contract
- Protected-main parent: `bf8d7e8a2dae94ea78f3a7f6f859ccb391dd70d8`
- Core baseline / DB schema: CB-1.4.0 / 1.6.0
- New controlled artifact: `M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json` v1.0.0
- Artifact SHA-256: `c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa`
- Trend profile SHA-256: `87981c6e3c79f9587786d082d826a6393d15192f67b10c817612da8912982729`
- Candidate Baseline Lock SHA-256: `8bc1834502561992e9aef64d73186c7854ef293e4ec57f658b4e9f72828e0cab`
- Controlled artifact count: 22 -> 23
- Preserved historical M2 adopted lock lineage: `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`

The authority freezes exact P1 sample aggregation, comparison-key/scope hashes, SESSION_ORDER EWMA/OLS/MAD trend semantics, exact-release replay, complete longitudinal/debrief DTOs, and annotation audit-reason binding without changing DB schema 1.6.0. These are new C3 decisions, not recovered R3.4 source facts.

Golden/negative/replay fixture: `C3_LONGITUDINAL_DEBRIEF_AUTHORITY_V1`.
Dedicated validator: `tools/baseline/validate_m4_longitudinal_authority.py`.
Dependent M4 product code remains blocked until protected-main adoption.
