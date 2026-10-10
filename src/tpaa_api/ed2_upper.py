"""Exact-ID HTTP read surface for ED-2 B3 upper products."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService


def _error(exc: Exception) -> JSONResponse:
    detail = str(exc)
    upper = detail.upper()
    code = (
        status.HTTP_404_NOT_FOUND
        if "NOT_FOUND" in upper or isinstance(exc, LookupError)
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return JSONResponse(
        status_code=code,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {
                "code": "ED2_UPPER_EXACT_READ_FAILED",
                "detail": detail,
            },
        },
    )


def register_ed2_upper_routes(
    app: FastAPI,
    application: ApplicationService,
) -> FastAPI:
    @app.get(
        "/api/v1/upper/{kind}",
        operation_id="listED2UpperProducts",
    )
    def list_upper(kind: str) -> dict[str, object] | JSONResponse:
        try:
            return application.ed2_upper_list(kind)
        except (LookupError, RuntimeError, ValueError) as exc:
            return _error(exc)

    @app.get(
        "/api/v1/upper/{kind}/{snapshot_id}",
        operation_id="getED2UpperProduct",
    )
    def exact_upper(
        kind: str,
        snapshot_id: UUID,
    ) -> dict[str, object] | JSONResponse:
        try:
            return application.ed2_upper_exact(
                snapshot_id=str(snapshot_id),
                expected_kind=kind,
            )
        except (LookupError, RuntimeError, ValueError) as exc:
            return _error(exc)

    return app
