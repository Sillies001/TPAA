from __future__ import annotations

from fastapi.testclient import TestClient

from tests.fixtures.weapon_events import (
    InMemoryWeaponEventStore,
    StaticLaunchSource,
    launch_fact,
    shooter_anchors,
)
from tpaa_api import UnifiedPrincipal, create_unified_service_app
from tpaa_application import ApplicationService, WeaponEventApplicationService
from tpaa_application.weapon_event import WeaponEventDetector
from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    ResourceContext,
    load_security_policy,
)


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage is not used by G5 read routes")


class _Resolver:
    def __init__(self, weapon_event_id: str, batch_id: str) -> None:
        self.weapon_event_id = weapon_event_id
        self.batch_id = batch_id

    def resolve(self, method: str, path: str) -> ResourceContext | None:
        if method == "GET" and path.startswith("/api/v1/gui/weapon-events/"):
            requested = path.split("/")[5]
            return ResourceContext(
                resource_type="WEAPON_EVENT",
                resource_id=requested,
                weapon_event_id=requested,
                batch_id=self.batch_id if requested == self.weapon_event_id else None,
                release_id="release-1" if requested == self.weapon_event_id else None,
                context_id="context-1" if requested == self.weapon_event_id else None,
            )
        return None


def _application() -> tuple[ApplicationService, str, str]:
    batch_id = "11111111-1111-4111-8111-111111111111"
    store = InMemoryWeaponEventStore()
    fact = launch_fact("L1", batch_id=batch_id)
    event = WeaponEventDetector(StaticLaunchSource((fact,)), store).detect_and_publish(batch_id)[0]
    service = WeaponEventApplicationService(store)
    service.register(event, shooter_anchors())
    return (
        ApplicationService(
            get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
            weapon_event=service,
        ),
        event.weapon_event_id,
        batch_id,
    )


def _client(scopes: tuple[str, ...]) -> tuple[TestClient, str]:
    application, weapon_event_id, batch_id = _application()
    effective_scopes = tuple(
        f"weapon_event:{weapon_event_id}" if value == "__EXACT__" else value
        for value in scopes
    )
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()),
        audit=InMemoryApiAuthorizationAudit(),
        resource_resolver=_Resolver(weapon_event_id, batch_id),
    )
    principal = UnifiedPrincipal(
        role="INSTRUCTOR_EVALUATOR",
        actor_id="22222222-2222-4222-8222-222222222222",
        scope_match=True,
        resource_scopes=effective_scopes,
    )
    app = create_unified_service_app(
        application=application,
        principal_resolver=lambda _request: principal,
        authorization_guard=guard,
    )
    return TestClient(app), weapon_event_id


def test_exact_weapon_event_scope_allows_three_g5_read_routes() -> None:
    client, weapon_event_id = _client(("__EXACT__",))
    with client:
        detail = client.get(f"/api/v1/gui/weapon-events/{weapon_event_id}")
        window = client.get(
            f"/api/v1/gui/weapon-events/{weapon_event_id}/windows/shooter"
        )
        perspective = client.get(
            f"/api/v1/gui/weapon-events/{weapon_event_id}/perspectives/shooter"
        )
    assert detail.status_code == 200
    assert window.status_code == 200
    assert perspective.status_code == 200
    assert detail.headers["cache-control"] == "private, no-store"


def test_complete_batch_release_context_scope_is_accepted() -> None:
    client, weapon_event_id = _client(
        (
            "batch:11111111-1111-4111-8111-111111111111",
            "release:release-1",
            "context:context-1",
        )
    )
    with client:
        response = client.get(f"/api/v1/gui/weapon-events/{weapon_event_id}")
    assert response.status_code == 200


def test_wrong_or_wildcard_scope_is_denied_before_read_model() -> None:
    for scopes in (
        ("weapon_event:wrong",),
        ("batch:11111111-1111-4111-8111-111111111111", "release:wrong", "context:context-1"),
        ("batch:11111111-1111-4111-8111-111111111111", "release:release-1", "context:wrong"),
        ("*",),
    ):
        client, weapon_event_id = _client(scopes)
        with client:
            response = client.get(f"/api/v1/gui/weapon-events/{weapon_event_id}")
        assert response.status_code == 403
        assert response.json()["error"]["code"] in {
            "WEAPON_EVENT_EXACT_SCOPE_DENIED",
            "RESOURCE_SCOPE_WILDCARD_DENIED",
        }


def test_exact_absent_id_returns_404_and_invalid_perspective_returns_422() -> None:
    client, weapon_event_id = _client(("__EXACT__",))
    with client:
        invalid = client.get(
            f"/api/v1/gui/weapon-events/{weapon_event_id}/windows/diagonal"
        )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "PERSPECTIVE_INVALID"

    absent_client, _ = _client(("weapon_event:missing",))
    with absent_client:
        absent = absent_client.get("/api/v1/gui/weapon-events/missing")
    assert absent.status_code == 404
    assert absent.json()["code"] == "WEAPON_EVENT_NOT_FOUND"


def test_g5_routes_are_not_registered_without_capability_service() -> None:
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
    )
    app = create_unified_service_app(
        application=application,
        principal_resolver=lambda _request: UnifiedPrincipal(
            role="ADMIN_AUDITOR",
            actor_id="33333333-3333-4333-8333-333333333333",
            scope_match=True,
        ),
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/gui/weapon-events/missing")
    assert response.status_code == 404
