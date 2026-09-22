"""FastAPI health/readiness/version transport for M0-API-002.

Controllers deliberately consume only ``tpaa_application``. They do not import Core,
Canonical, Repository, DB-driver, or GUI implementation packages and do not recompute
READY semantics.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService, RuntimeBaselineStatus


def _readiness_payload(runtime: RuntimeBaselineStatus) -> dict[str, object]:
    return {
        "status": runtime.readiness,
        "ready": runtime.ready,
        "mismatches": list(runtime.mismatches),
    }


def _version_payload(runtime: RuntimeBaselineStatus) -> dict[str, object]:
    return {
        "readiness": runtime.readiness,
        "expected": asdict(runtime.expected),
        "observed": asdict(runtime.observed),
    }


def create_app(application: ApplicationService) -> FastAPI:
    """Create the local/service HTTP adapter around an already-wired Application Service."""

    app = FastAPI(title="TPAA", version="0.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Process liveness only; it intentionally does not claim business readiness."""

        return {"status": "UP"}

    @app.get("/readiness")
    def readiness() -> JSONResponse:
        """Expose the Application-projected Core handshake with fail-closed HTTP status."""

        runtime = application.runtime_baseline_status()
        http_status = status.HTTP_200_OK if runtime.ready else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=http_status, content=_readiness_payload(runtime))

    @app.get("/version")
    def version() -> dict[str, object]:
        """Expose expected/observed runtime baseline/build identity for diagnostics."""

        return _version_payload(application.runtime_baseline_status())

    return app
