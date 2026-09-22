# M0-STO-003 — PostgreSQL Service Repository Skeleton

- **Status:** IN PROGRESS
- **Workstream:** WS-STORAGE
- **Depends on:** M0-STO-001 COMPLETE, M0-STO-002 COMPLETE, ADR-M0-004 CLOSED
- **Target:** PostgreSQL Service Repository skeleton using the same engine-neutral Repository/UoW contract as SQLite Desktop.

## Objective

Implement the ADR-M0-004 synchronous Psycopg 3 Service adapter without changing Canonical schema authority, Repository ports, transaction ownership, or runtime migration policy.

## SDIB acceptance

`M0-STO-003` minimum acceptance is PostgreSQL Service repository skeleton with the same Repository contract conformance as SQLite. The broader Storage acceptance also requires SQLite/PostgreSQL repository conformance.

## Frozen implementation boundary

- `tpaa_storage.ports` remains the engine-neutral contract.
- Service driver: Psycopg 3 synchronous DB-API; decision reference `3.3.6`.
- Explicit parameterized SQL only; no SQLAlchemy runtime abstraction and no asyncpg.
- One UoW owns one connection/transaction; repositories never commit.
- Successful use case requires explicit UoW commit; exceptions and uncommitted exit roll back.
- Runtime Repository opens only an already M0-STO-001-ready database and never bootstraps, migrates, repairs, or silently accepts schema/provenance drift.
- Pooling is not required in M0.

## First vertical slice

1. PostgreSQL baseline-metadata repository implementing the existing port.
2. PostgreSQL Service UoW with explicit commit/rollback and read-only transaction support.
3. Readiness check against M0-STO-001 manifest, exact table inventory and physical catalog fingerprint.
4. Minimal parameterized diagnostic write used only for Repository conformance/smoke acceptance.
5. Shared SQLite/PostgreSQL logical metadata/UoW conformance tests.
6. Real-server acceptance on PostgreSQL 16 using the existing disposable M0-STO-001 database/bootstrap harness.

## Dependency activation

The governed dependency is `psycopg[binary]==3.3.6`. The current Chat execution host cannot resolve PyPI, so `uv lock` cannot be regenerated here. The repository must not commit an inconsistent `pyproject.toml`/`uv.lock`; dependency activation remains an explicit completion gate to execute in the user's networked Windows CPython 3.13 environment before this task can become COMPLETE.

## Failure semantics

- missing Psycopg dependency -> deterministic fail-closed error;
- connection failure -> fail closed;
- autocommit connection -> reject;
- manifest/schema/provenance mismatch -> reject before Repository use;
- explicit commit finalizes the UoW;
- exception/uncommitted exit -> rollback;
- no runtime bootstrap/migration/repair.

## Explicit non-scope

- business Metric/Stage/Release repositories;
- connection pooling;
- Alembic activation (M0-STO-005);
- Application/FastAPI/PySide6;
- M0-CORE-006 runtime handshake completion.

## Completion gates

1. `psycopg[binary]==3.3.6` activated through `uv` and the single `uv.lock`.
2. Psycopg import on governed CPython 3.13 profile PASS.
3. Real PostgreSQL Repository acceptance PASS.
4. SQLite/PostgreSQL shared Repository/UoW conformance PASS.
5. Existing M0-STO-001/M0-STO-002 and historical architecture/codegen/baseline gates remain PASS.
6. Formal commit, clean clone, evidence, bundle, repo ZIP and SHA-256 manifest.
