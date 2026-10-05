"""Desktop-profile FastAPI surface for the GUI-owned local backend."""

from __future__ import annotations

import hmac
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tpaa_application import ApplicationService

from .m8_app import M8PrincipalResolver
from .m9_app import M9PrincipalResolver
from .unified import register_unified_routes

_bearer = HTTPBearer(auto_error=False)
_DESKTOP_ALLOWED_PATHS = frozenset(
    {
        "/health",
        "/readiness",
        "/version",
        "/runtime/features",
        "/runtime/qualification",
        "/runtime/observability",
        "/jobs",
    }
)
_DESKTOP_ALLOWED_PREFIXES = (
    "/jobs/",
    "/m1/",
    "/m3/",
    "/m4/",
    "/m6/",
    "/m7/",
    "/m8/",
    "/m9/",
    "/api/v1/",
)


def _deny_principal(_request: Request) -> None:
    raise PermissionError("runtime principal resolver is not configured")


def create_desktop_app(
    *,
    application: ApplicationService,
    bearer_token: str,
    m8_principal_resolver: M8PrincipalResolver | None = None,
    m9_principal_resolver: M9PrincipalResolver | None = None,
) -> FastAPI:
    """Create the loopback-only Desktop surface over one composed Application graph."""

    if not bearer_token:
        raise ValueError("bearer_token must be non-empty")

    def require_bearer(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(_bearer),
        ],
    ) -> None:
        supplied = "" if credentials is None else credentials.credentials
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not hmac.compare_digest(supplied, bearer_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="UNAUTHORIZED",
            )

    app = FastAPI(
        title="TPAA Desktop Local Backend",
        version="0.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(require_bearer)],
    )

    @app.middleware("http")
    async def enforce_desktop_surface(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        allowed = (
            path in _DESKTOP_ALLOWED_PATHS
            or any(path.startswith(prefix) for prefix in _DESKTOP_ALLOWED_PREFIXES)
        )
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "PATH_NOT_ALLOWED"},
            )
        if request.headers.get("origin") is not None:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "ORIGIN_FORBIDDEN"},
            )
        return await call_next(request)

    return register_unified_routes(
        app,
        application,
        m8_principal_resolver=(
            m8_principal_resolver
            or cast(M8PrincipalResolver, _deny_principal)
        ),
        m9_principal_resolver=(
            m9_principal_resolver
            or cast(M9PrincipalResolver, _deny_principal)
        ),
    )
