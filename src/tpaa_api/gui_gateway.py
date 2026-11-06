"""G3 GUI catalog/bootstrap/selectors transport over the Application gateway."""

from __future__ import annotations

import secrets

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService, GuiGatewayError, GuiGatewayPrincipal
from tpaa_security import derive_gui_permissions, load_security_policy


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "")
    if supplied and len(supplied) <= 128 and supplied.replace("-", "").replace("_", "").isalnum():
        return supplied
    return f"g3-{secrets.token_hex(16)}"


def _principal(request: Request) -> GuiGatewayPrincipal:
    from .unified import UnifiedPrincipal

    value = getattr(request.state, "tpaa_principal", None)
    if not isinstance(value, UnifiedPrincipal):
        raise GuiGatewayError("FORBIDDEN", http_status=403)
    authorization = value.authorization_principal()
    policy = load_security_policy()
    business_permissions = frozenset(
        permission for role in authorization.roles for permission in policy.role_permissions[role]
    )
    return GuiGatewayPrincipal(
        subject=authorization.subject,
        roles=tuple(sorted(role.value for role in authorization.roles)),
        gui_permissions=derive_gui_permissions(authorization.roles, business_permissions),
        resource_scopes=tuple(sorted(authorization.scopes)),
    )


def _error(exc: GuiGatewayError, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "schema": "TPAA_GUI_GATEWAY_ERROR_V1",
            "request_id": request_id,
            "status": "FORBIDDEN" if exc.http_status == 403 else "ERROR",
            "code": exc.code,
            "reason_code": exc.reason_code,
            "retryable": exc.retryable,
            "provenance": {
                "authority_id": "GUI_ASYNC_GATEWAY_AUTHORITY",
                "authority_version": "1.0.0",
                "core_baseline": "CB-1.8.0",
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


def register_gui_gateway_routes(app: FastAPI, application: ApplicationService) -> None:
    @app.get("/api/v1/gui/catalog", operation_id="getGuiCatalog")
    def catalog(request: Request) -> JSONResponse:
        request_id = _request_id(request)
        try:
            payload = application.gui_catalog(_principal(request), request_id=request_id)
        except GuiGatewayError as exc:
            return _error(exc, request_id)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.get("/api/v1/gui/bootstrap", operation_id="getGuiBootstrap")
    def bootstrap(request: Request) -> JSONResponse:
        request_id = _request_id(request)
        try:
            payload = application.gui_bootstrap(_principal(request), request_id=request_id)
        except GuiGatewayError as exc:
            return _error(exc, request_id)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.get("/api/v1/gui/selectors/{selector_id}", operation_id="getGuiSelector")
    def selector(
        selector_id: str,
        request: Request,
        release_id: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> JSONResponse:
        request_id = _request_id(request)
        try:
            payload = application.gui_selector(
                _principal(request),
                selector_id,
                request_id=request_id,
                release_id=release_id,
                cursor=cursor,
                limit=limit,
            )
        except GuiGatewayError as exc:
            return _error(exc, request_id)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})


__all__ = ["register_gui_gateway_routes"]
