"""M6 exact-release P2 comparison/diagnostics FastAPI transport."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M6ApplicationError,
    M6P2ComparisonQuery,
    M6P2DiagnosticsQuery,
)

from .app import create_app


def _error(exc: M6ApplicationError) -> JSONResponse:
    if exc.code == "M6_P2_ESTIMATE_NOT_FOUND":
        status = 404
    elif exc.code.endswith("_MISMATCH") or exc.code == "M6_P2_IMMUTABLE_CONFLICT":
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


def register_m6_routes(
    app: FastAPI,
    application: ApplicationService,
) -> FastAPI:
    """Register exact-release read-only P2 workspace routes."""

    @app.get(
        "/m6/p2/releases/{p2_release_id}/estimates/{estimate_id}/comparison"
    )
    def comparison(
        p2_release_id: str,
        estimate_id: str,
    ) -> JSONResponse:
        try:
            payload = application.m6_p2_comparison(
                M6P2ComparisonQuery(
                    p2_release_id=p2_release_id,
                    estimate_id=estimate_id,
                )
            )
        except M6ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m6/p2/releases/{p2_release_id}/estimates/{estimate_id}/diagnostics"
    )
    def diagnostics(
        p2_release_id: str,
        estimate_id: str,
    ) -> JSONResponse:
        try:
            payload = application.m6_p2_diagnostics(
                M6P2DiagnosticsQuery(
                    p2_release_id=p2_release_id,
                    estimate_id=estimate_id,
                )
            )
        except M6ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    return app


def create_m6_app(application: ApplicationService) -> FastAPI:
    """Extend the stable local transport with release-bound M6 P2 read routes."""

    return register_m6_routes(create_app(application), application)
