"""G7 V26 Batch-events HTTP adapter."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService, BatchEventsError


def _error(exc: BatchEventsError) -> JSONResponse:
    state = (
        exc.code
        if exc.code in {"CAPABILITY_DISABLED", "ADAPTER_UNAVAILABLE"}
        else "ERROR"
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "schema": "TPAA_G7_BATCH_EVENTS_ERROR_V1",
            "state": state,
            "code": exc.code,
            "detail": exc.detail,
            "provenance": {
                "authority_id": "GUI_BATCH_EVENTS_AUTHORITY",
                "core_baseline": "CB-1.14.0",
                "latest_fallback": False,
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


def register_gui_batch_events_routes(app: FastAPI, application: ApplicationService) -> None:
    """Register the G7 batch-events route only when the capability is active."""

    if not isinstance(application, ApplicationService) or not application.has_batch_events():
        return

    @app.get(
        "/api/v1/gui/batches/{batch_id}/weapon-events",
        operation_id="getGuiBatchWeaponEvents",
    )
    def batch_events(batch_id: str, request: Request) -> JSONResponse:
        params = request.query_params
        request_id = request.headers.get("x-request-id", "g7-batch-events")
        try:
            payload = application.batch_events().workbench(
                batch_id,
                {
                    "category": params.get("category", "ALL"),
                    "adjudication": params.get("adjudication", "ALL"),
                    "cluster_id": params.get("cluster_id"),
                    "entity_id": params.get("entity_id"),
                    "episode_id": params.get("episode_id"),
                    "start_time_us": params.get("start_time_us"),
                    "end_time_us": params.get("end_time_us"),
                },
                cursor=params.get("cursor"),
                limit=int(params.get("limit", "25")),
                request_id=request_id,
            )
        except BatchEventsError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})
