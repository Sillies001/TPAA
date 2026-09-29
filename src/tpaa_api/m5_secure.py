"""M5 service-profile authentication and default-deny transport wrapper."""

from __future__ import annotations

import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService

from .app import create_app


class M5ServiceSecurityError(RuntimeError):
    """Fail-closed construction error for M5 service transport security."""


def create_m5_service_app(
    application: ApplicationService,
    *,
    bearer_token: str,
) -> FastAPI:
    """Wrap the service API with explicit authentication and default-deny authorization.

    The credential is injected by deployment/runtime configuration. There is deliberately
    no default token or development fallback.
    """

    if not isinstance(bearer_token, str) or not bearer_token.strip():
        raise M5ServiceSecurityError("M5 service bearer token is required")
    if len(bearer_token) < 24:
        raise M5ServiceSecurityError("M5 service bearer token is too short")

    expected = bearer_token.encode("utf-8")
    app = create_app(application)

    @app.middleware("http")
    async def m5_default_deny(request: Request, call_next):  # type: ignore[no-untyped-def]
        authorization = request.headers.get("authorization")
        if authorization is None or not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {"code": "M5_AUTHENTICATION_REQUIRED"},
                },
            )
        presented = authorization.removeprefix("Bearer ").encode("utf-8")
        if not hmac.compare_digest(presented, expected):
            return JSONResponse(
                status_code=403,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {"code": "M5_AUTHORIZATION_DENIED"},
                },
            )
        return await call_next(request)

    app.state.m5_authentication_required = True
    app.state.m5_default_deny_authorization = True
    app.state.m5_default_credentials_present = False
    return app
