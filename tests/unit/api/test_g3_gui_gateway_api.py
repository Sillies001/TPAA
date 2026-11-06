from __future__ import annotations

from fastapi.testclient import TestClient

from tpaa_api import UnifiedPrincipal, create_unified_service_app
from tpaa_application import ApplicationService, GuiGatewayService
from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    load_security_policy,
)


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage must not be used by the G3 GUI read model")


def _application() -> ApplicationService:
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        gui_gateway=GuiGatewayService(),
    )


def _principal(role: str = "ADMIN_AUDITOR") -> UnifiedPrincipal:
    return UnifiedPrincipal(
        role=role,
        actor_id="11111111-1111-4111-8111-111111111111",
        scope_match=True,
        resource_scopes=("release:allowed",),
    )


def _client(*, role: str = "ADMIN_AUDITOR") -> tuple[TestClient, InMemoryApiAuthorizationAudit]:
    audit = InMemoryApiAuthorizationAudit()
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()),
        audit=audit,
    )
    app = create_unified_service_app(
        application=_application(),
        principal_resolver=lambda _request: _principal(role),
        authorization_guard=guard,
    )
    return TestClient(app), audit


def test_bootstrap_catalog_and_selector_use_one_authorized_application_boundary() -> None:
    client, audit = _client()
    with client:
        bootstrap = client.get("/api/v1/gui/bootstrap", headers={"X-Request-Id": "boot-1"})
        catalog = client.get("/api/v1/gui/catalog", headers={"X-Request-Id": "catalog-1"})
        selector = client.get("/api/v1/gui/selectors/views?limit=5")

    assert bootstrap.status_code == 200
    assert bootstrap.headers["cache-control"] == "private, no-store"
    body = bootstrap.json()
    assert body["schema"] == "TPAA_GUI_BOOTSTRAP_V1"
    assert body["request_id"] == "boot-1"
    assert body["provenance"]["core_baseline"] == "CB-1.8.0"
    assert len(body["catalog"]["views"]) == 26
    assert "11111111-1111-4111-8111-111111111111" not in bootstrap.text
    assert catalog.status_code == 200
    assert selector.status_code == 200
    assert len(selector.json()["items"]) == 5
    assert {event.route_id for event in audit.events} == {
        "api.route.087",
        "api.route.088",
        "api.route.089",
    }
    assert all(event.allowed for event in audit.events)


def test_trainee_receives_only_approved_role_projection() -> None:
    client, _audit = _client(role="SUBJECT_SELF")
    with client:
        response = client.get("/api/v1/gui/bootstrap")
    assert response.status_code == 200
    body = response.json()
    assert body["principal"]["roles"] == ["TRAINEE"]
    assert len(body["catalog"]["views"]) == 23


def test_selector_errors_keep_stable_reason_and_provenance() -> None:
    client, _audit = _client()
    with client:
        response = client.get("/api/v1/gui/selectors/not-registered")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["reason_code"] == "NOT_FOUND"
    assert response.json()["provenance"] == {
        "authority_id": "GUI_ASYNC_GATEWAY_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": "CB-1.8.0",
    }


def test_reserved_g4_business_route_is_not_exposed_and_fails_closed() -> None:
    client, audit = _client()
    with client:
        response = client.get("/api/v1/gui/historical-overview")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROUTE_NOT_AUTHORIZED"
    assert audit.events[-1].route_id == "UNREGISTERED"
    assert audit.events[-1].allowed is False


def test_missing_principal_fails_before_gateway_execution() -> None:
    def denied(_request: object) -> object:
        raise PermissionError("identity unavailable")

    app = create_unified_service_app(
        application=_application(),
        principal_resolver=denied,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/gui/bootstrap")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PRINCIPAL_RESOLUTION_REQUIRED"
