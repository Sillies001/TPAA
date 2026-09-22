# Architecture Decision Records

SDIB-1.0 requires ADR-M0-001 through ADR-M0-010 during M0. Decisions are not implied by code; each ADR must carry status, owner role, decision, alternatives and evidence.

## Closed

- [ADR-M0-001 — Python runtime baseline](ADR-M0-001-python-runtime-baseline.md) — **CLOSED**, CPython 3.13.x on all governed Windows/Linux x64 profiles.
- [ADR-M0-002 — Dependency resolver / lock](ADR-M0-002-dependency-resolver-lock.md) — **CLOSED**, uv + one universal `uv.lock`.
- [ADR-M0-003 — Static quality toolchain](ADR-M0-003-static-quality-toolchain.md) — **CLOSED**, Ruff + mypy + pytest through the unified developer dispatcher.

## Closed during Repository technology freeze

- [ADR-M0-004 — Repository DB access implementation](ADR-M0-004-repository-db-access-implementation.md) — **CLOSED**, synchronous explicit-SQL adapters: stdlib sqlite3 for Desktop, Psycopg 3 for Service, engine-neutral Repository/UoW ports, Alembic confined to migration tooling.

## Closed during M0-CORE-004

- [ADR-M0-007 — Generated-source policy](ADR-M0-007-generated-source-policy.md) — **CLOSED**, checked-in generated source with vendor-neutral regenerate-diff enforcement.

## Still required before M0 Exit

ADR-M0-005, ADR-M0-006, ADR-M0-008, ADR-M0-009 and ADR-M0-010 remain **OPEN / NOT YET DECIDED**. No implementation may silently turn one of those undecided topics into a de-facto standard.
