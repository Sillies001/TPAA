"""M7 exact-twin-revision P3 FastAPI read transport."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M7ApplicationError,
    M7EstimateQuery,
    M7TwinQuery,
    M7WorkspaceQuery,
)

from .app import create_app


def _error(exc: M7ApplicationError) -> JSONResponse:
    if exc.code in {"M7_P3_TWIN_NOT_FOUND", "M7_P3_ESTIMATE_NOT_FOUND"}:
        status = 404
    elif exc.code == "M7_P3_NOT_ADMITTED":
        status = 423
    elif exc.code.endswith("_MISMATCH") or exc.code == "M7_P3_IMMUTABLE_CONFLICT":
        status = 409
    else:
        status = 422
    return JSONResponse(
        status_code=status,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {"code": exc.code, "detail": exc.detail},
        },
    )


def register_m7_routes(
    app: FastAPI,
    application: ApplicationService,
) -> FastAPI:
    """Register exact-revision, admission-gated P3 read routes."""

    @app.get("/m7/p3/twins/{twin_revision_id}")
    def twin(twin_revision_id: str) -> JSONResponse:
        try:
            payload = application.m7_p3_twin(
                M7TwinQuery(twin_revision_id=twin_revision_id)
            )
        except M7ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m7/p3/twins/{twin_revision_id}/estimates/{estimate_id}"
    )
    def estimate(
        twin_revision_id: str,
        estimate_id: str,
    ) -> JSONResponse:
        try:
            payload = application.m7_p3_estimate(
                M7EstimateQuery(
                    twin_revision_id=twin_revision_id,
                    estimate_id=estimate_id,
                )
            )
        except M7ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m7/p3/twins/{twin_revision_id}/estimates/{estimate_id}/workspace"
    )
    def workspace(
        twin_revision_id: str,
        estimate_id: str,
    ) -> JSONResponse:
        try:
            payload = application.m7_p3_workspace(
                M7WorkspaceQuery(
                    twin_revision_id=twin_revision_id,
                    estimate_id=estimate_id,
                )
            )
        except M7ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    return app


def create_m7_app(application: ApplicationService) -> FastAPI:
    """Extend stable transport with admission-gated exact P3 reads."""

    return register_m7_routes(create_app(application), application)
