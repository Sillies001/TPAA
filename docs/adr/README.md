# Architecture Decision Records

SDIB-1.0 requires ADR-M0-001 through ADR-M0-010 during M0. Decisions are not implied by code; each ADR must carry status, owner role, decision, alternatives and evidence.

## Closed

- [ADR-M0-001 — Python runtime baseline](ADR-M0-001-python-runtime-baseline.md) — **CLOSED**, CPython 3.13.x on all governed Windows/Linux x64 profiles.
- [ADR-M0-002 — Dependency resolver / lock](ADR-M0-002-dependency-resolver-lock.md) — **CLOSED**, uv + one universal `uv.lock`.
- [ADR-M0-003 — Static quality toolchain](ADR-M0-003-static-quality-toolchain.md) — **CLOSED**, Ruff + mypy + pytest through the unified developer dispatcher.

## Closed during Repository technology freeze

- [ADR-M0-004 — Repository DB access implementation](ADR-M0-004-repository-db-access-implementation.md) — **CLOSED**, synchronous explicit-SQL adapters: stdlib sqlite3 for Desktop, Psycopg 3 for Service, engine-neutral Repository/UoW ports, Alembic confined to migration tooling.

## Closed before Desktop lifecycle implementation

- [ADR-M0-005 — Desktop backend lifecycle / IPC](ADR-M0-005-desktop-backend-lifecycle-ipc.md) — **CLOSED**, GUI-owned isolated local backend child, loopback ephemeral listener, private stdio lifecycle control and per-process bearer token.

## Closed during M0-CORE-004

- [ADR-M0-007 — Generated-source policy](ADR-M0-007-generated-source-policy.md) — **CLOSED**, checked-in generated source with vendor-neutral regenerate-diff enforcement.

## Closed during SDIB §39 Step 10

- [ADR-M0-006 — Packaging](ADR-M0-006-packaging.md) — **CLOSED**, M0 development bundles are profile-specific deterministic source/runtime archives; formal installer qualification remains M5.
- [ADR-M0-008 — Structured logging / telemetry](ADR-M0-008-structured-logging-telemetry.md) — **CLOSED**, TPAA-owned stdlib logging facade with NDJSON machine records and strict business/log-time separation.
- [ADR-M0-009 — Local object / Parquet layout](ADR-M0-009-local-object-parquet-layout.md) — **CLOSED**, logical URI identity separated from configurable physical roots with Unicode/case safety.
- [ADR-M0-010 — SBOM / license tooling](ADR-M0-010-sbom-license-tooling.md) — **CLOSED**, repository-controlled CycloneDX 1.6 SBOM plus explicit license/native dependency inventories.

All ADR-M0-001 through ADR-M0-010 are now CLOSED. Reopen conditions remain defined by each ADR.
