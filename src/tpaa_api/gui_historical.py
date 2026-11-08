"""G6 V01 Historical-overview HTTP adapter."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService, HistoricalOverviewError


def _error(exc: HistoricalOverviewError) -> JSONResponse:
    state = (
        exc.code
        if exc.code in {"CAPABILITY_DISABLED", "ADAPTER_UNAVAILABLE"}
        else "ERROR"
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "schema": "TPAA_G6_HISTORICAL_OVERVIEW_ERROR_V1",
            "state": state,
            "code": exc.code,
            "detail": exc.detail,
            "provenance": {
                "authority_id": "GUI_HISTORICAL_OVERVIEW_AUTHORITY",
                "core_baseline": "CB-1.14.0",
                "latest_fallback": False,
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


def register_gui_historical_routes(app: FastAPI, application: ApplicationService) -> None:
    """Register the G6 historical-overview route only when the capability is active."""

    if not isinstance(application, ApplicationService) or not application.has_historical_overview():
        return

    @app.get(
        "/api/v1/gui/historical-overview",
        operation_id="getGuiHistoricalOverview",
    )
    def historical_overview(request: Request) -> JSONResponse:
        params = request.query_params
        query = {
            "start_date": params.get("start_date", "1970-01-01"),
            "end_date": params.get("end_date", "2999-12-31"),
            "model": params.get("model", "ALL"),
            "training_type": params.get("training_type", "ALL"),
        }
        try:
            payload = application.historical_overview().overview(query)
        except HistoricalOverviewError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})
