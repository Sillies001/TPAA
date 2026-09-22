# M0-STO-002 — SQLite Desktop Repository Skeleton

- **Status:** COMPLETE
- **Workstream:** WS-STORAGE
- **SDIB acceptance:** SQLite WAL, single Backend writer, transaction smoke PASS
- **Architecture authority:** ADR-M0-004 (CLOSED)
- **Schema/readiness authority:** M0-STO-001 / DB schema 1.6.0

## 1. Objective

Implement the smallest SQLite Desktop Repository skeleton required by SDIB-1.0 without introducing business persistence semantics. The slice establishes engine-neutral Repository/Unit-of-Work ports, a synchronous stdlib `sqlite3` Desktop adapter, explicit transaction ownership, WAL/readiness enforcement, and deterministic single-writer/read-write transaction diagnostics.

## 2. Acceptance criteria

1. Runtime access opens only an existing M0-STO-001-verified SQLite database; it never bootstraps, migrates or repairs schema.
2. SQLite journal mode must already be `WAL`; mismatch fails closed.
3. Foreign keys are enabled on every adapter connection.
4. One write Unit of Work owns one connection and begins `BEGIN IMMEDIATE`.
5. A second concurrent writer for the same DB path is rejected deterministically in-process; SQLite's own writer lock remains the cross-process guard.
6. Repository methods never commit. Unit-of-Work success requires explicit `commit()`; exception or exit without commit rolls back.
7. Engine-neutral ports expose no `sqlite3.Connection`, SQL strings, DSN or dialect switch.
8. Read/write transaction smoke uses the real adapter and M0-STO-001 bootstrap manifest; it does not create a second schema implementation.
9. Historical M0-STO-001 and architecture/codegen/baseline gates remain PASS.

## 3. Authority mapping

- SDIB-1.0 §10.2: Desktop = SQLite WAL + local Backend single writer; SQLite/PostgreSQL share Repository contract.
- SDIB-1.0 §17: M0-STO-002 = SQLite Desktop repository skeleton; minimum acceptance `WAL、单写者、事务 smoke PASS`.
- SDIB-1.0 Appendix Q: Repository readiness includes required read/write transaction smoke.
- ADR-M0-004: synchronous stdlib `sqlite3`, explicit parameterized SQL, explicit UoW, one connection per UoW, Repository commit forbidden.
- M0-STO-001: schema/bootstrap/version/provenance verification remains authoritative.

## 4. Skeleton architecture

`tpaa_storage.ports` contains only engine-neutral protocols and immutable metadata values. `tpaa_storage.sqlite_repository` implements those ports for Desktop SQLite. The adapter validates M0-STO-001 readiness before opening a transaction and never mutates schema as part of startup.

## 5. Transaction semantics

- Read UoW: `BEGIN` + `PRAGMA query_only=ON`.
- Write UoW: process-local writer lease + `BEGIN IMMEDIATE`.
- `commit()` finalizes the transaction explicitly.
- `rollback()` finalizes explicitly.
- `__exit__` rolls back every still-open transaction, including normal exit without explicit commit.
- Nested/public savepoint semantics are out of scope per ADR-M0-004.

## 6. Single-writer policy

The Desktop application architecture permits one authoritative local Backend writer. The adapter adds a non-blocking per-database process-local writer lease to reject accidental concurrent writer UoWs deterministically. `BEGIN IMMEDIATE` remains the SQLite database-level/cross-process writer serialization mechanism.

## 7. Minimal Repository surface

The only concrete Repository in this M0 skeleton is read-only baseline/schema metadata backed by the existing `_tpaa_bootstrap_manifest`. No Metric, Stage, Release, Assessment or other business Repository is introduced.

## 8. Diagnostics / smoke

The acceptance diagnostic performs:

1. metadata read transaction;
2. committed write transaction using a no-op manifest update;
3. uncommitted write mutation followed by automatic rollback and M0-STO-001 re-verification;
4. exception-triggered rollback and re-verification;
5. concurrent-writer rejection while one write UoW is active.

The mutation is confined to a disposable M0-STO-002 acceptance DB and is never a new schema authority.

## 9. Failure semantics

Missing DB, invalid bootstrap provenance/schema, non-WAL DB, disabled FK enforcement, writer contention, invalid UoW lifecycle and SQL/database errors fail closed with deterministic Storage errors.

## 10. Explicit non-scope

- PostgreSQL/Psycopg adapter (M0-STO-003).
- Business Repository methods/use cases.
- Connection pooling.
- Nested/public savepoints.
- Migration/Alembic activation (M0-STO-005).
- Application/FastAPI/PySide6 and M0-CORE-006 runtime handshake.

## 11. Test matrix

- ports contain no concrete driver types;
- valid bootstrapped DB metadata read;
- WAL and FK enforcement;
- explicit commit lifecycle;
- normal uncommitted exit rollback;
- exception rollback;
- deterministic second-writer rejection;
- read UoW rejects writes;
- missing/unbootstrapped/non-WAL target fails closed;
- real disposable acceptance smoke;
- historical M0-STO-001 and architecture gates.

## 12. Completion criteria

M0-STO-002 may become COMPLETE only after task tests, regression gates, clean Git commit, final-HEAD re-verification, bundle creation, empty-directory clean clone, clean-clone critical gates, machine-readable evidence and delivery SHA-256 manifest are complete.

## 13. Completion evidence

- Disposable SQLite Repository acceptance: PASS (WAL, FK enforcement, read transaction, write commit, uncommitted rollback, exception rollback, single-writer rejection).
- Test inventory: 118 collected; unit 42/42 PASS, migration 25/25 PASS, contract 51/51 PASS by complete file partition.
- Historical Baseline/Canonical/Repository-policy/architecture/codegen/generated-governance/regenerate-diff/bootstrap gates: PASS.
- `uv lock --check --offline`: PASS; no dependency change required.
- Ruff 0.16.8 and mypy 2.3.1: NOT CLAIMED on this host because the exact tools are not installed/cached and network access is disabled.
- Windows CI certification: NOT CLAIMED.
