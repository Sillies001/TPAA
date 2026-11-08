"""G8 co-attack HTTP adapter tests: authorization and fail-closed negatives."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tpaa_api import UnifiedPrincipal, create_unified_service_app
from tpaa_application import ApplicationService, CoAttackApplicationService
from tpaa_application.co_attack import CoAttackEventSource
from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    load_security_policy,
)

PATH = "/api/v1/gui/attack-clusters/cluster-1/co-attack-analysis"


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage is not used by the G8 read model")


class _FixtureSource(CoAttackEventSource):
    def cluster(self, cluster_id):
        if cluster_id != "cluster-1":
            return None
        return {"cluster_id": cluster_id, "batch_id": "b-1", "weapon_event_ids": ["we-1"]}

    def events(self, batch_id, weapon_event_ids):
        return (
            {"weapon_event_id": "we-1", "batch_id": "b-1", "category": "BVR",
             "t1_session_time_us": "100", "shooter_entity_id": "a-1", "target_entity_id": "t-1"},
        )

    def formation(self, context_id):
        return None


def _client(
    *, security_roles: tuple[str, ...] = ("ADMINISTRATOR",), scopes: tuple[str, ...] | None = None
) -> tuple[TestClient, InMemoryApiAuthorizationAudit]:
    audit = InMemoryApiAuthorizationAudit()
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()),
        audit=audit,
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        co_attack=CoAttackApplicationService(_FixtureSource()),
    )
    app = create_unified_service_app(
        application=application,
        principal_resolver=lambda _request: UnifiedPrincipal(
            role="ADMIN_AUDITOR",
            actor_id="g8-api-test",
            scope_match=True,
            security_roles=security_roles,
            resource_scopes=(("resource:API_PATH:" + PATH,) if scopes is None else scopes),
        ),
        authorization_guard=guard,
    )
    return TestClient(app), audit


def test_authorized_analysis_returns_exact_cluster_payload() -> None:
    client, audit = _client()
    with client:
        response = client.get(PATH, params={"context_id": "ctx-1"}, headers={"X-Request-Id": "g8-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "TPAA_G8_CO_ATTACK_ANALYSIS_V1"
    assert body["request_id"] == "g8-1"
    assert body["cluster_id"] == "cluster-1"
    assert len(body["weapon_events"]) == 1
    assert all(event.route_id == "api.route.102" and event.allowed for event in audit.events)


def test_unauthorized_role_denied_before_read_model() -> None:
    client, audit = _client(security_roles=("TRAINEE",), scopes=())
    with client:
        response = client.get(PATH)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_SCOPE_DENIED"
    assert audit.events[-1].route_id == "api.route.102"
    assert audit.events[-1].allowed is False


def test_unknown_cluster_is_404() -> None:
    client, _audit = _client()
    with client:
        response = client.get(
            "/api/v1/gui/attack-clusters/nope/co-attack-analysis",
            params={"context_id": "ctx-1"},
        )
    assert response.status_code == 404
    assert response.json()["code"] == "CLUSTER_NOT_FOUND"
    assert response.json()["provenance"]["latest_fallback"] is False


def test_missing_exact_context_is_rejected_before_cluster_read() -> None:
    client, _audit = _client()
    with client:
        response = client.get(PATH)
    assert response.status_code == 422
    assert response.json()["code"] == "CONTEXT_REQUIRED"
