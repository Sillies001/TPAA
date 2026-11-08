"""G5 CB-1.10.0 Weapon-Event successor, codegen reproducibility and fail-closed exposure."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.routing import APIRoute

from tools.baseline.adopt_g5_successor import check_successor
from tools.codegen.g5_weapon_event_generate import OUTPUTS, render
from tpaa_api import UnifiedPrincipal, create_desktop_app, create_unified_service_app
from tpaa_application import ApplicationService, WeaponEventApplicationService
from tpaa_security import (
    ApiAuthorizationGuard,
    ApprovalService,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    InMemoryApprovalEventRepository,
    load_security_policy,
)

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.10.0"

G5_PATHS = {
    "/api/v1/gui/weapon-events/{weapon_event_id}",
    "/api/v1/gui/weapon-events/{weapon_event_id}/windows/{perspective}",
    "/api/v1/gui/weapon-events/{weapon_event_id}/perspectives/{perspective}",
}


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _runtime_graph() -> set[tuple[str, str, str, str]]:
    policy = load_security_policy()
    approvals = ApprovalService(
        AuthorizationService(policy),
        InMemoryApprovalEventRepository(),
    )
    guard = ApiAuthorizationGuard(
        AuthorizationService(policy),
        audit=InMemoryApiAuthorizationAudit(),
    )
    principal = UnifiedPrincipal(
        role="ADMINISTRATOR",
        actor_id="g5-route-exposure-check",
        scope_match=True,
    )
    class _UnusedStorage:
        def execute(self) -> object:
            raise AssertionError

    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        weapon_event=WeaponEventApplicationService(),
    )
    apps = (
        create_unified_service_app(
            application=application,
            principal_resolver=lambda _request: principal,
            authorization_guard=guard,
            approval_service=approvals,
        ),
        create_desktop_app(
            application=application,
            bearer_token="g5-route-exposure-check",
            principal_resolver=lambda _request: principal,
            approval_service=approvals,
            desktop_nonce="g5-route-exposure-check-nonce",
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


def test_g5_successor_and_generated_runtime_are_reproducible() -> None:
    check_successor()
    for key, expected in render().items():
        assert OUTPUTS[key].read_text(encoding="utf-8") == expected
    baseline = _load(BASELINE / "BASELINE_LOCK.json")["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.10.0"
    assert baseline["db_schema"] == "1.10.0"
    assert baseline["approval_status"] == "APPROVED_LOCAL"
    assert baseline["release_claim"] is False


def test_g5_security_authority_appends_three_weapon_event_routes() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = authority["active_routes"]
    assert isinstance(routes, list) and len(routes) == 99
    g5 = [item for item in routes if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G5"]
    assert len(g5) == 3
    assert {str(item["path"]) for item in g5} == G5_PATHS
    assert all(item["module"] == "tpaa_api.gui_weapon_event" for item in g5)
    assert all(item["audit_mode"] == "ALWAYS" for item in g5)
    # Per-route permission mapping must mirror GUI_PERMISSION_AUDIT_AUTHORITY:
    # detail=DDR+weapon_event.read, window=RAW+weapon_event.window.read,
    # perspective=DDR+weapon_event.perspective.read.  No blanket weapon_event.read.
    mapping = {
        str(item["path"]): (item["permission_id"], item["gui_permission_id"]) for item in g5
    }
    assert mapping == {
        "/api/v1/gui/weapon-events/{weapon_event_id}": ("DERIVED_DATA_READ", "weapon_event.read"),
        "/api/v1/gui/weapon-events/{weapon_event_id}/windows/{perspective}": ("RAW_DATA_READ", "weapon_event.window.read"),
        "/api/v1/gui/weapon-events/{weapon_event_id}/perspectives/{perspective}": ("DERIVED_DATA_READ", "weapon_event.perspective.read"),
    }
    for number, item in enumerate(g5, start=97):
        assert str(item["route_id"]) == f"api.route.{number:03d}"


def test_g5_keeps_v26_overview_and_replay_reserved_fail_closed() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json")
    reserved = authority["reserved_routes"]
    assert isinstance(reserved, list) and len(reserved) == 3
    assert {str(item["route_id"]) for item in reserved} == {
        "gui.overview",
        "gui.batch.events",
        "gui.replay",
    }
    assert all(item.get("implementation_status") == "RESERVED_G5_NOT_EXPOSED" for item in reserved)


def test_g5_routes_are_exposed_only_when_the_application_capability_is_active() -> None:
    graph = _runtime_graph()
    exposed_paths = {path for _method, path, _module, _name in graph}
    assert G5_PATHS <= exposed_paths
    assert {
        module
        for _method, path, module, _name in graph
        if path in G5_PATHS
    } == {"tpaa_api.gui_weapon_event"}


def test_g5_authority_enforces_single_owner_and_cardinality_rules() -> None:
    authority = _load(BASELINE / "canonical" / "GUI_WEAPON_EVENT_AUTHORITY.json")
    rules = authority["rules"]
    owners = authority["single_owner_rules"]
    database = authority["database"]
    assert isinstance(rules, dict) and isinstance(owners, dict) and isinstance(database, dict)
    assert rules["we_cardinality"] == "ONE_PER_WEAPON_LAUNCH"
    assert rules["cluster_cardinality"] == "RELATION_ONLY_MULTIPLE_WE"
    assert rules["cross_batch_we_borrowing"] == "FORBIDDEN"
    assert rules["exact_identity_no_latest_fallback"] is True
    assert rules["terminal_adjudication_window_independent"] is True
    assert owners["weapon_event_detector"] == "tpaa_application.weapon_event"
    assert owners["event_window_resolver"] == "tpaa_application.event_window"
    assert owners["perspective_projection"] == "tpaa_application.perspective"
    assert owners["gui_business_recomputation"] == "FORBIDDEN"
    assert database["schema"] == "1.10.0"
    assert database["migration_required"] is False


def test_g5_authority_regressions_from_first_review_are_locked() -> None:
    """Invariants added after the first Codex review (REJECT) must stay enforced."""

    authority = _load(BASELINE / "canonical" / "GUI_WEAPON_EVENT_AUTHORITY.json")
    rules = authority["rules"]
    assert rules["cross_batch_ingress_rejection"] == "DETECTOR_IDENTITY_IMMEDIATE_AUDITED"
    assert rules["identity_supersession"] == (
        "SOURCE_REVISION_YIELDS_NEW_UUID_SUPERSEDES_OLD_NO_INPLACE_MUTATION"
    )
    assert rules["cluster_identity_stability"] == "UUID_FROM_SORTED_WE_ID_SET_ONLY"
    assert rules["dto_single_source"] == "CANONICAL_CONTRACT_GENERATES_PYTHON_AND_TYPESCRIPT"
    assert rules["capability_states"] == ["CAPABILITY_DISABLED", "ADAPTER_UNAVAILABLE", "EMPTY", "READY"]
    assert rules["http_404_semantics"] == "EXACT_WEAPON_EVENT_ABSENT_UNDER_READY_BACKEND"
    capability_status = authority["capability_status"]
    assert isinstance(capability_status, dict)
    assert set(capability_status.values()) == {"ACTIVE"}


def test_g5_typescript_declares_decimal_string_session_time() -> None:
    source = (ROOT / "frontend" / "gui-v33" / "src" / "generated" / "g5-weapon-event.ts").read_text(
        encoding="utf-8"
    )
    assert "export interface WeaponEventDetailDTO" in source
    assert "start_session_time_us: string" in source
    assert "G5_WEAPON_EVENT_ROUTES" in source
    assert not re.search(r"session_time_us:\s*number", source)
    python_dto = (ROOT / "src" / "tpaa_application" / "generated_g5_dto.py").read_text(
        encoding="utf-8"
    )
    assert "class WeaponEventDetailDTO(TypedDict)" in python_dto
    assert "t1_session_time_us: str" in python_dto
