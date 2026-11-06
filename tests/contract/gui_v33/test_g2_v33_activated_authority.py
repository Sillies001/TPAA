from __future__ import annotations

import json
import re
from pathlib import Path

from tools.baseline.adopt_g2_successor import _runtime_routes, check_successor
from tools.codegen.g2_security_generate import OUTPUT, render
from tpaa_security import (
    SecurityRole,
    derive_gui_permissions,
    load_security_policy,
    route_security,
)

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.7.0"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _concrete(template: str) -> str:
    return re.sub(r"\{[^}/]+\}", "exact-id", template)


def test_approved_successor_and_generated_runtime_authority_are_reproducible() -> None:
    check_successor()
    assert OUTPUT.read_text(encoding="utf-8") == render()
    lock = _load(BASELINE / "BASELINE_LOCK.json")
    baseline = lock["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.7.0"
    assert baseline["approval_status"] == "APPROVED_LOCAL"
    assert baseline["activation_status"] == "ACTIVE"
    assert baseline["release_claim"] is False


def test_explicit_route_authority_matches_registered_fastapi_graph_exactly() -> None:
    authority = _load(
        BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"
    )
    routes = authority["active_routes"]
    assert isinstance(routes, list)
    assert len(routes) == 86
    actual = {(item["method"], item["path"]) for item in _runtime_routes()}
    expected = {
        (item["method"], item["path"])
        for item in routes
        if isinstance(item, dict)
    }
    assert actual == expected
    assert len({item["route_id"] for item in routes if isinstance(item, dict)}) == 86
    for item in routes:
        assert isinstance(item, dict)
        binding = route_security(str(item["method"]), _concrete(str(item["path"])))
        assert binding is not None
        assert binding.route_id == item["route_id"]
        assert (
            None if binding.permission is None else binding.permission.value
        ) == item["permission_id"]
        assert binding.audit_mode == item["audit_mode"]


def test_approved_gui_role_view_matrix_covers_nine_roles_and_26_views() -> None:
    matrix = _load(
        BASELINE / "canonical" / "GUI_ROLE_VIEW_ACCESS_MATRIX.json"
    )
    views = matrix["views"]
    summary = matrix["role_summary"]
    assert matrix["approval_status"] == "APPROVED_LOCAL"
    assert matrix["activation_status"] == "ACTIVE"
    assert isinstance(views, list) and len(views) == 26
    assert isinstance(summary, list) and len(summary) == 9
    assert {item["role_id"] for item in summary if isinstance(item, dict)} == {
        "TRAINEE",
        "INSTRUCTOR",
        "EVALUATOR",
        "TRAINING_MANAGER",
        "UNIT_ANALYST",
        "MAINTENANCE_ENGINEERING",
        "DATA_ENGINEER",
        "ADMINISTRATOR",
        "MODEL_REVIEWER",
    }
    assert all(
        item.get("required_permissions")
        for item in views
        if isinstance(item, dict)
    )


def test_all_nine_runtime_role_grants_match_the_approved_view_matrix() -> None:
    matrix = _load(
        BASELINE / "canonical" / "GUI_ROLE_VIEW_ACCESS_MATRIX.json"
    )
    contract = _load(BASELINE / "canonical" / "GUI_VIEW_CONTRACT.json")
    summaries = matrix["role_summary"]
    views = contract["views"]
    assert isinstance(summaries, list)
    assert isinstance(views, list)
    expected_by_role = {
        str(item["role_id"]): set(item["view_ids"])
        for item in summaries
        if isinstance(item, dict) and isinstance(item.get("view_ids"), list)
    }
    policy = load_security_policy()
    for role in SecurityRole:
        grants = set(
            derive_gui_permissions(
                (role,),
                policy.role_permissions[role],
            )
        )
        actual_views = {
            str(item["view_id"])
            for item in views
            if isinstance(item, dict)
            and isinstance(item.get("required_permissions"), list)
            and set(item["required_permissions"]).issubset(grants)
        }
        assert actual_views == expected_by_role[role.value]
