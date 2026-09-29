# SDIB-1.5 Adoption / M6 Refinement Review

## Review identity
- **Change class:** C1 — post-M5 backlog refinement.
- **Candidate baseline:** SDIB-1.5; parent SDIB-1.4.
- **Tracking issue:** #150; program policy #149; P2 authority closure #151.
- **Core baseline / DB schema:** CB-1.4.0 / 1.6.0.

## Entry evidence
Protected main `aae1e692774f7c10114d66fd79acb254c2aabfef`, Run #472 / `36556569965` is PASS (14/14 jobs) and preserves the formally qualified P1 product state.

## Candidate refinement
SDIB-1.5 freezes 17 M6 Tasks across exact required workstreams: CAPABILITY, DATA, TEST, GUI and GOVERNANCE; exactly four coarse batches.

M6 is a C4 admission program for P2, but this C1 baseline does **not** itself admit P2. P1 remains immutable/currently admitted; P3-P6 remain inactive.

## C3 boundary
Existing Canonical defines P2 high-level semantics and Core tables `assessment.factor_feature_set`, `assessment.attribution_run`, and `capability.adjusted_capability_estimate`. The implementation-level semantic gap is fail-closed in #151.

## Rolling design
Program #149 requires one-milestone-ahead design. During active M6 implementation, M7/P3 is refined to task/interface/test detail using actual P2 implementation evidence; P3 implementation/admission remains forbidden until M6 protected-main Exit GO.

## Protected-main adoption
PENDING exact-head Hosted CI, guarded merge, and actual protected-main merge-SHA requalification.

**Decision: CANDIDATE.**
