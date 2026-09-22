# M0-GUI-003 — Baseline/Diagnostics view

Status: **COMPLETE**

## Scope

Implement the SDIB-1.0 M0-GUI-003 view that can display Core, P1 Catalog, DB schema, product build, and readiness diagnostics in the Desktop profile. The view is deliberately read-only: it consumes the M0-CORE-006/M0-API-002 authority already surfaced through the GUI-owned local backend and must not recompute READY.

## Implemented behavior

1. `tpaa_gui.diagnostics.DiagnosticsSnapshot` is the GUI-owned sanitized view model.
2. The snapshot contains only readiness/lifecycle diagnostics plus expected/observed values for product build, Core baseline, P1 Metric Catalog version, and DB schema.
3. `LocalBackendController` captures authenticated `/readiness` and `/version` payloads during the existing M0-GUI-002 handshake and retains the non-secret snapshot after fail-closed shutdown.
4. Runtime child failure overlays `NOT_READY` plus the lifecycle failure code without changing the underlying Core mismatch list or identity values.
5. The PySide6 shell renders stable labels for readiness, lifecycle state/failure, mismatch codes, build, Core, Catalog, and schema.
6. A 500 ms Qt timer refreshes the rendered snapshot so a backend crash cannot leave a stale READY display.
7. A startup readiness mismatch is still fail-closed, but the Desktop shell is allowed to remain open in NOT_READY diagnostics mode after the child has been cleaned up.

## Frozen UI object names

- `tpaaDiagnosticsTitle`
- `tpaaDiagnosticsReadiness`
- `tpaaDiagnosticsBackendState`
- `tpaaDiagnosticsFailure`
- `tpaaDiagnosticsMismatches`
- `tpaaDiagnosticsBuild`
- `tpaaDiagnosticsCore`
- `tpaaDiagnosticsCatalog`
- `tpaaDiagnosticsSchema`

These names are intentionally stable inputs for M0-GUI-004; M0-GUI-003 itself does not implement an automation harness.

## Boundary guarantees

- No GUI import of `tpaa_canonical`, `tpaa_storage`, FastAPI, DB drivers, or the Core handshake evaluator.
- No bearer token in diagnostics snapshots, UI text, logs, or control responses.
- No GUI-side mismatch-code comparison or READY decision.
- No new dependency activation; the existing governed PySide6/FastAPI/Psycopg lock is unchanged.

## Acceptance

M0-GUI-003 is accepted with **210/210 PASS** (unit 89/89, migration 26/26, contract 95/95). Tests prove the required SDIB dimensions render, NOT_READY diagnostics remain fail-closed, backend crash revokes displayed readiness, stable UI object names exist, and all historical M0 gates remain green.

## Non-scope

M0-GUI-004 UI automation, service-profile auth/RBAC, packaging, build manifest/SBOM, cross-platform CI, and M0 Exit remain outside this task.
