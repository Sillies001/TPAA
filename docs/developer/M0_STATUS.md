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

### M0-CORE-006 — COMPLETE

**Workstream:** WS-CORE
**Acceptance:** Core/Catalog/schema/build mismatch does not enter READY.

Completed implementation and acceptance:

1. `tpaa_canonical.runtime_handshake` defines the transport-neutral runtime baseline identity, READY/NOT_READY state, deterministic mismatch codes and exact fail-closed evaluator.
2. The governed identity includes product build, Core Baseline, Baseline Lock hash, DB schema, Core logical-model authority id/hash, P1 Metric Catalog version/hash and cross-layer DTO authority hash.
3. The trusted local identity is constructed only through `CanonicalArtifactLoader`, preserving the existing exact Baseline Lock and controlled-artifact hash trust boundary.
4. Product build identity is an explicit input; M0-CORE-006 does not invent or pre-empt the M0-DEV-003 build manifest/source-revision authority.
5. Exact Core, Catalog, schema or product-build mismatch returns `NOT_READY`; multiple mismatches are retained in deterministic diagnostic order.
6. The handshake module has no FastAPI, GUI, Repository, database-driver or platform implementation dependency; M0-API-002 will expose it through the Application/API boundary without reimplementing comparison rules.
7. Final regression passed 154/154 by complete partition: unit 63/63, migration 26/26, contract 65/65; historical Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository-policy/bootstrap/lock gates PASS.

Implementation record: `docs/implementation/M0-CORE-006_RUNTIME_BASELINE_HANDSHAKE.md`.


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

### M0-STO-001 — COMPLETE

**Workstream:** WS-STORAGE
**Acceptance:** empty DB initializes to schema 1.6.0 and passes schema/hash verification.

Completed implementation and acceptance:

1. Frozen SDIB-1.0 / Canonical authority mapping establishes DB target `1.6.0` from `BASELINE_LOCK.json` and `CORE_LOGICAL_MODEL.json`.
2. SQLite Desktop clean bootstrap is deterministic, WAL-backed for file DBs, transactional, provenance-bound and fail-closed.
3. PostgreSQL Service DDL is deterministically projected from the same 77-table Canonical authority using a 125-edge FK graph with zero missing targets/cycles and lexical tie-breaking.
4. Repository-controlled external-`psql` bootstrap/verify/acceptance harness implements exact table/schema inventory, manifest provenance and PostgreSQL catalog fingerprint verification without selecting a Python Repository driver.
5. Real PostgreSQL 16.15 acceptance PASS: clean bootstrap/verify, mid-bootstrap rollback, missing-table, manifest-tamper, DDL-tamper and unexpected-index fail-closed checks all PASS; verified schema `1.6.0`, 77 tables, Core Baseline `CB-1.4.0`, exact Canonical/baseline-lock hashes.
6. Final repository regression collected 98 tests and passed 98/98 by complete file/partition; historical Baseline/Canonical/codegen/generated-governance/regenerate-diff/architecture/bootstrap gates PASS.
7. M0-STO-001 itself did not freeze Repository technology; ADR-M0-004 was subsequently CLOSED before Repository skeleton implementation.

Implementation record: `docs/implementation/M0-STO-001_DB_1_6_0_CLEAN_BOOTSTRAP.md` v0.6.

### M0-STO-002 — COMPLETE

**Workstream:** WS-STORAGE
**Acceptance:** SQLite Desktop repository skeleton; WAL, single-writer and transaction smoke PASS.

Completed implementation and acceptance:

1. `tpaa_storage.ports` defines engine-neutral baseline-metadata Repository and explicit Unit-of-Work protocols with no concrete DB-driver types.
2. `SQLiteDesktopUnitOfWork` opens only an existing M0-STO-001-verified DB, requires WAL, enables FK enforcement, uses read `BEGIN` / write `BEGIN IMMEDIATE`, and never bootstraps or migrates at runtime.
3. Write UoWs require an exclusive process-local writer lease; SQLite `BEGIN IMMEDIATE` remains the database/cross-process serialization guard.
4. Repository methods never commit; explicit UoW commit is required, while exception or uncommitted exit rolls back. Read UoWs enforce `PRAGMA query_only=ON`.
5. The minimal concrete Repository exposes only existing bootstrap/baseline metadata; no Metric/Stage/Release/Application business Repository semantics were introduced.
6. `db-sqlite-repository-acceptance` executes disposable real-adapter WAL/read/write/rollback/single-writer smoke using the same M0-STO-001 bootstrap implementation.
7. Final regression collected 118 tests and passed 118/118 by complete partition: unit 42/42, migration 25/25, contract 51/51. Historical Baseline/Canonical/codegen/generated-governance/regenerate-diff/architecture/bootstrap and Repository-policy gates PASS.

Implementation record: `docs/implementation/M0-STO-002_SQLITE_DESKTOP_REPOSITORY_SKELETON.md`.

### M0-STO-003 — COMPLETE

**Workstream:** WS-STORAGE
**Acceptance:** PostgreSQL Service repository skeleton; shared Repository contract conformance PASS.

Completed implementation and acceptance:

1. `PostgreSQLServiceUnitOfWork` implements the ADR-M0-004 synchronous Service adapter behind the unchanged engine-neutral ports using Psycopg 3 synchronous DB-API.
2. `psycopg[binary]==3.3.6` is activated through the single governed `uv.lock`; Windows CPython 3.13.5 import reported Psycopg `3.3.6`, and `uv lock --check` passed.
3. Runtime readiness verifies M0-STO-001 manifest provenance, deterministic projection hash, exact table inventory and live PostgreSQL catalog hash before Repository use.
4. Explicit commit is required; uncommitted/exception exits roll back; read-only transactions use PostgreSQL `SET TRANSACTION READ ONLY`.
5. The disposable real-server harness composes the existing M0-STO-001 bootstrap with the Psycopg Repository smoke and enforces an M0-STO-003-scoped database prefix before create/drop.
6. Real PostgreSQL acceptance PASS: bootstrap verify, Repository conformance, transaction smoke, read transaction, explicit write commit, uncommitted-exit rollback and exception rollback; schema `1.6.0`, 77 Canonical tables, Core baseline `CB-1.4.0`.
7. Application/FastAPI/PySide6, Alembic activation and M0-CORE-006 were out of scope for M0-STO-003; M0-API-001 is completed separately below.

Implementation record: `docs/implementation/M0-STO-003_POSTGRESQL_SERVICE_REPOSITORY_SKELETON.md`.

### M0-API-001 — COMPLETE

**Workstream:** WS-API
**Acceptance:** Application Service skeleton; GUI/REST business access constrained to Application use cases.

Completed implementation and acceptance:

1. `tpaa_application` is now a real package with a typed `ApplicationService` facade and Application-owned result models.
2. The first concrete use case, `GetStorageBaselineStatus`, reads bootstrap provenance only through the engine-neutral `RepositoryUnitOfWork` port; no concrete database adapter or driver leaks into Application.
3. A real SQLite integration path proves M0-STO-001 bootstrap → Repository UoW → Application Service without direct transport/DB coupling.
4. Architecture policy now encodes Appendix E strictly: `tpaa_api` and `tpaa_gui` may import first-party `tpaa_application` and `tpaa_generated` only.
5. M0-CORE-006 READY/version mismatch semantics, FastAPI, PySide6 and ADR-M0-005 lifecycle/IPC remain deliberately outside this task.
6. Final regression passed 138/138 by complete partition: unit 50/50, migration 26/26, contract 62/62; historical Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository-policy/bootstrap/lock gates PASS.

Implementation record: `docs/implementation/M0-API-001_APPLICATION_SERVICE_SKELETON.md`.

### M0-API-002 — COMPLETE

**Workstream:** WS-API
**Acceptance:** FastAPI local/service skeleton; health/readiness/version endpoints smoke PASS.

Completed implementation and acceptance:

1. `tpaa_application.runtime` projects the M0-CORE-006 handshake into transport-neutral Application models without reimplementing READY comparison rules.
2. `tpaa_api.create_app()` exposes `/health`, `/readiness` and `/version`; API code imports `tpaa_application` rather than Canonical/Storage/GUI implementation packages.
3. `/readiness` maps authoritative READY to HTTP 200 and NOT_READY to HTTP 503 while preserving deterministic Core mismatch codes.
4. `api-smoke` performs real TestClient requests for liveness, ready/not-ready and version diagnostics and self-bootstraps the repository `src/` path for direct clean-checkout execution.
5. `fastapi[standard-no-fastapi-cloud-cli]==0.141.1` is frozen in `pyproject.toml` and the single universal `uv.lock`; the lock uses official PyPI sources and contains no project-index mirror override.
6. Governed Windows evidence: CPython 3.13.5 imports FastAPI 0.141.1; `api-smoke` health/readiness/version checks PASS; `uv lock --check` PASS.
7. Final regression passed 163/163 by complete partition: unit 68/68, migration 26/26, contract 69/69; historical Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository-policy/bootstrap/offline-lock gates PASS.

Implementation record: `docs/implementation/M0-API-002_FASTAPI_HEALTH_READINESS_VERSION.md`.

### ADR-M0-004 — CLOSED

**Decision:** Repository DB access implementation.

Frozen implementation boundary:

1. Engine-neutral Repository/Unit-of-Work ports live under `tpaa_storage.ports`; concrete driver types and dialect flags may not cross the port boundary.
2. Desktop adapter: synchronous CPython stdlib `sqlite3`, WAL, one Backend writer.
3. Service adapter: synchronous Psycopg 3 DB-API; decision reference version `3.3.6`, dependency activation owned by M0-STO-003 through the single `uv.lock`.
4. Runtime persistence uses explicit parameterized SQL; SQLAlchemy ORM/Core and asyncpg are rejected as Repository runtime abstractions.
5. Unit of Work owns one connection/transaction; repositories never commit; successful work requires explicit use-case commit and all exceptional/uncommitted exits roll back.
6. M0-STO-001 remains the schema/readiness authority; Repository runtime never silently bootstraps/migrates/repairs schema.
7. ED-2.0 05E Alembic requirement is retained for migration execution/history only; M0-STO-005 owns activation and migration topology.
8. `verify-repository-policy` provides a machine-readable ADR gate; architecture policy prevents rejected runtime abstractions in `tpaa_storage` and retains upper-layer DB-driver bans.

Evidence study: `docs/implementation/ADR-M0-004_REPOSITORY_DB_ACCESS_STUDY.md`.
Machine policy: `tools/storage/REPOSITORY_DB_ACCESS_POLICY.json`.

## Closed ADRs

- **ADR-M0-001 — CLOSED:** CPython 3.13.x on all four governed Windows/Linux x64 profiles.
- **ADR-M0-002 — CLOSED:** uv resolver, one universal `uv.lock`, frozen sync semantics.
- **ADR-M0-003 — CLOSED:** Ruff 0.16.8 formatter/linter, mypy 2.3.1, pytest 9.0.2, local/CI routed through the developer dispatcher.
- **ADR-M0-004 — CLOSED:** engine-neutral Repository/UoW ports; stdlib sqlite3 synchronous Desktop adapter; Psycopg 3 synchronous Service adapter; explicit parameterized SQL; SQLAlchemy ORM/Core rejected as runtime abstraction; Alembic limited to migration tooling.
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

## ADR-M0-005 — CLOSED

**Desktop backend lifecycle / IPC:** frozen before PySide6 implementation.

1. One GUI owns one isolated local backend child process; no in-process server and no silent attach to unowned backends.
2. Backend binds only `127.0.0.1` on an OS-assigned ephemeral port; fixed ports and probe-close-rebind selection are forbidden.
3. GUI generates a fresh 32-byte random bearer token per backend process and passes it only through the private stdin startup control record.
4. Lifecycle control is stdio NDJSON; HTTP READY requires authenticated `/readiness` plus `/version` after the child reports `LISTENING`.
5. Normal shutdown is cooperative over stdin; terminate/kill are bounded failure-recovery fallbacks only.
6. Desktop HTTP disables docs/OpenAPI/CORS and requires bearer authentication on all routes.
7. PySide6 is not activated by the ADR; M0-GUI-001 owns that governed dependency activation.

Machine gate: `python tools/dev/tpaa_dev.py verify-desktop-lifecycle-policy`.


## M0-GUI-001 — COMPLETE

**PySide6 application shell:** shell, governed dependency activation, and Windows/Linux startup-exit acceptance complete.

1. `tpaa_gui` now owns a minimal `QApplication`/`QMainWindow` shell with lazy PySide6 loading and deterministic missing-dependency failure.
2. Developer commands `run gui`, `run-gui`, and `gui-smoke --headless` are implemented for the shell.
3. The shell deliberately contains no backend child process, token, port, readiness, HTTP, Storage, or Canonical logic; those remain M0-GUI-002 under ADR-M0-005.
4. `PySide6==6.11.2` is present in `pyproject.toml` and the single governed 46-package `uv.lock`; Windows CPython 3.13.5 import/version and headless startup-exit smoke are PASS.
5. Linux Ubuntu 24.04 LTS / WSL2 x86_64 with CPython 3.13.5 and `uv 0.12.17` consumed the same lock via `uv sync --locked`; PySide6 6.11.2 import and headless startup-exit smoke are PASS, exit code 0, and the Git worktree remained clean.
6. Final repository regression passed **181/181** by complete partition: unit 72/72, migration 26/26, contract 83/83; historical Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository-policy/Desktop-lifecycle-policy/bootstrap/API-smoke/offline-lock gates PASS.
7. Backend child process/token/port/readiness lifecycle remains explicitly owned by M0-GUI-002.


## M0-GUI-002 — IN PROGRESS

**Local backend lifecycle handshake:** executable ADR-M0-005 child/token/READY/shutdown slice implemented; Windows real-process acceptance remains outstanding.

1. GUI owns one isolated backend child and generates a fresh 32-byte URL-safe bearer token per lifecycle.
2. Child binds `127.0.0.1:0`, reports non-secret `LISTENING` over stdout NDJSON, and never receives the token through argv/environment/files.
3. Parent performs authenticated `/readiness` and `/version`; LISTENING alone never implies READY.
4. Desktop HTTP requires exact bearer authentication, rejects Origin, and disables docs/OpenAPI/CORS.
5. Backend crash or handshake mismatch becomes NOT_READY immediately.
6. Normal exit sends stdin `SHUTDOWN`; terminate/kill are bounded fallback only.
7. Linux/current-host real lifecycle smoke is PASS. The first Windows run failed closed with `LISTENING_PID_MISMATCH` because the Windows venv executable is a redirector; the implementation now bypasses that redirector using `sys._base_executable` plus `__PYVENV_LAUNCHER__` while retaining exact PID ownership checks. Windows rerun is required before COMPLETE.

Developer gate: `python tools/dev/tpaa_dev.py desktop-backend-smoke`.

## Partial governance state

`M0-GOV-001` is **PARTIAL**, not complete. ADR-M0-001, ADR-M0-002, ADR-M0-003, ADR-M0-004, ADR-M0-005 and ADR-M0-007 are formally closed; ADR-M0-006/008/009/010 remain open and must be resolved before M0 Exit.

## Source-entry evidence retained

- R3.3 source ZIP SHA-256 matches SDIB-1.0.
- Package manifest: PASS.
- Core validator: **65/65 PASS**.
- Independent audit: **24/24 PASS**.

## Not claimed

- M0 overall completion or M0 Exit Gate.
- P1 capability completion/admission.
- M0-GUI-002 Windows real-process lifecycle acceptance, GUI diagnostics/automation, packaging, SBOM, build manifest, CI matrix or cold-start completion.
- Windows/Linux certification or logical-equivalence qualification.

## Next required sequence

Per SDIB-1.0 §39, steps 1–6 are complete and step 7 is now active. Proceed in dependency order:

1. Complete **M0-GUI-002 — Local backend lifecycle handshake** with Windows real-process acceptance against the implemented frozen policy.
2. Complete M0-GUI-003/004 diagnostics and UI automation in dependency order.
3. Then proceed to §39 step 8 cross-platform CI.
