"""G6 CB-1.11.0 Historical-overview successor, codegen parity and fail-closed exposure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fastapi.routing import APIRoute

from tools.baseline.adopt_g6_successor import check_successor
from tpaa_api import UnifiedPrincipal, create_desktop_app, create_unified_service_app
from tpaa_application import ApplicationService
from tpaa_security import (
    ApiAuthorizationGuard,
    ApprovalService,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    InMemoryApprovalEventRepository,
    load_security_policy,
)

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.11.0"
OVERVIEW_PATH = "/api/v1/gui/historical-overview"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _runtime_graph() -> set[tuple[str, str, str, str]]:
    policy = load_security_policy()
    approvals = ApprovalService(AuthorizationService(policy), InMemoryApprovalEventRepository())
    guard = ApiAuthorizationGuard(AuthorizationService(policy), audit=InMemoryApiAuthorizationAudit())
    principal = UnifiedPrincipal(role="ADMINISTRATOR", actor_id="g6-exposure-check", scope_match=True)
    application = cast(ApplicationService, object())
    apps = (
        create_unified_service_app(
            application=application,
            principal_resolver=lambda _request: principal,
            authorization_guard=guard,
            approval_service=approvals,
        ),
        create_desktop_app(
            application=application,
            bearer_token="g6-exposure-check",
            principal_resolver=lambda _request: principal,
            approval_service=approvals,
            desktop_nonce="g6-exposure-check-nonce",
        ),
    )
    graph: set[tuple[str, str, str, str]] = set()
    for app in apps:
        for route in app.routes:
            if isinstance(route, APIRoute):
                assert route.methods is not None and len(route.methods) == 1
                graph.add(
                    (
                        next(iter(route.methods)),
                        route.path,
                        route.endpoint.__module__,
                        route.endpoint.__name__,
                    )
                )
    return graph


def test_g6_successor_locks_parent_and_db_schema() -> None:
    check_successor()
    baseline = _load(BASELINE / "BASELINE_LOCK.json")["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.11.0"
    assert baseline["db_schema"] == "1.10.0"
    assert baseline["approval_status"] == "APPROVED_LOCAL"
    assert baseline["release_claim"] is False
    lineage = baseline.get("lock_lineage_sha256")
    assert isinstance(lineage, list) and len(lineage) == 1


def test_g6_security_authority_appends_overview_route() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = authority["active_routes"]
    assert isinstance(routes, list) and len(routes) == 100
    g6 = [item for item in routes if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G6"]
    assert len(g6) == 1
    route = g6[0]
    assert route["route_id"] == "api.route.100"
    assert route["path"] == OVERVIEW_PATH
    assert route["permission_id"] == "DERIVED_DATA_READ"
    assert route["gui_permission_id"] == "batch.history.read"
    assert route["audit_mode"] == "ALWAYS"


def test_g6_keeps_batch_events_and_replay_reserved() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json")
    reserved = authority["reserved_routes"]
    assert isinstance(reserved, list) and len(reserved) == 2
    assert {str(item["route_id"]) for item in reserved} == {"gui.batch.events", "gui.replay"}
    assert all(item.get("implementation_status") == "RESERVED_G6_NOT_EXPOSED" for item in reserved)


def test_g6_overview_route_is_not_exposed_until_activation() -> None:
    graph = _runtime_graph()
    exposed = {path for _method, path, _module, _name in graph}
    assert OVERVIEW_PATH not in exposed, "G6 overview route must stay unregistered until CB-1.11.0 activation"


def test_g6_authority_enforces_single_workset_and_fail_closed_rules() -> None:
    authority = _load(BASELINE / "canonical" / "GUI_HISTORICAL_OVERVIEW_AUTHORITY.json")
    rules = authority["rules"]
    owners = authority["single_owner_rules"]
    database = authority["database"]
    assert rules["single_batch_workset"] is True
    assert rules["ratio_recompute"] == "AGGREGATE_NUMERATOR_DENOMINATOR"
    assert rules["simple_average"] == "FORBIDDEN"
    assert rules["zero_denominator"] == "FAIL_CLOSED_NULL_REASON"
    assert rules["equipment_comparability"] == "FAIL_CLOSED"
    assert rules["latest_fallback"] == "FORBIDDEN"
    assert owners["historical_overview_query"] == "tpaa_application.historical_overview"
    assert owners["gui_business_recomputation"] == "FORBIDDEN"
    assert database["schema"] == "1.10.0"
    assert database["migration_required"] is False
