# Architecture Decision Records

SDIB-1.0 requires ADR-M0-001 through ADR-M0-010 during M0. Decisions are not implied by code; each ADR must carry status, owner role, decision, alternatives and evidence.

## Closed

- [ADR-M0-001 — Python runtime baseline](ADR-M0-001-python-runtime-baseline.md) — **CLOSED**, CPython 3.13.x on all governed Windows/Linux x64 profiles.
- [ADR-M0-002 — Dependency resolver / lock](ADR-M0-002-dependency-resolver-lock.md) — **CLOSED**, uv + one universal `uv.lock`.
- [ADR-M0-003 — Static quality toolchain](ADR-M0-003-static-quality-toolchain.md) — **CLOSED**, Ruff + mypy + pytest through the unified developer dispatcher.

## Still required before M0 Exit

ADR-M0-004 through ADR-M0-010 remain **OPEN / NOT YET DECIDED**. No implementation may silently turn one of those undecided topics into a de-facto standard.
