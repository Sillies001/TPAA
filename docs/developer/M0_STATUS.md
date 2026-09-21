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


### M0-CORE-003 — COMPLETE

**Workstream:** WS-CORE
**Acceptance:** DTO/enum/Stage/P-M-WS/Metric registry projections are repeatably generated from Canonical authority.

Implemented:

1. `src/tpaa_codegen/` provides deterministic generator models, naming, rendering, manifest and coordination.
2. All Canonical domain generators consume authority through `CanonicalArtifactLoader`; direct Canonical JSON parsing is prohibited and contract-tested.
3. Generated projections cover baseline metadata, P/M/WS registries and enums, Stage registry, P1 Metric registry, and cross-layer DTO transport types.
4. Canonical identities are preserved as values; Python identifier projection is language-only and collision-fails-closed rather than inventing suffixes.
5. `python tools/dev/tpaa_dev.py generate` writes deterministic UTF-8/LF output; `generate --check` verifies byte identity against checked-in generation.
6. Generation manifest records generator version, Core Baseline, source artifact version/hash and output hash/size.
7. Repeated generation is byte-identical and all generated Python modules import successfully.
8. M0-CORE-004 now governs the checked-in projections; M0-CORE-003 remains the generation-semantics owner.


### M0-CORE-004 — COMPLETE

**Workstream:** WS-CORE
**Acceptance:** generated code carries source hash provenance and manual edits are blocked by regenerate-diff.

Implemented:

1. `GenerationCoordinator` injects deterministic generated markers, generator id/version and source artifact id/version/SHA-256 into every generated Python file.
2. `src/tpaa_generated/__init__.py` is generated as well; the governed tree has no handwritten source exception.
3. `verify-generated` verifies exact expected inventory, exact bytes and provenance without rewriting the worktree.
4. `regenerate-diff` refuses pre-existing uncommitted generated changes, regenerates through the approved coordinator, verifies the tree and requires `git diff --exit-code -- src/tpaa_generated`.
5. Fault injection rejects one-byte drift, missing output, rogue output and uncommitted manual edits.
6. A temporary clean Git checkout proves a committed manual generated edit is rejected after regeneration.
7. ADR-M0-007 is CLOSED on checked-in generated source plus vendor-neutral regenerate-diff enforcement.
8. External CI-provider and Windows execution are not claimed by this task; later platform/CI evidence must invoke the same repository gate.

### M0-CORE-005 — COMPLETE

**Workstream:** WS-CORE
**Acceptance:** lower layers cannot depend on GUI/API and business core cannot directly depend on `tpaa_platform` implementation.

Implemented:

1. `tools/architecture/ARCHITECTURE_POLICY.json` is the executable projection of SDIB-1.0 §7.1 / Appendix E.
2. The standard-library AST scanner resolves static and literal dynamic imports and fails closed on Python parse errors.
3. Governed lower packages importing `tpaa_gui` or `tpaa_api` are rejected with `LOWER_LAYER_TRANSPORT_DEPENDENCY`.
4. Business-core packages importing `tpaa_platform` are rejected with `BUSINESS_CORE_PLATFORM_IMPLEMENTATION_DEPENDENCY`.
5. Concrete Appendix-E reverse edges and selected framework/DB-driver leakage are also enforced.
6. First-party identities are policy-defined, so a prohibited target is still recognized when its source directory is absent.
7. `tpaa_generated` is constrained to Python stdlib/self imports at M0.
8. `python tools/dev/tpaa_dev.py verify-architecture` is the single vendor-neutral local/later-CI entry point.
9. Import scanning deliberately does not claim semantic checks that imports cannot prove; those limitations are machine-readable evidence.

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

### M0-STO-001 — IN PROGRESS

**Workstream:** WS-STORAGE
**Acceptance:** empty DB initializes to schema 1.6.0 and passes schema/hash verification.

Current implementation phase:

1. SDIB-1.0 and frozen Canonical DB authority mapping completed.
2. Implementation Plan v0.1 recorded in `docs/implementation/M0-STO-001_DB_1_6_0_CLEAN_BOOTSTRAP.md`.
3. First vertical slice is the clean bootstrap kernel + schema/version/provenance verification + failure-injection tests.
4. PostgreSQL real-server execution and any unresolved schema/index authority gap remain completion blockers.
5. Repository technology remains outside this slice; ADR-M0-004 is still required before Repository adapter technology is frozen.

## Closed ADRs

- **ADR-M0-001 — CLOSED:** CPython 3.13.x on all four governed Windows/Linux x64 profiles.
- **ADR-M0-002 — CLOSED:** uv resolver, one universal `uv.lock`, frozen sync semantics.
- **ADR-M0-003 — CLOSED:** Ruff 0.16.8 formatter/linter, mypy 2.3.1, pytest 9.0.2, local/CI routed through the developer dispatcher.
- **ADR-M0-007 — CLOSED:** generated source is committed and governed by vendor-neutral verify/regenerate-diff commands.

The project also records **Polars-first** as the default flight-data/DataFrame policy; Pandas is not a default dependency.

## Verification status for this increment

- Baseline exact verification: **21/21 PASS**.
- Repository tests: **69/69 PASS by complete collected-test partition** at M0-CORE-005 completion on this Linux host. The execution harness timed out when all subprocess-heavy contracts were placed in one tool call; unit and every contract partition were executed separately with no failures.
- Canonical loader acceptance verifier: **21/21 controlled artifacts loaded; 8/8 fail-closed negative checks PASS**.
- Toolchain decision verifier: **13/13 checks PASS**.
- `bootstrap --check-only`: **PASS** on CPython 3.13.5 / Linux x86_64.
- `bootstrap` with frozen offline project sync: **PASS** on this host.
- pytest 9.0.2 execution: **PASS** on this host.
- Ruff 0.16.8 execution: **NOT CLAIMED** on this host; exact binary is not installed and the execution environment is network-isolated.
- mypy 2.3.1 execution: **NOT CLAIMED** for the same reason.
- Windows execution/certification: **NOT CLAIMED**; later `M0-PLAT-004` evidence is still required.

## Partial governance state

`M0-GOV-001` is **PARTIAL**, not complete. ADR-M0-001, ADR-M0-002, ADR-M0-003 and ADR-M0-007 are formally closed; ADR-M0-004/005/006/008/009/010 remain open and must be resolved before M0 Exit.

## Source-entry evidence retained

- R3.3 source ZIP SHA-256 matches SDIB-1.0.
- Package manifest: PASS.
- Core validator: **65/65 PASS**.
- Independent audit: **24/24 PASS**.

## Not claimed

- M0 overall completion or M0 Exit Gate.
- P1 capability completion/admission.
- Database, API, GUI, packaging, SBOM, build manifest, CI matrix or cold-start completion.
- Windows/Linux certification or logical-equivalence qualification.

## Next required sequence

Per SDIB-1.0 §39, startup steps 1–4 are complete. Proceed next to:

1. **M0-STO-001 — 1.6.0 clean DB bootstrap**, then Repository skeleton work per SDIB-1.0 §39.
2. Build Application/FastAPI/PySide6 shell and close **M0-CORE-006 runtime baseline handshake** in the prescribed dependency order.
