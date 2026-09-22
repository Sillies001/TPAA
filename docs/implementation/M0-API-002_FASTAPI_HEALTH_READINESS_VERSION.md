# M0-API-002 — FastAPI health/readiness/version exposure

**Status:** COMPLETE
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

Dependency activation was completed in a clean Windows clone with CPython 3.13.5 and uv 0.12.17. `uv add "fastapi[standard-no-fastapi-cloud-cli]==0.141.1"` resolved the universal environment, `fastapi.__version__` reported `0.141.1`, and the resulting project/lock state was transferred byte-for-byte into the formal completion repository. The lock uses the official PyPI registry and contains no project-level mirror override.

## Completion acceptance evidence

- Windows governed environment: FastAPI `0.141.1` import/version PASS on CPython 3.13.5.
- Windows `api-smoke`: health PASS, readiness READY PASS, readiness NOT_READY/503 PASS, version PASS.
- Windows `uv lock --check`: PASS after resolving 42 packages.
- Dependency declaration is exact: `fastapi[standard-no-fastapi-cloud-cli]==0.141.1`.
- Universal `uv.lock` uses official `https://pypi.org/simple` sources and contains no Tsinghua/project-index pollution.
- API/Application specialty slice includes direct smoke execution without ambient `PYTHONPATH`.
- Controller boundary contract: no direct Canonical/Storage/GUI/driver import and no READY comparison implementation.
- Final regression: unit 68/68, migration 26/26, contract 69/69 = 163/163 PASS.
- Historical Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository/bootstrap/offline-lock gates PASS.
- Final local regression and historical gates are recorded in `M0-API-002_COMPLETE_EVIDENCE.json`.

## Completion gate

All completion conditions are satisfied:

1. `pyproject.toml` and the single universal `uv.lock` contain the exact FastAPI 0.141.1 activation without project-index pollution.
2. Governed Windows import/version reports `0.141.1`.
3. Governed Windows `api-smoke` passes for health, READY, NOT_READY/503 and version.
4. Unit/migration/contract regression and historical Baseline/Canonical/generated/architecture/Repository/bootstrap/lock gates pass.
5. COMPLETE status and clean-clone verification are recorded.

## Explicit non-scope

- M0-API-003 Critical DTO/OpenAPI exact-parity snapshot;
- authentication/token policy and ADR-M0-005 Desktop IPC/lifecycle decisions;
- PySide6 shell or GUI-backend process lifecycle;
- business job endpoints;
- M0-DEV-003 build manifest generation;
- M0 Exit or platform certification.
