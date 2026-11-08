"""G8 V24 Co-attack HTTP adapter."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService, CoAttackError


def _error(exc: CoAttackError) -> JSONResponse:
    state = (
        exc.code
        if exc.code in {"CAPABILITY_DISABLED", "ADAPTER_UNAVAILABLE"}
        else "ERROR"
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "schema": "TPAA_G8_CO_ATTACK_ERROR_V1",
            "state": state,
            "code": exc.code,
            "detail": exc.detail,
            "provenance": {
                "authority_id": "GUI_CO_ATTACK_AUTHORITY",
                "core_baseline": "CB-1.14.0",
                "latest_fallback": False,
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


def register_gui_co_attack_routes(app: FastAPI, application: ApplicationService) -> None:
    """Register the G8 co-attack route only when the capability is active."""

    if not isinstance(application, ApplicationService) or not application.has_co_attack():
        return

    @app.get(
        "/api/v1/gui/attack-clusters/{cluster_id}/co-attack-analysis",
        operation_id="getGuiCoAttackAnalysis",
    )
    def co_attack(cluster_id: str, request: Request) -> JSONResponse:
        request_id = request.headers.get("x-request-id", "g8-co-attack")
        try:
            payload = application.co_attack().analysis(
                cluster_id,
                {"context_id": request.query_params.get("context_id")},
                request_id=request_id,
            )
        except CoAttackError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})
