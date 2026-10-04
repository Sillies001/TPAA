"""PIQB B4 unified Desktop/Service route graph and principal boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M8ViewerContext,
    M9ViewerContext,
)

from .app import ActorResolver, register_base_routes
from .m1_app import register_m1_routes
from .m3_app import register_m3_routes
from .m4_app import register_m4_routes
from .m6_app import register_m6_routes
from .m7_app import register_m7_routes
from .m8_app import M8PrincipalResolver, register_m8_routes
from .m9_app import M9PrincipalResolver, register_m9_routes
from .product_v1 import register_product_v1_routes
from .runtime import register_product_runtime_routes


@dataclass(frozen=True, slots=True)
class UnifiedPrincipal:
    """Transport-neutral authenticated principal projected into frozen domain policies."""

    role: str
    actor_id: str | None
    scope_match: bool
    validation_only: bool = False
    privileged_identity_authorized: bool = False
    visibility_authorized: bool = False
    export_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError("principal role must be non-empty")
        if self.actor_id is not None and (
            not isinstance(self.actor_id, str) or not self.actor_id.strip()
        ):
            raise ValueError("principal actor_id must be non-empty when provided")

    @property
    def actor_key(self) -> str:
        return self.actor_id or f"ROLE:{self.role}"

    def m8_viewer(self) -> M8ViewerContext:
        return M8ViewerContext(
            viewer_role=self.role,
            viewer_actor_id=self.actor_id,
            scope_match=self.scope_match,
            privileged_identity_authorized=self.privileged_identity_authorized,
            visibility_authorized=self.visibility_authorized,
            export_authorized=self.export_authorized,
        )

    def m9_viewer(self) -> M9ViewerContext:
        return M9ViewerContext(
            role=self.role,
            actor_id=self.actor_id,
            scope_match=self.scope_match,
            validation_only=self.validation_only,
            privileged_identity_authorized=self.privileged_identity_authorized,
            export_authorized=self.export_authorized,
        )


UnifiedPrincipalResolver = Callable[[Request], object]


def _request_principal(request: Request) -> UnifiedPrincipal:
    value = getattr(request.state, "tpaa_principal", None)
    if not isinstance(value, UnifiedPrincipal):
        raise PermissionError("authenticated principal is not available")
    return value


def _m8_from_state(request: Request) -> M8ViewerContext:
    return _request_principal(request).m8_viewer()


def _m9_from_state(request: Request) -> M9ViewerContext:
    return _request_principal(request).m9_viewer()


def _actor_from_state(request: Request) -> str:
    return _request_principal(request).actor_key


def register_unified_routes(
    app: FastAPI,
    application: ApplicationService,
    *,
    m8_principal_resolver: M8PrincipalResolver,
    m9_principal_resolver: M9PrincipalResolver,
    actor_resolver: ActorResolver | None = None,
) -> FastAPI:
    """Register the one P1-P6 HTTP route graph for both runtime profiles."""

    register_base_routes(
        app,
        application,
        actor_resolver=actor_resolver,
    )
    register_product_runtime_routes(app, application)
    register_m1_routes(app, application)
    register_m3_routes(app, application)
    register_m4_routes(app, application)
    register_m6_routes(app, application)
    register_m7_routes(app, application)
    register_m8_routes(
        app,
        application,
        principal_resolver=m8_principal_resolver,
    )
    register_m9_routes(
        app,
        application,
        principal_resolver=m9_principal_resolver,
    )
    register_product_v1_routes(
        app,
        application,
        m8_principal_resolver=m8_principal_resolver,
        m9_principal_resolver=m9_principal_resolver,
    )
    return app


def create_unified_service_app(
    *,
    application: ApplicationService,
    principal_resolver: UnifiedPrincipalResolver,
) -> FastAPI:
    """Create default-deny Service API with one injected identity/principal resolver."""

    app = FastAPI(
        title="TPAA Unified Service API",
        version="0.0.0",
    )

    @app.middleware("http")
    async def resolve_service_principal(request: Request, call_next):  # type: ignore[no-untyped-def]
        try:
            principal = principal_resolver(request)
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {"code": "PRINCIPAL_RESOLUTION_REQUIRED"},
                },
            )
        if not isinstance(principal, UnifiedPrincipal):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {"code": "PRINCIPAL_RESOLUTION_INVALID"},
                },
            )
        request.state.tpaa_principal = principal
        return await call_next(request)

    register_unified_routes(
        app,
        application,
        m8_principal_resolver=_m8_from_state,
        m9_principal_resolver=_m9_from_state,
        actor_resolver=_actor_from_state,
    )
    app.state.piqb_b4_unified_principal_required = True
    app.state.piqb_b4_transport_actor_header_authoritative = False
    return app
