# ADR-M0-004 — Repository DB Access Implementation

- **Status:** CLOSED
- **Decision date:** 2026-09-22
- **Owner role:** WS-STORAGE technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §10.2, §17, Appendix E/F/Q; ED-2.0 05E §2, §15, §16
- **Evidence study:** `docs/implementation/ADR-M0-004_REPOSITORY_DB_ACCESS_STUDY.md`
- **Machine policy:** `tools/storage/REPOSITORY_DB_ACCESS_POLICY.json`

## Decision

TPAA freezes Repository runtime access as a **synchronous, explicit-SQL, driver-isolated port/adapter architecture**:

1. Repository and Unit-of-Work contracts live in `tpaa_storage.ports` and expose only engine-neutral Python protocols/value objects. Concrete driver types, SQL, dialect flags and connection objects are forbidden in Domain/Application/API/GUI contracts.
2. Desktop Repository implementation uses CPython 3.13 standard-library `sqlite3`, SQLite WAL, and the SDIB single-Backend-writer model.
3. Service Repository implementation uses **Psycopg 3 synchronous DB-API**, with Psycopg **3.3.6** as the decision reference version for M0-STO-003 dependency activation. Async Psycopg/`asyncpg` is not the M0/M1 Repository contract.
4. Runtime adapters use **explicit parameterized SQL**. SQLAlchemy ORM and SQLAlchemy Core are not Repository runtime abstractions and must not create a second persistence mapping/schema authority.
5. A Unit of Work owns one adapter connection/transaction. Repository methods never commit. The Application use case explicitly commits successful work; exceptions or exit without explicit commit roll back. Multiple repositories in one use case share that UoW transaction.
6. Connection pooling is behind the connection-provider/adapter boundary and is **not required in M0**. A later pool implementation must not change Repository/UoW contracts.
7. M0-STO-001 remains the schema/bootstrap/readiness authority. Repository startup never silently bootstraps, migrates, repairs or accepts a mismatched schema.
8. ED-2.0 05E's **Alembic** requirement is retained for Service/CI migration execution/history. Alembic is not schema authority and is not a Repository runtime abstraction. M0-STO-005 owns its activation and migration discipline.

The decision does **not** implement M0-STO-002/M0-STO-003 repositories; it freezes the technology and transaction boundary those tasks must implement.

## Rationale

The Canonical baseline already defines persistence fields and M0-STO-001 produces/validates physical schema projections. Introducing ORM entities or SQLAlchemy `MetaData` as the normal runtime mapping would create an unnecessary second representation that could drift from that authority. Direct DB-API adapters keep dialect-specific details at the Storage edge while the shared ports/conformance tests preserve logical equivalence.

A synchronous contract is the smallest common model for the required Desktop single-writer SQLite backend and Service PostgreSQL profile. Psycopg 3 provides a modern synchronous DB-API with explicit transaction controls and also retains an async API if later measured workload evidence justifies reopening the contract. FastAPI availability does not by itself require an async database contract.

Explicit Unit-of-Work ownership is required because SDIB release/publish semantics span multiple persistence operations atomically. Allowing individual repositories to auto-commit would make cross-repository rollback impossible and would conflict with fail-closed publication semantics.

## Alternatives considered

### SQLAlchemy Core

Rejected as the Repository runtime abstraction. It is mature and supports connection/transaction management, but its SQL/schema expression model adds a second mapping layer without removing actual SQLite/PostgreSQL semantic differences. Alembic may depend on SQLAlchemy internally in migration tooling; that does not authorize runtime Repository imports.

### SQLAlchemy ORM

Rejected. Identity maps and ORM entities are unnecessary for the Canonical/release-oriented persistence model and would invite persistence entities into Domain/Application contracts, contrary to SDIB Appendix E.

### asyncpg / async-first Repository contract

Rejected for M0/M1. It would split the Desktop and Service programming models before workload evidence demonstrates a need, while complicating transaction/UoW parity. Async access is a reopen option, not the baseline.

### One generic adapter hiding both drivers

Rejected. Genuine engine differences belong in concrete adapters. The commonality is the Repository/UoW **contract and conformance behavior**, not pretending SQL dialects are identical.

## Dependency and migration consequences

Closing this ADR freezes technology but intentionally does not add unused dependencies to `pyproject.toml` before the implementing work package:

- M0-STO-002 requires no new DB package (`sqlite3` is stdlib).
- M0-STO-003 must activate Psycopg 3.3.6 through `uv` and the one governed `uv.lock`, then prove import/connection/conformance on mandatory profiles.
- M0-STO-005 activates the baseline-required Alembic migration tooling. Alembic autogeneration cannot replace Canonical/migration review authority.

The current architecture policy is strengthened so `tpaa_storage` runtime code cannot silently introduce SQLAlchemy, Alembic or asyncpg; Psycopg and sqlite3 remain confined to Storage adapters, while existing upper-layer driver bans remain in force.

## Verification / evidence

- `docs/implementation/ADR-M0-004_REPOSITORY_DB_ACCESS_STUDY.md`
- `tools/storage/REPOSITORY_DB_ACCESS_POLICY.json`
- `tests/contract/test_adr_m0_004_repository_db_access.py`
- M0-STO-001 SQLite transaction/fail-closed suite.
- M0-STO-001 real PostgreSQL 16.15 acceptance: clean bootstrap/verify, transactional rollback, schema/provenance tamper detection.
- Current upstream review: Psycopg 3.3.6 supports CPython 3.13 and Windows/POSIX; SQLAlchemy 2.0.54 and Alembic 1.20.0 support Python 3.13.
- Historical Baseline/Canonical/codegen/generated-governance/architecture/bootstrap gates must remain PASS when this ADR closes.

The current Chat host is network-isolated for `uv`; therefore a Psycopg package import/connection is not claimed here. As with ADR-M0-003 tool availability, this does not leave the architecture decision open: M0-STO-003 owns exact dependency activation and platform execution evidence before its implementation can be complete.

## Reopen conditions

Reopen if:

- Psycopg 3 cannot satisfy the governed CPython 3.13 Windows/Linux x64 profiles;
- SQLite/PostgreSQL conformance reveals a semantic mismatch that cannot be contained in adapters;
- measured workload evidence requires an async Repository contract rather than an implementation detail;
- migration tooling begins to compete with the Canonical schema authority;
- security/support status invalidates a selected technology.
