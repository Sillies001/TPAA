# ADR-M0-005 — Desktop Backend Lifecycle / IPC

- **Status:** CLOSED
- **Decision date:** 2026-09-22
- **Owner role:** WS-GUI / WS-API technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §9, §17, §33, §39 step 7; Appendix E/Q
- **Evidence study:** `docs/implementation/ADR-M0-005_DESKTOP_BACKEND_LIFECYCLE_STUDY.md`
- **Machine policy:** `tools/desktop/DESKTOP_BACKEND_LIFECYCLE_POLICY.json`

## Decision

TPAA freezes the Desktop local-backend lifecycle as a **GUI-owned, isolated child process with private stdio control IPC and authenticated loopback HTTP data/control-plane access**:

1. One PySide6 GUI process owns exactly one local FastAPI backend child process. The backend does not run in the GUI process/thread, and the GUI must not silently attach to an unowned pre-existing backend.
2. The child binds **IPv4 loopback `127.0.0.1` only** and asks the OS for an ephemeral port by binding port `0`. Fixed Desktop ports, non-loopback binds, `localhost` hostname ambiguity, and “find a free port then close/rebind” probing are forbidden.
3. The GUI generates a fresh bearer token for each backend process using `secrets.token_urlsafe(32)` (32 random bytes before URL-safe encoding). The token exists only in memory for that child lifetime.
4. The token is delivered to the child in the initial private stdin control record. It must not appear in command-line arguments, environment variables, files, stdout control responses, logs, fixtures, build manifests, query strings, cookies or persisted settings.
5. Parent/child lifecycle IPC is newline-delimited JSON over dedicated stdio: parent→child on stdin, child→parent on stdout. Stdout is reserved for lifecycle control records and is not a logging stream. Logging selection/format remains owned by ADR-M0-008.
6. After it has successfully bound the listener, the child emits a non-secret `LISTENING` control record containing protocol version, PID and actual port. The GUI then performs authenticated `GET /readiness` and `GET /version`; READY requires M0-CORE-006/M0-API-002 readiness to return HTTP 200. A mismatch, timeout, malformed control record or child exit is fail-closed NOT_READY.
7. Desktop-profile HTTP requires `Authorization: Bearer <token>` on every route. Token equality uses constant-time comparison. Interactive docs/OpenAPI routes and CORS are disabled in the Desktop profile; unexpected `Origin` headers are rejected unless a later explicit allowlist decision permits them.
8. Normal shutdown uses a private `SHUTDOWN` stdin control record, not an HTTP shutdown route. The parent waits up to 5 seconds for graceful child exit; only then may it use process termination, wait 2 further seconds, and finally force-kill if required. Forced termination is failure recovery, not the normal lifecycle.
9. If the backend exits or the control channel closes unexpectedly, GUI readiness becomes false immediately and the GUI must stop issuing backend requests until an explicit new child lifecycle is established.
10. This decision applies only to the **Desktop local-backend profile**. Service deployment transport identity/RBAC and network exposure are separate concerns and must not reuse this ephemeral Desktop bearer token as a service authentication design.

## Rationale

A separate child process preserves the architectural rule that PySide6 is a transport/UI shell rather than a host for Storage or business logic. It also gives crash isolation and makes the Desktop backend behave like the Service API at the Application boundary without forcing the GUI to understand repositories.

Loopback plus an OS-assigned ephemeral port avoids fixed-port collisions and avoids the race created by probing a free port in one process and rebinding it later in another. The backend that will serve requests owns the listening socket before reporting the selected port.

A per-process bearer token protects the loopback service from unrelated local processes accidentally or opportunistically invoking it. The token is carried as an HTTP Bearer credential because FastAPI directly supports the standard `Authorization: Bearer` pattern. The token is deliberately transferred over the already-private parent/child stdin channel instead of argv or environment so it is not normal process metadata.

The normal shutdown path is cooperative because Python's subprocess semantics are materially different across Windows and POSIX: on Windows `Popen.terminate()` calls `TerminateProcess()`, which does not provide a graceful application cleanup path. Therefore terminate/kill are bounded recovery fallbacks only.

## Startup protocol

The concrete M0-GUI-002 implementation must preserve this state sequence:

`SPAWNED → CONFIG_SENT → LISTENING → HTTP_HANDSHAKE → READY`

Any invalid transition, timeout, process exit, token failure or M0-CORE-006 mismatch transitions to `NOT_READY` and requires lifecycle cleanup before a new start attempt.

The first parent control record carries startup configuration plus the bearer token. The child's `LISTENING` response is non-secret. The GUI must not treat the control record alone as READY; READY is the authenticated HTTP readiness result backed by the Core handshake authority.

## Shutdown protocol

Normal close sequence:

`READY/NOT_READY → SHUTDOWN_SENT → EXITED`

If the child does not exit within 5 seconds, the GUI may terminate it and wait 2 seconds. If it still exists, the GUI may force-kill it. The GUI must record the forced-shutdown reason through the future ADR-M0-008 logging interface, without recording the token.

## Alternatives considered

### FastAPI/Uvicorn in a GUI thread

Rejected. It couples event-loop/server lifetime to Qt internals, weakens crash isolation, and makes accidental direct in-process access to backend objects easier.

### Fixed localhost port

Rejected. It creates collision/multi-instance problems and encourages reconnecting to a backend not owned by the current GUI process.

### Parent probes a free port, closes it, then starts backend on that number

Rejected because the interval between probe close and child bind creates a race. The child must bind port `0` itself and report the actual port only after successful bind.

### Token in command line or environment

Rejected because secrets would become ordinary process launch metadata and are more likely to appear in diagnostics. The private stdin bootstrap record has a narrower exposure surface.

### HTTP shutdown endpoint

Rejected for the Desktop profile. A dedicated parent-child control channel already exists and is the more constrained shutdown authority. HTTP remains the authenticated Application transport, not the process-ownership control channel.

### `terminate()` as normal shutdown

Rejected. On Windows Python maps it to `TerminateProcess()`, so cleanup/finally semantics cannot be treated as graceful lifecycle behavior.

## Dependency consequences

Closing ADR-M0-005 **does not activate PySide6** and does not add a new runtime dependency. M0-GUI-001 owns PySide6 dependency activation through the governed `uv.lock`. M0-GUI-002 implements this lifecycle protocol using stdlib process/IPC primitives plus the already-governed FastAPI local backend.

The M0-API-002 base transport may remain reusable for Service tests. Desktop-profile bearer enforcement/docs/CORS restrictions are applied when the local Desktop backend entry point is created; this ADR does not redefine Service authentication.

## Verification / evidence

- `tools/desktop/DESKTOP_BACKEND_LIFECYCLE_POLICY.json`
- `tools/desktop/verify_desktop_lifecycle_policy.py`
- `tests/contract/test_adr_m0_005_desktop_backend_lifecycle.py`
- `docs/implementation/ADR-M0-005_DESKTOP_BACKEND_LIFECYCLE_STUDY.md`
- SDIB security minimum: Desktop backend loopback-only, random bearer token, controlled origin/path behavior, and no token/credential in logs/fixtures/build manifests.
- Python subprocess documentation confirms `Popen.terminate()` sends SIGTERM on POSIX but calls `TerminateProcess()` on Windows, so forced termination cannot be the normal cross-platform graceful-shutdown mechanism.
- FastAPI provides standard HTTP Bearer extraction through `fastapi.security.HTTPBearer`; implementation must still compare the configured Desktop token rather than merely checking that a bearer header exists.

## Reopen conditions

Reopen if:

- Windows/Linux M0-GUI lifecycle tests show stdio control IPC is not robust under the governed packaging model;
- the one-child-per-GUI ownership model prevents a required multi-window/multi-process workflow;
- platform security evidence requires stronger local IPC than loopback HTTP + private control pipe;
- FastAPI/Uvicorn lifecycle changes make the child bind/report sequence impractical;
- a future embedded browser UI requires an explicit CORS/origin policy broader than the native PySide6 profile.
