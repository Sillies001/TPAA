# ADR-M0-004 Repository DB Access Implementation Study

- **Study version:** 1.0
- **Date:** 2026-09-22
- **Decision:** ADR-M0-004
- **Scope:** Repository access technology only; no business Repository implementation is introduced by this study.

## 1. Objective

Freeze the SQLite/PostgreSQL Repository access implementation required by SDIB-1.0 without creating a second schema authority, leaking database-driver types into Domain/Application contracts, or prematurely implementing M0-STO-002/M0-STO-003 business persistence.

## 2. Binding authority and existing evidence

The decision is constrained by the frozen repository and Canonical baseline:

1. SDIB-1.0 §10.2 requires Desktop SQLite WAL, Service PostgreSQL, and one shared Repository contract with no dialect branch in Domain.
2. SDIB Appendix E allows `tpaa_storage` to own storage ports/implementations while forbidding DB-driver leakage into business-core/Application/GUI layers.
3. ED-2.0 05E §2 requires Desktop SQLite WAL with one Backend Repository writer and Service/CI PostgreSQL; §16 repeats single-writer Desktop and shared dialect-neutral Repository contracts.
4. M0-STO-001 established `CORE_LOGICAL_MODEL.json` as the single persistence schema authority and completed clean bootstrap/verification on SQLite and real PostgreSQL 16.15.
5. M0-STO-001 real PostgreSQL acceptance already demonstrated transactional rollback and fail-closed physical-schema/provenance verification using direct SQL. Repository runtime access must consume that schema, never redefine or auto-migrate it.

## 3. Decision drivers

- Preserve one engine-neutral Repository contract.
- Keep Canonical schema authority singular; avoid ORM metadata becoming a shadow schema.
- Make transaction ownership explicit and testable across SQLite/PostgreSQL.
- Respect Desktop single-writer semantics.
- Support CPython 3.13 and governed Windows/Linux x64 profiles.
- Keep dependency and runtime complexity proportional to M0/M1 needs.
- Permit later FastAPI/PySide6 shells without forcing GUI/API code to know database technology.
- Keep migration execution separate from runtime Repository access.

## 4. Candidate matrix

| Candidate | Strengths | Material risks against TPAA baseline | Result |
| --- | --- | --- | --- |
| stdlib `sqlite3` + Psycopg 3 + explicit parameterized SQL | Direct DB-API semantics; explicit transaction control; preserves Canonical DDL authority; small runtime abstraction; easy engine-specific adapters behind same port | Requires deliberate parity/conformance tests and two SQL adapters where dialects differ | **SELECTED** |
| SQLAlchemy Core + SQLite/PostgreSQL | Common connection/transaction API and SQL expression system; mature multi-dialect ecosystem | Core `MetaData`/Table definitions risk becoming a second physical schema model; abstraction does not remove genuine SQLite/PostgreSQL semantic differences; extra runtime layer not required by current acceptance | REJECTED for Repository runtime |
| SQLAlchemy ORM | Rich unit-of-work/identity-map features | ORM entities would couple persistence shape to runtime objects, create a competing mapping authority, and are explicitly unwanted above Storage; unnecessary for current release/replay repository model | REJECTED |
| `sqlite3` + async PostgreSQL/`asyncpg` | High-concurrency async Service potential | Splits transaction programming model from synchronous Desktop, complicates shared UoW semantics before workload evidence, and makes later GUI/local backend integration harder; FastAPI does not require async DB access | REJECTED for M0/M1 baseline |

## 5. External compatibility review

The decision review used current upstream package metadata/documentation on 2026-09-22:

- Psycopg 3.3.6 is the current stable Psycopg 3 release reviewed for this ADR, requires Python >=3.10, declares CPython 3.13 and Windows/POSIX support, and provides synchronous DB-API plus optional async APIs. The `psycopg-binary` 3.3.6 distribution publishes CPython 3.13 Windows x64 and Linux x64 wheels.
- SQLAlchemy 2.0.54 declares CPython 3.13 support. Its Core layer provides SQL rendering, DB-API integration, transactions and schema description; these capabilities are not needed as an additional Repository runtime authority for TPAA.
- Alembic 1.20.0 requires Python >=3.10 and declares Python 3.13 support. ED-2.0 05E already places Alembic in the Service/CI migration profile; this ADR therefore preserves Alembic as migration execution/history tooling, not Repository runtime abstraction and not schema authority.

The current Chat execution host is network-isolated for `uv`, so the selected Psycopg dependency is intentionally **not activated early** merely to close the architecture decision. M0-STO-003 must add the exact governed dependency through `uv`/`uv.lock` and execute import/connection/conformance evidence on the mandatory platform profiles. This is an implementation handoff, not an undecided architecture choice.

## 6. Transaction / Unit-of-Work spike and semantics

The chosen contract is synchronous and explicit:

1. Application use cases request an engine-neutral Unit of Work through a port.
2. A Storage adapter owns one connection and one transaction for that UoW.
3. Repository methods never commit or roll back independently.
4. Successful persistence requires an explicit `commit()` by the use case/UoW coordinator.
5. Exceptions roll back; leaving the UoW without explicit commit also rolls back (fail-closed).
6. Multiple repositories participating in one use case share the same UoW transaction.
7. Nested/savepoint semantics are not part of the M0 public contract.

SQLite stdlib transaction behavior is executable on the current host and is contract-tested. PostgreSQL transactional rollback and clean-schema behavior were already proven by M0-STO-001 against PostgreSQL 16.15. Psycopg 3 upstream transaction contexts support commit-on-success/rollback-on-exception, but TPAA will wrap them so the public UoW requires explicit commit and does not expose the driver object.

## 7. Port and adapter boundary

The implementation handoff is frozen as:

```text
Application use case
        |
        v
engine-neutral Repository/UoW ports (`tpaa_storage.ports`)
        |
        +-----------------------+
        |                       |
        v                       v
SQLite adapter              PostgreSQL adapter
stdlib sqlite3              Psycopg 3 sync API
WAL / single writer         PostgreSQL transaction
        \                       /
         \                     /
          same logical contract
```

Ports may use Python protocols/dataclasses/value objects only. They must not expose `sqlite3.Connection`, `psycopg.Connection`, SQLAlchemy types, SQL syntax, DSNs, or dialect flags.

## 8. SQL and schema boundary

Runtime Repository adapters use explicit parameterized SQL. SQL may differ per adapter where the engines genuinely differ, but logical Repository behavior must remain conformant. Runtime SQL must not redefine table identity/nullability/constraints already governed by `CORE_LOGICAL_MODEL.json` and M0-STO-001 projections.

No runtime Repository code may automatically create, migrate, or repair the schema. Runtime startup/readiness consumes M0-STO-001 verification and fails closed on incompatibility.

## 9. Migration boundary

ED-2.0 05E prescribes Alembic for the Service/CI migration profile. ADR-M0-004 therefore records:

- Alembic is an execution/history mechanism only.
- `CORE_LOGICAL_MODEL.json` plus formally governed migration artifacts remain authoritative.
- Alembic autogeneration output is never accepted as independent schema truth.
- Repository runtime startup never auto-migrates.
- Detailed migration topology, down/forward-recovery and SQLite integration remain M0-STO-005 scope.

## 10. Dependency activation policy

This ADR freezes technology but does not add unused runtime dependencies before the owning implementation task:

- `sqlite3`: already part of CPython 3.13; activated by M0-STO-002.
- `psycopg` generation 3, reference version 3.3.6: M0-STO-003 must add the exact selected dependency through the single `uv.lock` and validate Windows/Linux x64.
- Alembic, reference version 1.20.0: M0-STO-005 activates/pins it when the migration harness needs it.
- SQLAlchemy may exist transitively through Alembic but is forbidden as a Repository runtime abstraction unless this ADR is reopened.

## 11. Implementation handoff acceptance

M0-STO-002/M0-STO-003 must prove, before their own completion:

- ports expose no concrete DB types;
- SQLite uses WAL and one Backend writer;
- one UoW transaction spans all repositories participating in a use case;
- explicit commit persists and exception/uncommitted exit rolls back;
- PostgreSQL adapter uses the selected synchronous Psycopg 3 API;
- same logical fixtures produce equivalent Repository results on SQLite/PostgreSQL;
- M0-STO-001 schema/provenance verification remains the startup boundary;
- architecture policy rejects ORM/async-driver leakage and upper-layer DB access.

## 12. Reopen triggers

Reopen ADR-M0-004 only if platform support, security/support status, conformance evidence, or measured workload evidence invalidates the frozen choices. Convenience preference alone is not a reopen reason.
