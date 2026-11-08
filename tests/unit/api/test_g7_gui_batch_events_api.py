"""G7 batch-events HTTP adapter tests: authorization, exact scope, fail-closed errors."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tpaa_api import UnifiedPrincipal, create_unified_service_app
from tpaa_application import ApplicationService, BatchEventsApplicationService
from tpaa_application.batch_events import BatchEventRecord
from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    load_security_policy,
)

PATH = "/api/v1/gui/batches/b-1/weapon-events"


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage is not used by the G7 read model")


class _FixtureSource:
    def batch_ids(self):
        return ("b-1",)

    def batch_context(self, batch_id):
        return None

    def events(self, batch_id):
        return (
            BatchEventRecord(
                weapon_event_id="we-1", revision_no=1, batch_id="b-1",
                t1_session_time_us=100, category="BVR", classification_exception=False,
                shooter_entity_id="shooter-1", target_entity_id="target-1",
                episode_id="episode-1", weapon_terminal_state="TERMINAL_KNOWN",
                adjudication_state="ADJUDICATED", observation_window_state="WINDOW_CLOSED",
                cluster_id=None,
            ),
        )

    def cluster_of(self, batch_id, weapon_event_id):
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
        batch_events=BatchEventsApplicationService(_FixtureSource()),
    )
    app = create_unified_service_app(
        application=application,
        principal_resolver=lambda _request: UnifiedPrincipal(
            role="ADMIN_AUDITOR",
            actor_id="g7-api-test",
            scope_match=True,
            security_roles=security_roles,
            resource_scopes=(
                ("resource:API_PATH:" + PATH,) if scopes is None else scopes
            ),
        ),
        authorization_guard=guard,
    )
    return TestClient(app), audit


def test_authorized_workbench_returns_exact_scope_payload() -> None:
    client, audit = _client()
    with client:
        response = client.get(PATH, headers={"X-Request-Id": "g7-req-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "TPAA_G7_BATCH_EVENT_WORKBENCH_V1"
    assert body["request_id"] == "g7-req-1"
    assert body["batch_id"] == "b-1"
    assert body["total_count"] == 1
    assert body["items"][0]["weapon_event_id"] == "we-1"
    assert body["summary"]["adjudication_counts"]["ADJUDICATED"] == 1
    assert all(event.route_id == "api.route.101" and event.allowed for event in audit.events)


def test_unauthorized_role_denied_before_read_model() -> None:
    client, audit = _client(security_roles=("TRAINEE",), scopes=())
    with client:
        response = client.get(PATH)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_SCOPE_DENIED"
    assert audit.events[-1].route_id == "api.route.101"
    assert audit.events[-1].allowed is False


def test_unknown_batch_is_404_not_empty() -> None:
    client, _audit = _client()
    with client:
        response = client.get("/api/v1/gui/batches/nope/weapon-events")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "BATCH_NOT_FOUND"
    assert body["provenance"]["latest_fallback"] is False


def test_invalid_filter_and_tampered_cursor_fail_closed() -> None:
    client, _audit = _client()
    with client:
        invalid = client.get(PATH, params={"category": "DOGFIGHT"})
        tampered = client.get(PATH, params={"cursor": "AAAA"})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "FILTER_INVALID"
    assert tampered.status_code == 400
    assert tampered.json()["code"] == "CURSOR_INVALID"


def test_exact_entity_episode_and_time_filters_are_forwarded() -> None:
    client, _audit = _client()
    with client:
        matching = client.get(
            PATH,
            params={
                "entity_id": "shooter-1",
                "episode_id": "episode-1",
                "start_time_us": "100",
                "end_time_us": "100",
            },
        )
        outside = client.get(PATH, params={"start_time_us": "101"})
        invalid = client.get(
            PATH, params={"start_time_us": "200", "end_time_us": "100"}
        )
    assert matching.status_code == 200
    assert matching.json()["total_count"] == 1
    assert matching.json()["filter"]["entity_id"] == "shooter-1"
    assert outside.status_code == 200 and outside.json()["total_count"] == 0
    assert invalid.status_code == 422 and invalid.json()["code"] == "FILTER_INVALID"
