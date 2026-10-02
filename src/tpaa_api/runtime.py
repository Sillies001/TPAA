"""PIQB product-runtime API projections layered above the stable base API."""

from __future__ import annotations

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

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

    return app
