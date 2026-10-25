"""Desktop-profile FastAPI surface for the GUI-owned local backend."""

from __future__ import annotations

import hmac
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tpaa_application import ApplicationService
from tpaa_security import ApiAuthorizationGuard, ApprovalService

from .m8_app import M8PrincipalResolver
from .m9_app import M9PrincipalResolver
from .unified import UnifiedPrincipal, UnifiedPrincipalResolver, register_unified_routes

_bearer = HTTPBearer(auto_error=False)
_DESKTOP_ALLOWED_PATHS = frozenset(
    {
        "/health",
        "/readiness",
        "/version",
        "/runtime/features",
        "/runtime/external-capabilities",
        "/runtime/qualification",
        "/runtime/observability",
        "/runtime/metrics",
        "/jobs",
    }
)
_DESKTOP_IDENTITY_OPTIONAL_PATHS = frozenset(
    {
        "/health",
        "/readiness",
        "/version",
        "/runtime/features",
        "/runtime/external-capabilities",
        "/runtime/qualification",
        "/runtime/observability",
        "/runtime/metrics",
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
    principal_resolver: UnifiedPrincipalResolver | None = None,
    authorization_guard: ApiAuthorizationGuard | None = None,
    approval_service: ApprovalService | None = None,
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
        allowed = path in _DESKTOP_ALLOWED_PATHS or any(
            path.startswith(prefix) for prefix in _DESKTOP_ALLOWED_PREFIXES
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
        authorization = request.headers.get("authorization", "")
        scheme, separator, supplied = authorization.partition(" ")
        if (
            separator != " "
            or scheme.lower() != "bearer"
            or not hmac.compare_digest(supplied, bearer_token)
        ):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "UNAUTHORIZED"},
            )
        principal: UnifiedPrincipal | None = None
        if principal_resolver is not None:
            try:
                candidate = principal_resolver(request)
                if isinstance(candidate, UnifiedPrincipal):
                    principal = candidate
            except Exception:
                principal = None
        qualification_projection = (
            m8_principal_resolver is not None and m9_principal_resolver is not None
        )
        if (
            principal is None
            and not qualification_projection
            and path not in _DESKTOP_IDENTITY_OPTIONAL_PATHS
        ):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "DESKTOP_LOCAL_IDENTITY_REQUIRED"},
            )
        if principal is not None:
            request.state.tpaa_principal = principal
            if authorization_guard is not None:
                decision = authorization_guard.authorize(
                    principal.authorization_principal(),
                    method=request.method,
                    path=path,
                    approval_id=request.headers.get("x-tpaa-approval-id"),
                )
                if not decision.allowed:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": decision.code},
                    )
        return await call_next(request)

    def desktop_m8_principal(request: Request):  # type: ignore[no-untyped-def]
        principal = getattr(request.state, "tpaa_principal", None)
        if not isinstance(principal, UnifiedPrincipal):
            raise PermissionError("Desktop local identity is unavailable")
        return principal.m8_viewer()

    def desktop_m9_principal(request: Request):  # type: ignore[no-untyped-def]
        principal = getattr(request.state, "tpaa_principal", None)
        if not isinstance(principal, UnifiedPrincipal):
            raise PermissionError("Desktop local identity is unavailable")
        return principal.m9_viewer()

    def desktop_actor(request: Request) -> str:
        principal = getattr(request.state, "tpaa_principal", None)
        if not isinstance(principal, UnifiedPrincipal):
            raise PermissionError("Desktop local identity is unavailable")
        return principal.actor_key

    result = register_unified_routes(
        app,
        application,
        m8_principal_resolver=(
            m8_principal_resolver
            or (
                cast(M8PrincipalResolver, desktop_m8_principal)
                if principal_resolver is not None
                else cast(M8PrincipalResolver, _deny_principal)
            )
        ),
        m9_principal_resolver=(
            m9_principal_resolver
            or (
                cast(M9PrincipalResolver, desktop_m9_principal)
                if principal_resolver is not None
                else cast(M9PrincipalResolver, _deny_principal)
            )
        ),
        actor_resolver=desktop_actor if principal_resolver is not None else None,
    )
    if approval_service is not None:
        from .security import register_security_routes

        register_security_routes(result, approval_service)
    return result
