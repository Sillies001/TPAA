"""Desktop-profile FastAPI surface for the GUI-owned local backend."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tpaa_application import ApplicationService

from .app import _readiness_payload, _version_payload

_bearer = HTTPBearer(auto_error=False)
_DESKTOP_ALLOWED_PATHS = frozenset({"/health", "/readiness", "/version"})


def create_desktop_app(*, application: ApplicationService, bearer_token: str) -> FastAPI:
    """Create the loopback-only Desktop HTTP surface frozen by ADR-M0-005.

    Listener ownership/binding remains with the child process.  This factory only
    applies the Desktop HTTP policy: bearer auth on every route, no docs/OpenAPI,
    no CORS middleware, and fail-closed Origin rejection.
    """

    if not bearer_token:
        raise ValueError("bearer_token must be non-empty")

    def require_bearer(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> None:
        supplied = "" if credentials is None else credentials.credentials
        if credentials is None or credentials.scheme.lower() != "bearer" or not hmac.compare_digest(
            supplied, bearer_token
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")

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
        if request.url.path not in _DESKTOP_ALLOWED_PATHS:
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "UP"}

    @app.get("/readiness")
    def readiness() -> JSONResponse:
        runtime = application.runtime_baseline_status()
        http_status = status.HTTP_200_OK if runtime.ready else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=http_status, content=_readiness_payload(runtime))

    @app.get("/version")
    def version() -> dict[str, object]:
        return _version_payload(application.runtime_baseline_status())

    return app
