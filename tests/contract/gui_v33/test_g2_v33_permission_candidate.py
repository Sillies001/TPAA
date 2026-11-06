from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARENT = ROOT / "baseline" / "CB-1.6.0" / "canonical" / "API_ROUTE_AUTHORITY.json"
CANDIDATE = ROOT / "baseline" / "candidates" / "CB-1.7.0"
ROUTES = CANDIDATE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"
VIEWS = CANDIDATE / "canonical" / "GUI_VIEW_CONTRACT.json"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_candidate_route_authority_covers_frozen_graph_and_defaults_deny() -> None:
    parent = _load(PARENT)
    authority = _load(ROUTES)
    routes = authority["active_routes"]
    assert authority["approval_status"] == "PROPOSED_NOT_APPROVED"
    assert authority["activation_status"] == "INACTIVE"
    assert authority["default_unknown_route_policy"] == "DENY"
    assert isinstance(routes, list)
    assert len(routes) == len(parent["routes"]) == 71
    assert [(item["method"], item["path"]) for item in routes] == [
        (item["method"], item["path"]) for item in parent["routes"]
    ]
    route_ids = [item["route_id"] for item in routes]
    assert len(route_ids) == len(set(route_ids))
    assert all(item["authorization_mode"] != "HEURISTIC" for item in routes)
    assert all(
        item["audit_mode"] == "ALWAYS"
        for item in routes
        if item["permission_id"] is not None
    )


def test_candidate_keeps_reserved_gui_routes_and_view_invariants() -> None:
    parent = _load(PARENT)
    authority = _load(ROUTES)
    views = _load(VIEWS)["views"]
    assert authority["reserved_gui_routes"] == parent["reserved_routes"]
    assert all(
        item["implementation_status"] == "RESERVED_G1_NOT_EXPOSED"
        for item in authority["reserved_gui_routes"]
    )
    assert len(views) == 26
    assert all(item["required_permissions"] for item in views)
    v24 = next(item for item in views if item["view_id"] == "V24")
    assert v24["allowed_predecessor"] == ["V08"]
    assert v24["return_target"] == "V08"
    assert next(item for item in views if item["view_id"] == "V06")["perspectives"] == ["shooter"]
    assert next(item for item in views if item["view_id"] == "V21")["perspectives"] == ["shooter"]
