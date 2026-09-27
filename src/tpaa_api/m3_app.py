"""M3 release-bound Metric/Evidence FastAPI query transport."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M3MetricNotFound,
    M3PublicationError,
    M3ReleaseNotFound,
    M3WorkspaceProjectionError,
)

from .app import create_app


def _m3_error(\n    exc: M3PublicationError | M3WorkspaceProjectionError,\n) -> JSONResponse:
    if isinstance(exc, M3ReleaseNotFound):
        code = "RELEASE_NOT_FOUND"
        detail = exc.release_id
        http_status = 404
    elif isinstance(exc, M3MetricNotFound):
        code = "METRIC_NOT_FOUND"
        detail = exc.metric_code
        http_status = 404
    elif isinstance(exc, M3WorkspaceProjectionError):
        code = exc.code
        detail = exc.detail
        http_status = 409
    else:
        code = "M3_QUERY_ERROR"
        detail = str(exc)
        http_status = 422
    return JSONResponse(
        status_code=http_status,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {"code": code, "detail": detail},
        },
    )


def register_m3_routes(app: FastAPI, application: ApplicationService) -> FastAPI:
    """Register M3 Release-ID-bound query routes over Application projections."""

    @app.get("/m3/releases/{release_id}")
    def get_release(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.m3_release(release_id),
            )
        except M3PublicationError as exc:
            return _m3_error(exc)

    @app.get("/m3/releases/{release_id}/workspace")
    def get_workspace(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.m3_workspace(release_id),
            )
        except (M3PublicationError, M3WorkspaceProjectionError) as exc:
            return _m3_error(exc)

    @app.get("/m3/releases/{release_id}/metrics")
    def get_metrics(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content={
                    "release_id": release_id,
                    "items": application.m3_metrics(release_id),
                },
            )
        except M3PublicationError as exc:
            return _m3_error(exc)

    @app.get("/m3/releases/{release_id}/metrics/{metric_code}")
    def get_metric(release_id: str, metric_code: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.m3_metric(release_id, metric_code),
            )
        except M3PublicationError as exc:
            return _m3_error(exc)

    @app.get("/m3/releases/{release_id}/metrics/{metric_code}/evidence")
    def get_metric_evidence(release_id: str, metric_code: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.m3_metric_evidence(release_id, metric_code),
            )
        except M3PublicationError as exc:
            return _m3_error(exc)

    return app


def create_m3_app(application: ApplicationService) -> FastAPI:
    """Extend stable M0 transport with M3 release-bound query endpoints."""

    return register_m3_routes(create_app(application), application)
