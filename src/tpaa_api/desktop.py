"""Desktop-profile FastAPI surface for the GUI-owned local backend."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
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
        "/runtime/operations",
        "/runtime/final-qualification",
        "/runtime/qualification",
        "/runtime/observability",
        "/runtime/metrics",
        "/ui",
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
        "/runtime/operations",
        "/runtime/final-qualification",
        "/runtime/qualification",
        "/runtime/observability",
        "/runtime/metrics",
        "/ui",
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
    "/security/",
    "/ui/",
)



_V24_DIRECT_QUERY_KEYS = frozenset({"view", "view_id", "route", "page"})


def _is_direct_v24_navigation(request: Request) -> bool:
    """Reject direct V24 URLs; only the in-memory V08 controlled entry may enter."""

    path = request.url.path
    if path != "/ui" and not path.startswith("/ui/"):
        return False
    if any(segment.upper() == "V24" for segment in path.split("/") if segment):
        return True
    return any(
        value.strip().upper() == "V24"
        for key in _V24_DIRECT_QUERY_KEYS
        for value in request.query_params.getlist(key)
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
    desktop_nonce: str | None = None,
    web_asset_root: Path | None = None,
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
        origin = request.headers.get("origin")
        if origin is not None:
            server = request.scope.get("server")
            server_port = (
                server[1]
                if isinstance(server, (tuple, list)) and len(server) == 2
                else None
            )
            expected_origin = f"http://127.0.0.1:{server_port}"
            supplied_nonce = request.headers.get("x-tpaa-desktop-nonce", "")
            if (
                desktop_nonce is None
                or origin != expected_origin
                or not hmac.compare_digest(supplied_nonce, desktop_nonce)
            ):
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
        if _is_direct_v24_navigation(request):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "V24_REQUIRES_V08_CONTEXT"},
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
            and not path.startswith("/ui/")
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

    if desktop_nonce is not None:
        assets = (web_asset_root or Path(__file__).resolve().parents[1] / "tpaa_gui" / "web_dist").resolve()
        if not (assets / "index.html").is_file():
            raise ValueError("WebEngine static asset root is unavailable")

        def static_response(relative: str) -> FileResponse:
            candidate = (assets / relative).resolve()
            if assets not in candidate.parents and candidate != assets:
                raise HTTPException(status_code=404, detail="STATIC_ASSET_NOT_FOUND")
            if not candidate.is_file():
                raise HTTPException(status_code=404, detail="STATIC_ASSET_NOT_FOUND")
            response = FileResponse(candidate)
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                "object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        @app.get("/ui", include_in_schema=False)
        def web_index() -> FileResponse:
            return static_response("index.html")

        @app.get("/ui/{asset_path:path}", include_in_schema=False)
        def web_asset(asset_path: str) -> FileResponse:
            return static_response(asset_path or "index.html")

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
