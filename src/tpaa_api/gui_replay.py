"""G9 V03 Replay HTTP adapter."""

from __future__ import annotations

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService, ReplayContextError


def _error(exc: ReplayContextError) -> JSONResponse:
    state = (
        exc.code
        if exc.code in {"CAPABILITY_DISABLED", "ADAPTER_UNAVAILABLE"}
        else "ERROR"
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "schema": "TPAA_G9_REPLAY_ERROR_V1",
            "state": state,
            "code": exc.code,
            "detail": exc.detail,
            "provenance": {
                "authority_id": "GUI_REPLAY_AUTHORITY",
                "core_baseline": "CB-1.14.0",
                "latest_fallback": False,
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


def register_gui_replay_routes(app: FastAPI, application: ApplicationService) -> None:
    """Register the G9 replay-context route only when the capability is active."""

    if not isinstance(application, ApplicationService) or not application.has_replay_context():
        return

    @app.get(
        "/api/v1/gui/weapon-events/{weapon_event_id}/replay-context",
        operation_id="getGuiWeaponEventReplayContext",
    )
    def replay_context(
        weapon_event_id: str,
        request: Request,
        release_id: str = Query(min_length=1),
        context_id: str = Query(min_length=1),
        perspective: str = Query(pattern="^(shooter|target)$"),
    ) -> JSONResponse:
        request_id = request.headers.get("x-request-id", "g9-replay")
        try:
            payload = application.replay_context().context(
                weapon_event_id,
                request_id=request_id,
                release_id=release_id,
                context_id=context_id,
                perspective=perspective,
            )
        except ReplayContextError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})
