"""PIQB product-runtime API projections layered above the stable base API."""

from __future__ import annotations

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, Response

from tpaa_application import ApplicationService


def register_product_runtime_routes(
    app: FastAPI,
    application: ApplicationService,
) -> FastAPI:
    """Register PIQB product-only runtime diagnostics without mutating M0 OpenAPI."""

    @app.get("/runtime/features")
    def runtime_features() -> JSONResponse:
        try:
            payload = application.feature_availability()
        except RuntimeError as exc:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {
                        "code": "FEATURE_AVAILABILITY_NOT_CONFIGURED",
                        "detail": str(exc),
                    },
                },
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    @app.get("/runtime/qualification")
    def runtime_qualification() -> JSONResponse:
        try:
            payload = application.qualification_status()
        except RuntimeError as exc:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {
                        "code": "QUALIFICATION_STATUS_NOT_CONFIGURED",
                        "detail": str(exc),
                    },
                },
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    @app.get("/runtime/observability")
    def runtime_observability() -> JSONResponse:
        try:
            payload = application.operational_status()
        except RuntimeError:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {
                        "code": "OPERATIONAL_STATUS_NOT_CONFIGURED",
                        "detail": "operational status unavailable",
                    },
                },
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload)

    @app.get("/runtime/metrics", response_class=Response)
    def runtime_metrics() -> Response:
        try:
            # Keep the product-runtime package import lazy: tpaa_runtime also
            # composes tpaa_api, so importing it while routes are registering
            # would create an initialization cycle.
            from tpaa_runtime.prometheus_metrics import render_prometheus_metrics

            payload = application.operational_status()
            body = render_prometheus_metrics(payload)
        except (RuntimeError, ValueError):
            return Response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content="# TPAA operational metrics unavailable\n",
                media_type="text/plain",
            )
        return Response(
            status_code=status.HTTP_200_OK,
            content=body,
            media_type="text/plain; version=0.0.4",
        )

    return app
