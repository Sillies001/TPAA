"""G9 replay-context HTTP adapter tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.fixtures.weapon_events import (
    InMemoryWeaponEventStore,
    StaticLaunchSource,
    launch_fact,
    shooter_anchors,
)
from tpaa_api import UnifiedPrincipal, create_unified_service_app
from tpaa_application import (
    ApplicationService,
    ReplayContextApplicationService,
    WeaponEventApplicationService,
)
from tpaa_application.weapon_event import WeaponEventDetector
from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    load_security_policy,
)

PATH_SUFFIX = "/replay-context"
RELEASE_ID = "22222222-2222-4222-8222-222222222222"
CONTEXT_ID = "33333333-3333-4333-8333-333333333333"
EXACT_QUERY = f"?release_id={RELEASE_ID}&context_id={CONTEXT_ID}&perspective=shooter"


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage is not used by the G9 read model")


def _client() -> tuple[TestClient, InMemoryApiAuthorizationAudit, str]:
    audit = InMemoryApiAuthorizationAudit()
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()),
        audit=audit,
    )
    batch_id = "11111111-1111-4111-8111-111111111111"
    store = InMemoryWeaponEventStore()
    fact = launch_fact("L1", batch_id=batch_id, release_id=RELEASE_ID)
    event = WeaponEventDetector(StaticLaunchSource((fact,)), store).detect_and_publish(batch_id)[0]
    weapon_service = WeaponEventApplicationService(store)
    weapon_service.register(event, shooter_anchors(), context_id=CONTEXT_ID)
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        weapon_event=weapon_service,
        replay_context=ReplayContextApplicationService(weapon_service),
    )
    app = create_unified_service_app(
        application=application,
        principal_resolver=lambda _request: UnifiedPrincipal(
            role="ADMIN_AUDITOR",
            actor_id="g9-api-test",
            scope_match=True,
            security_roles=("ADMINISTRATOR",),
            resource_scopes=("*",),
        ),
        authorization_guard=guard,
    )
    return TestClient(app), audit, event.weapon_event_id


def test_authorized_replay_context_returns_exact_payload() -> None:
    client, audit, weapon_event_id = _client()
    with client:
        response = client.get(f"/api/v1/gui/weapon-events/{weapon_event_id}{PATH_SUFFIX}{EXACT_QUERY}")
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "TPAA_G9_REPLAY_CONTEXT_V1"
    assert body["weapon_event_id"] == weapon_event_id
    assert body["release_id"] == RELEASE_ID
    assert body["context_id"] == CONTEXT_ID
    assert body["ranges"]["media_ranges"] == []
    assert all(event.route_id == "api.route.103" and event.allowed for event in audit.events)


def test_unknown_weapon_event_is_404() -> None:
    client, _audit, _weapon_event_id = _client()
    with client:
        response = client.get(f"/api/v1/gui/weapon-events/nope{PATH_SUFFIX}{EXACT_QUERY}")
    assert response.status_code == 404
    assert response.json()["code"] == "WEAPON_EVENT_NOT_FOUND"
    assert response.json()["provenance"]["latest_fallback"] is False


def test_replay_context_requires_exact_scope_query() -> None:
    client, _audit, weapon_event_id = _client()
    with client:
        response = client.get(f"/api/v1/gui/weapon-events/{weapon_event_id}{PATH_SUFFIX}")
    assert response.status_code == 422


def test_replay_context_rejects_mismatched_release() -> None:
    client, _audit, weapon_event_id = _client()
    query = (
        "?release_id=44444444-4444-4444-8444-444444444444"
        f"&context_id={CONTEXT_ID}&perspective=shooter"
    )
    with client:
        response = client.get(f"/api/v1/gui/weapon-events/{weapon_event_id}{PATH_SUFFIX}{query}")
    assert response.status_code == 422
    assert response.json()["code"] == "REPLAY_SCOPE_MISMATCH"
