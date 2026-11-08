"""G6 historical-overview HTTP adapter tests: authorization, fail-closed query semantics."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from tpaa_api import UnifiedPrincipal, create_unified_service_app
from tpaa_application import ApplicationService, HistoricalOverviewApplicationService
from tpaa_application.historical_overview import (
    BatchOverviewRecord,
    BatchWorksetSource,
    EquipmentMetricInput,
    TaskMetricInput,
)
from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    load_security_policy,
)


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage is not used by the G6 read model")


class _FixtureSource(BatchWorksetSource):
    def __init__(self) -> None:
        self._batches = (
            BatchOverviewRecord(
                "b-001", date(2026, 10, 20), "COMPREHENSIVE_OPPOSITION",
                6, 4, 9, 7, "QUALIFIED", True,
            ),
            BatchOverviewRecord(
                "b-002", date(2026, 10, 22), "SIMPLE_OPPOSITION",
                4, 3, 5, 5, "QUALIFIED", False,
            ),
        )

    def qualified_batches(self):
        return self._batches

    def task_metric_inputs(self, batch_ids):
        return (TaskMetricInput("kill_ratio", "击杀比", "ratio", 7, 10),)

    def equipment_metric_inputs(self, batch_ids):
        return (
            EquipmentMetricInput(
                "sustained_turn", "持续盘旋角速度", "deg/s",
                True, "ELIGIBLE", None, (("2026-10-20", 13.2),),
            ),
        )


def _application() -> ApplicationService:
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        historical_overview=HistoricalOverviewApplicationService(_FixtureSource()),
    )


def _client(
    *, security_roles: tuple[str, ...] = ("ADMINISTRATOR",), scopes: tuple[str, ...] = ("*",)
) -> tuple[TestClient, InMemoryApiAuthorizationAudit]:
    audit = InMemoryApiAuthorizationAudit()
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()),
        audit=audit,
    )
    app = create_unified_service_app(
        application=_application(),
        principal_resolver=lambda _request: UnifiedPrincipal(
            role="ADMIN_AUDITOR",
            actor_id="g6-api-test",
            scope_match=True,
            security_roles=security_roles,
            resource_scopes=scopes,
        ),
        authorization_guard=guard,
    )
    return TestClient(app), audit


def test_authorized_overview_returns_exact_workset_payload() -> None:
    client, audit = _client()
    with client:
        response = client.get("/api/v1/gui/historical-overview")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    assert body["schema"] == "TPAA_G6_HISTORICAL_OVERVIEW_V1"
    assert body["kpi"]["batch_count"] == 2
    assert len(body["batches"]) == 2
    assert body["provenance"]["single_batch_workset"] is True
    assert body["provenance"]["latest_fallback"] is False
    assert all(event.allowed and event.route_id == "api.route.100" for event in audit.events)


def test_unauthorized_role_is_denied_before_read_model() -> None:
    """TRAINEE holds DERIVED_DATA_READ but not the ownership scope for this API path."""
    client, audit = _client(security_roles=("TRAINEE",), scopes=())
    with client:
        response = client.get("/api/v1/gui/historical-overview")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_SCOPE_DENIED"
    assert audit.events[-1].route_id == "api.route.100"
    assert audit.events[-1].allowed is False


def test_reverse_date_range_fails_closed_empty_with_warning() -> None:
    client, _audit = _client()
    with client:
        response = client.get(
            "/api/v1/gui/historical-overview",
            params={"start_date": "2026-10-31", "end_date": "2026-10-01"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["filter"]["invalid_date_range"] is True
    assert body["batches"] == []
    assert body["kpi"]["batch_count"] == 0
    assert body["provenance"]["batch_count"] == 0


def test_malformed_date_fails_closed_422() -> None:
    client, _audit = _client()
    with client:
        response = client.get(
            "/api/v1/gui/historical-overview", params={"start_date": "not-a-date"}
        )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "OVERVIEW_QUERY_INVALID"
    assert body["provenance"]["core_baseline"] == "CB-1.14.0"
    assert body["provenance"]["latest_fallback"] is False
