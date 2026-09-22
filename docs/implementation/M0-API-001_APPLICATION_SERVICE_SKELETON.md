# M0-API-001 — Application Service skeleton

**Status:** COMPLETE  
**Workstream:** WS-API  
**Authority:** SDIB-1.0 §7.1, §12, §17, §39 and Appendix E

## Objective

Establish `tpaa_application` as the only business-entry boundary for future REST and GUI transports. The task must not select FastAPI/PySide6 lifecycle details, database dialects, or complete the runtime READY/version handshake owned by M0-CORE-006.

## Implemented boundary

1. `tpaa_application.ports.RepositoryUnitOfWorkFactory` consumes only the engine-neutral `tpaa_storage.ports.RepositoryUnitOfWork` contract.
2. `GetStorageBaselineStatus` is the first concrete Application use case. It reads persisted bootstrap provenance through the Repository port and projects it into an Application-owned immutable result model.
3. `ApplicationService` is the typed transport-facing facade. Future `tpaa_api` and `tpaa_gui` code must call Application use cases/facade rather than Repository or Domain implementations directly.
4. The use case is read-only by behavior: it does not call `commit()` and relies on the UoW exit semantics established by ADR-M0-004.
5. No concrete SQLite/PostgreSQL adapter, SQL, driver type, FastAPI, Starlette, or Qt type appears in the Application boundary.

## Architecture enforcement

Appendix E is encoded more strictly for the two transport packages:

- `tpaa_api` may depend on first-party `tpaa_application` and `tpaa_generated` only;
- `tpaa_gui` may depend on first-party `tpaa_application` and `tpaa_generated` only.

The existing architecture verifier enforces these import edges in CI/local gates.

## Acceptance evidence

- Application unit/contract slice: 5/5 PASS.
- Real SQLite integration: M0-STO-001 bootstrap → SQLite Repository UoW → `ApplicationService.storage_baseline_status()` returns schema `1.6.0`, Core baseline `CB-1.4.0`, and Canonical authority id `CORE_LOGICAL_MODEL`.
- Architecture dependency verifier: PASS, zero violations after tightening transport edges.
- Final regression: unit 50/50, migration 26/26, contract 62/62; total 138/138 PASS by complete partition.
- Historical Baseline/Canonical/codegen/generated/regenerate-diff/Repository-policy/bootstrap/lock gates: PASS.

## Explicit non-scope

This task does **not** claim:

- M0-CORE-006 READY/version mismatch semantics;
- M0-API-002 FastAPI endpoints;
- M0-GUI-001 PySide6 application shell;
- ADR-M0-005 Desktop backend lifecycle/IPC decisions;
- job submission/query/cancel business behavior;
- M0 Exit or P1 capability completion.

## Next dependency

Per SDIB-1.0 §39 step 7, the next dependency is **M0-CORE-006 runtime baseline handshake model** so that later FastAPI readiness/version endpoints and GUI lifecycle handshake consume one Application/Core readiness authority rather than invent transport-local rules.
