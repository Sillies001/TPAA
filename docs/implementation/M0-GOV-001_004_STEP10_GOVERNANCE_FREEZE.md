# M0-GOV-001..004 + ADR-M0-006/008/009/010 — Step 10 Governance Freeze

- **Status:** IN-PROGRESS — governance/ADR implementation is present on the Step 10 branch; hosted CI and later Step 10 backlog remain required.
- **Authority:** SDIB-1.0 §9, §17, §30–§34, §39 step 10; Appendix F/H/I/P/T.
- **Starting revision:** Step 9 frozen-input parity repair `257164dac88825b1f9f7cf781b170e62bc69aaac`.

## Decisions frozen

- ADR-M0-006: M0 profile-specific deterministic development bundles; formal installer qualification remains M5.
- ADR-M0-008: TPAA-owned stdlib structured logging/telemetry facade; UTC log time remains separate from Session Time.
- ADR-M0-009: logical object/Parquet URIs are independent of absolute local filesystem roots.
- ADR-M0-010: repository-controlled CycloneDX 1.6 SBOM plus explicit license/native-dependency inventories.

The machine projections live under `tools/manifest`, `tools/security`, and `tools/storage`.

## Governance backlog

- M0-GOV-001: all ADR-M0-001..010 have CLOSED decisions, owner roles and evidence references.
- M0-GOV-002: governed Feature and Baseline Change issue forms plus PR template require M/WS/P/Stage, authority, change class, tests, security/data and platform impact.
- M0-GOV-003: `docs/governance/BASELINE_CHANGE.md` freezes C0..C4 change classification and C2/C3 baseline-change closure.
- M0-GOV-004: `docs/governance/DEFINITION_OF_DONE.md` freezes PR/Feature/Milestone DoD.

`verify-governance` is a standard-library repository gate and is inserted into the governed CI gate set. Reserved/future Step 10 work is not marked complete by this checkpoint.

## Remaining Step 10

This checkpoint does not yet claim completion of Storage 004..007, API 003..005, Platform 001..003, Security 001..004, DevOps 003..006, package/SBOM generation, or cold-start. Those continue after the governance decisions they depend on are accepted.
