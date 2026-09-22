# M0-GUI-002 — Local backend lifecycle handshake

Status: **IN PROGRESS**

## Objective

Implement ADR-M0-005 as executable Desktop lifecycle behavior without moving business or Storage logic into PySide6. One GUI process owns one isolated local FastAPI child; READY is reached only after a private stdio control handshake and authenticated M0-CORE-006/M0-API-002 HTTP readiness/version confirmation.

## Implemented vertical slice

- `tpaa_gui.local_backend.LocalBackendController` owns exactly one child process.
- A fresh `secrets.token_urlsafe(32)` bearer secret is generated for each child lifecycle and sent only in the first stdin NDJSON `START` record.
- The child entry point is `tpaa_api.local_backend_child`; it binds `127.0.0.1:0` itself and emits a non-secret `LISTENING` record containing PID and actual port.
- `tpaa_api.create_desktop_app` requires the exact bearer token on every defined route using constant-time comparison, disables docs/OpenAPI, installs no CORS middleware, and rejects any `Origin` header.
- The parent never treats `LISTENING` as READY. It performs authenticated `GET /readiness` and `GET /version`; any mismatch/non-200/child exit/timeout is fail-closed.
- `python -m tpaa_gui` now composes the existing PySide6 shell with the owned local-backend lifecycle.
- Normal shutdown writes private `SHUTDOWN` over stdin and waits 5 seconds before bounded terminate (2 seconds) and final kill fallback.
- `desktop-backend-smoke` performs a real child spawn, ephemeral-port handshake, bearer-negative probe and graceful cleanup.
- Windows virtual-environment launch bypasses CPython's venv redirector: the controller directly spawns `sys._base_executable` with `__PYVENV_LAUNCHER__` pointing at the governed venv interpreter. This preserves venv package resolution while keeping `Popen.pid == LISTENING.pid`, so owned-child PID enforcement and terminate/kill fallback target the real backend Python process.

## Architecture boundary

`tpaa_gui` uses stdlib process/control/HTTP primitives and does not import `tpaa_api`, Canonical, Storage, DB drivers, FastAPI or HTTPX. The child executable lives at the API adapter edge and consumes Application-owned runtime wiring; the API child does not import Canonical directly.

## Acceptance status

Current host evidence:

- real local child spawn/listen/authenticated READY/version handshake: **PASS**;
- unauthenticated Desktop HTTP rejected: **PASS**;
- mismatch fixture remains NOT_READY: **PASS**;
- backend crash immediately revokes GUI readiness: **PASS**;
- cooperative shutdown and cleanup: **PASS**;
- architecture import gate: **PASS**.

Checkpoint regression: unit **83/83 PASS**, migration **26/26 PASS**, contract **90/90 PASS**, total **199/199 PASS**. Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository-policy/Desktop-lifecycle-policy/bootstrap/API-smoke/Desktop-backend-smoke/offline-lock gates are PASS on the current host.

The first Windows real-process acceptance run correctly failed closed with `LISTENING_PID_MISMATCH`: CPython's Windows venv launcher inserted a redirector process, so `Popen.pid` named the redirector while the backend reported the real interpreter PID. The checkpoint now bypasses that redirector using the same `sys._base_executable` + `__PYVENV_LAUNCHER__` pattern used by CPython's Windows process-launch support, without weakening the PID equality check. A Windows rerun of `desktop-backend-smoke` is still required before marking this task COMPLETE.

## Explicit non-scope

M0-GUI-002 does not implement the M0-GUI-003 diagnostics view, M0-GUI-004 UI automation, service-profile authentication/RBAC, ADR-M0-008 logging selection, packaging, build manifest, or CI matrix.
