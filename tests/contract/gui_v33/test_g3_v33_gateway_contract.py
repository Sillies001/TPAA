from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fastapi.routing import APIRoute

from tools.baseline.adopt_g3_successor import check_successor
from tools.codegen.g3_gateway_generate import OUTPUTS, render
from tpaa_api import UnifiedPrincipal, create_desktop_app, create_unified_service_app
from tpaa_application import ApplicationService
from tpaa_security import (
    ApiAuthorizationGuard,
    ApprovalService,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    InMemoryApprovalEventRepository,
    load_security_policy,
    route_security,
)

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.8.0"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _runtime_graph() -> set[tuple[str, str, str, str]]:
    principal = UnifiedPrincipal(
        role="ADMIN_AUDITOR",
        actor_id="g3-route-parity",
        scope_match=True,
    )
    policy = load_security_policy()
    approvals = ApprovalService(
        AuthorizationService(policy),
        InMemoryApprovalEventRepository(),
    )
    guard = ApiAuthorizationGuard(
        AuthorizationService(policy),
        audit=InMemoryApiAuthorizationAudit(),
    )
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
            bearer_token="g3-route-parity",
            principal_resolver=lambda _request: principal,
            approval_service=approvals,
            desktop_nonce="g3-route-parity-nonce",
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


def test_g3_successor_and_generated_clients_are_reproducible() -> None:
    check_successor()
    for key, expected in render().items():
        assert OUTPUTS[key].read_text(encoding="utf-8") == expected
    lock = _load(BASELINE / "BASELINE_LOCK.json")
    baseline = lock["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.8.0"
    assert baseline["approval_status"] == "APPROVED_LOCAL"
    assert baseline["activation_status"] == "ACTIVE"
    assert baseline["release_claim"] is False
    provenance = _load(BASELINE / "IMPORT_PROVENANCE.json")
    assert provenance["source_baseline"] == "CB-1.7.0"


def test_g3_security_authority_matches_the_runtime_route_graph_exactly() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = authority["active_routes"]
    assert isinstance(routes, list) and len(routes) == 89
    expected = {
        (item["method"], item["path"], item["module"], item["handler"])
        for item in routes
        if isinstance(item, dict)
    }
    assert _runtime_graph() == expected
    assert len({item["route_id"] for item in routes if isinstance(item, dict)}) == 89
    for number, path in enumerate(
        (
            "/api/v1/gui/bootstrap",
            "/api/v1/gui/catalog",
            "/api/v1/gui/selectors/views",
        ),
        start=87,
    ):
        binding = route_security("GET", path)
        assert binding is not None
        assert binding.route_id == f"api.route.{number:03d}"
        assert binding.permission is None
        assert binding.gui_permission_id == "gui.view"
        assert binding.audit_mode == "ALWAYS"


def test_only_three_g3_gui_routes_are_active_and_business_routes_remain_reserved() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json")
    routes = authority["routes"]
    reserved = authority["reserved_routes"]
    assert isinstance(routes, list)
    assert isinstance(reserved, list) and len(reserved) == 12
    active_gui = {
        item["path"]
        for item in routes
        if isinstance(item, dict) and str(item.get("path", "")).startswith("/api/v1/gui")
    }
    assert active_gui == {
        "/api/v1/gui/bootstrap",
        "/api/v1/gui/catalog",
        "/api/v1/gui/selectors/{selector_id}",
    }
    assert all(item.get("implementation_status") == "RESERVED_G3_NOT_EXPOSED" for item in reserved)


def test_g3_dto_and_gateway_policies_cover_required_failure_boundaries() -> None:
    dto = _load(BASELINE / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json")
    contracts = dto["contracts"]
    assert isinstance(contracts, dict)
    assert {
        "GuiCatalogDTO",
        "GuiBootstrapDTO",
        "GuiSelectorDTO",
        "GuiGatewayErrorDTO",
        "GuiCursorPageDTO",
        "SeriesRangeDTO",
        "MediaTicketDTO",
    }.issubset(contracts)
    gateway = _load(BASELINE / "canonical" / "GUI_ASYNC_GATEWAY_AUTHORITY.json")
    assert gateway["activation_status"] == "ACTIVE"
    assert gateway["request_policy"] == {
        "default_timeout_ms": 8000,
        "maximum_timeout_ms": 30000,
        "deduplicate_inflight": True,
        "cancel_superseded": True,
        "discard_stale_response": True,
        "retry_unsafe_methods": False,
    }
    cache = gateway["cache_policy"]
    assert isinstance(cache, dict)
    assert cache["partition_keys"] == ["principal_cache_key", "release_id"]
    assert cache["cross_principal"] == "FORBIDDEN"
    assert cache["cross_release"] == "FORBIDDEN"
