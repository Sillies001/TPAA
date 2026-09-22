# ADR-M0-005 Desktop Backend Lifecycle / IPC Study

**Status:** COMPLETE — decision frozen by ADR-M0-005  
**Authority:** SDIB-1.0 §9, §33, §39 step 7  
**Decision artifact:** `docs/adr/ADR-M0-005-desktop-backend-lifecycle-ipc.md`

## Problem

SDIB step 7 requires a PySide6 Desktop shell to own a local FastAPI backend and reach READY only after the governed runtime baseline handshake succeeds. Before GUI lifecycle code is written, M0 must freeze process ownership, port selection, token transfer, startup handshake, crash behavior and shutdown semantics so implementation does not accidentally define architecture.

## Constraints extracted from SDIB

- Desktop backend is loopback-only.
- A random bearer token is required.
- Origin/path exposure is controlled.
- Tokens/credentials do not enter logs, fixtures, build manifests or diagnostic payloads.
- GUI/REST use Application services rather than Repository/business-layer bypasses.
- Backend crash or baseline/version mismatch must fail closed and not become READY.
- Windows and Linux behavior must share one logical lifecycle contract.

## Evaluated lifecycle shapes

### In-process server thread

Smallest process count, but rejected because Qt/server lifetime becomes coupled and crash isolation is lost. It also increases the temptation to bypass the HTTP/Application boundary with direct Python object access.

### Child process with fixed port

Simple configuration, but rejected because fixed ports collide across parallel instances and make accidental attachment to stale/unowned processes more likely.

### Child process with parent-side free-port probing

Portable but racy: after the probe socket closes, another process can take the selected port before the backend binds.

### Child process with child-owned ephemeral bind

Selected. The serving process binds `127.0.0.1:0`, learns the OS-selected port and reports it only after successful bind. This removes the probe/rebind race and supports multiple independent Desktop instances.

## Selected control/data split

- **Lifecycle control plane:** private parent/child stdio NDJSON.
- **Application transport:** authenticated loopback HTTP.

The split keeps process ownership commands narrower than the HTTP API. The GUI sends startup secret/configuration and later SHUTDOWN through stdin; the child emits non-secret lifecycle records over stdout. HTTP routes are never used to grant process ownership.

## Token handling

The GUI creates 32 random bytes through Python `secrets` and URL-safe encodes them. This provides a per-process capability token without adding a secret-management dependency. The token is memory-only and moves to the child only via the startup stdin record. HTTP uses the standard bearer header, and implementation must compare credentials in constant time.

## Shutdown evidence

Python documents that `Popen.terminate()` is SIGTERM on POSIX but Win32 `TerminateProcess()` on Windows. Normal lifecycle therefore cannot rely on terminate as if it guaranteed graceful cleanup. The selected protocol requests shutdown cooperatively over the private control channel first, with bounded terminate/kill fallback for a wedged child.

## Decision-to-task mapping

- **M0-GUI-001:** activate PySide6 and create the application shell; no backend lifecycle shortcut.
- **M0-GUI-002:** implement this child/control/token/READY/shutdown protocol and failure fixtures.
- **M0-GUI-003:** display readiness plus Core/Catalog/schema/build diagnostics supplied by Application/API.
- **M0-GUI-004:** automate start → READY → close and crash/mismatch cases.

## Non-decisions retained

This ADR does not choose packaging (ADR-M0-006), structured logging library (ADR-M0-008), object/Parquet layout (ADR-M0-009) or SBOM tooling (ADR-M0-010). It also does not define Service-profile authentication/RBAC.

## Closure verification

ADR closure regression on the implementation host:

- unit: 68/68 PASS;
- migration: 26/26 PASS;
- contract: 78/78 PASS;
- total: 172/172 PASS by complete collected-test partition;
- Baseline exact, Canonical loader, codegen check, generated verification, regenerate-diff, architecture, Repository policy, Desktop lifecycle policy, bootstrap check-only, API smoke and `uv lock --check --offline`: PASS.

Not claimed by ADR closure: PySide6 runtime availability, Windows/Linux Desktop start/exit smoke, child crash recovery, packaged-process behavior, Ruff/mypy execution or cross-platform CI. Those remain implementation/platform gates.
