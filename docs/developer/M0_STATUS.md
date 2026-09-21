# M0 Engineering Bootstrap Status

## Completed

### M0-CORE-001 — COMPLETE

**Workstream:** WS-CORE
**Acceptance:** `baseline verify` returns exact PASS for all controlled artifacts.

Controls already established:

1. CB-1.4.0 Canonical snapshot imported byte-for-byte from the validated R3.3 source package.
2. Repository verifier pins the approved `BASELINE_LOCK.json` SHA-256.
3. All 21 lock-listed artifacts are checked for exact filename, byte count and SHA-256.
4. Missing, modified or unexpected Canonical JSON fails closed.
5. Machine-readable evidence is generated for review.


### M0-CORE-002 — COMPLETE

**Workstream:** WS-CORE
**Acceptance:** Canonical artifact version, schema and hash errors fail closed; errors include artifact id/version context.

Implemented:

1. `src/tpaa_canonical/loader.py` is the governed Canonical consumption entry point.
2. The loader pins the approved CB-1.4.0 `BASELINE_LOCK.json` SHA-256 before trusting lock contents.
3. A selected artifact is trusted only after exact byte-count and SHA-256 verification.
4. Canonical JSON must be an object; declared envelope values are type-checked.
5. Declared `core_baseline` and `db_schema_version` must agree with the frozen baseline metadata.
6. Consumer compatibility expectations support exact artifact version, schema version and required top-level keys.
7. Artifacts without an authority-declared independent version remain `UNVERSIONED_BY_AUTHORITY`; no implementation-only version is invented.
8. `CanonicalArtifactError` carries deterministic engineering diagnostics including artifact id plus expected/actual version and schema context.
9. `python tools/dev/tpaa_dev.py verify-canonical` emits machine-readable acceptance evidence.

### M0-DEV-001 — COMPLETE for backlog minimum acceptance

**Workstream:** WS-DEVOPS
**Acceptance:** `bootstrap/generate/test/run/package` command semantics are discoverable.

Implemented:

- Cross-platform standard-library dispatcher: `tools/dev/tpaa_dev.py`.
- SDIB Appendix I command names are discoverable with explicit implementation state.
- Implemented commands include bootstrap, baseline verification, quality-tool entry points and test-family entry points.
- Commands controlled by future tasks are reserved and fail closed with the controlling task ID instead of returning false success.

### M0-DEV-002 — COMPLETE for backlog minimum acceptance

**Workstream:** WS-DEVOPS
**Acceptance:** Windows/Linux use the same logical dependency lock.

Implemented:

- `pyproject.toml` is the reviewed dependency declaration.
- `uv.lock` is the sole project dependency lock.
- `uv lock --check --offline` verifies lock/project consistency.
- Per-OS Python lockfiles are prohibited by ADR-M0-002.
- Current lock contains no third-party runtime package because no completed task requires one yet.

## Closed ADRs

- **ADR-M0-001 — CLOSED:** CPython 3.13.x on all four governed Windows/Linux x64 profiles.
- **ADR-M0-002 — CLOSED:** uv resolver, one universal `uv.lock`, frozen sync semantics.
- **ADR-M0-003 — CLOSED:** Ruff 0.16.8 formatter/linter, mypy 2.3.1, pytest 9.0.2, local/CI routed through the developer dispatcher.

The project also records **Polars-first** as the default flight-data/DataFrame policy; Pandas is not a default dependency.

## Verification status for this increment

- Baseline exact verification: **21/21 PASS**.
- Repository tests: **25/25 PASS** (10 unit + 15 contract).
- Canonical loader acceptance verifier: **21/21 controlled artifacts loaded; 8/8 fail-closed negative checks PASS**.
- Toolchain decision verifier: **13/13 checks PASS**.
- `bootstrap --check-only`: **PASS** on CPython 3.13.5 / Linux x86_64.
- `bootstrap` with frozen offline project sync: **PASS** on this host.
- pytest 9.0.2 execution: **PASS** on this host.
- Ruff 0.16.8 execution: **NOT CLAIMED** on this host; exact binary is not installed and the execution environment is network-isolated.
- mypy 2.3.1 execution: **NOT CLAIMED** for the same reason.
- Windows execution/certification: **NOT CLAIMED**; later `M0-PLAT-004` evidence is still required.

## Partial governance state

`M0-GOV-001` is **PARTIAL**, not complete. ADR-M0-001 through ADR-M0-003 are formally closed; ADR-M0-004 through ADR-M0-010 remain open and must be resolved before M0 Exit.

## Source-entry evidence retained

- R3.3 source ZIP SHA-256 matches SDIB-1.0.
- Package manifest: PASS.
- Core validator: **65/65 PASS**.
- Independent audit: **24/24 PASS**.

## Not claimed

- M0 overall completion or M0 Exit Gate.
- P1 capability completion/admission.
- M0-CORE-003/004 code generation and generated-source governance.
- Database, API, GUI, packaging, SBOM, build manifest, CI matrix or cold-start completion.
- Windows/Linux certification or logical-equivalence qualification.

## Next required sequence

Per SDIB-1.0 §39, startup steps 1–4 are complete. Proceed next to:

1. **M0-CORE-003 — code generator framework**.
2. **M0-CORE-004 — generated-source read-only/regenerate-diff governance**.
3. Continue the remaining M0 Core/Storage/Application/Platform backlog in SDIB dependency order.
