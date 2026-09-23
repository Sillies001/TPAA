# Baseline Change Workflow

This policy implements SDIB-1.0 §5, §30–§31, §39–§40 and M0-GOV-003.

## Classification first

Every proposed change is classified before implementation:

- **C0 Implementation-only:** logical product/authority unchanged.
- **C1 SDIB implementation contract:** repository, CI, packaging or M0/M1 implementation contract.
- **C2 Canonical non-semantic metadata:** authority bytes change without business-behavior change.
- **C3 Semantic contract:** Metric/Stage/DTO/schema/nullability/authority behavior changes.
- **C4 Capability admission:** P2–P6/intended-use expansion.

## Baseline-change rule

C2/C3 changes may not be hidden inside an implementation-only PR. The Baseline Change record must identify authority artifacts, old/new identity/version/hash, validator impact, generated projections, migration/replay/Golden impact, and approval evidence.

A C3 change updates Canonical/version authority **before** implementation consumers are changed. Generated projections are consequences, never the authority.

## Required closure evidence

A Baseline Change PR includes:

1. change class and rationale;
2. affected M/WS/P/Stage and authority refs;
3. prior/new artifact hashes and version/comparability statement;
4. Baseline Lock/validator result;
5. generated-diff result;
6. Golden/replay/migration impact;
7. Windows/Linux impact;
8. security/data-governance impact;
9. reviewer/approval role evidence.

Emergency or critical-security handling may accelerate review but does not permit silent semantic drift.
