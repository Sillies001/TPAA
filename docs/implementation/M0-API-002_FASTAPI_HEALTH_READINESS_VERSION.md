# M0-API-002 — FastAPI health/readiness/version exposure

**Status:** IN PROGRESS  
**Workstream:** WS-API  
**Authority:** SDIB-1.0 §17, §39 step 7, Appendix E and Appendix Q

## Objective

Expose the completed M0-CORE-006 runtime baseline handshake through a minimal FastAPI transport without moving READY comparison rules into HTTP controllers. The acceptance target is a smoke-tested `health/readiness/version` surface for local/service use.

## Implemented slice

1. `tpaa_application.runtime` projects the Core-owned `RuntimeBaselineHandshake` into transport-neutral Application models. It does not call `evaluate_runtime_baseline_handshake` and does not contain mismatch comparison rules.
2. `ApplicationService.runtime_baseline_status()` is the sole API-facing entry point for runtime readiness/version diagnostics.
3. `tpaa_api.create_app()` creates the FastAPI adapter and imports only `tpaa_application` from first-party runtime packages.
4. `GET /health` is liveness-only and returns HTTP 200 / `UP`; it deliberately makes no READY claim.
5. `GET /readiness` returns HTTP 200 for authoritative `READY` and HTTP 503 for authoritative `NOT_READY`, preserving Core mismatch codes unchanged.
6. `GET /version` exposes the expected and observed build/Core/Baseline-Lock/schema/P1-Catalog/DTO identity projected by Application for diagnostics.
7. `api-smoke` executes real ASGI/TestClient requests for liveness, READY, NOT_READY and version diagnostics and self-bootstraps `src/` on `sys.path` so direct execution from a clean checkout does not depend on ambient `PYTHONPATH`.

## Framework dependency decision for this task

The selected activation target is:

`fastapi[standard-no-fastapi-cloud-cli]==0.141.1`

Rationale:

- 0.141.1 is the current PyPI release verified during this task and supports Python 3.13.
- the official `standard-no-fastapi-cloud-cli` extra supplies the local server/TestClient standard stack (including Uvicorn/HTTPX) without admitting the unrelated FastAPI Cloud deployment client.
- ADR-M0-002 still requires the declaration and universal `uv.lock` to change together.

The Chat execution host cannot resolve `pypi.org`, so dependency activation is deliberately **not committed yet**. The host has FastAPI 0.128.2/HTTPX 0.28.1 preinstalled, which is sufficient only for implementation smoke during this checkpoint and is not claimed as the governed project dependency.

## Current acceptance evidence

- API/Application specialty slice: 12/12 PASS on the Chat host, including direct smoke execution without ambient `PYTHONPATH`.
- `api-smoke`: PASS for health, READY, NOT_READY/503 and version endpoints.
- Controller boundary contract: no direct Canonical/Storage/GUI/driver import and no READY comparison implementation.
- Formal FastAPI 0.141.1 lock activation: PENDING external networked `uv add` and subsequent frozen-lock verification.

## Completion gate

M0-API-002 may move to COMPLETE only after all of the following are true:

1. `uv add "fastapi[standard-no-fastapi-cloud-cli]==0.141.1"` updates `pyproject.toml` and the single universal `uv.lock` without project-index pollution.
2. `uv run python -c "import fastapi; print(fastapi.__version__)"` reports `0.141.1`.
3. `uv run python tools/dev/tpaa_dev.py api-smoke` passes in the governed environment.
4. Unit/contract regression and historical Baseline/Canonical/generated/architecture/Repository/bootstrap/lock gates pass.
5. Documentation/status is switched from IN PROGRESS to COMPLETE and a clean-clone verification is recorded.

## Explicit non-scope

- M0-API-003 Critical DTO/OpenAPI exact-parity snapshot;
- authentication/token policy and ADR-M0-005 Desktop IPC/lifecycle decisions;
- PySide6 shell or GUI-backend process lifecycle;
- business job endpoints;
- M0-DEV-003 build manifest generation;
- M0 Exit or platform certification.
