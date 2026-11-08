"""G10 CB-1.15.0 view-closure successor and NOT_ADMITTED authority contract."""

from __future__ import annotations

import json
from pathlib import Path

from tools.baseline.adopt_g10_successor import check_successor

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.15.0"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_g10_successor_locks_parent_and_keeps_route_count() -> None:
    check_successor()
    baseline = _load(BASELINE / "BASELINE_LOCK.json")["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.15.0"
    assert baseline["db_schema"] == "1.10.0"
    assert baseline["release_claim"] is False
    security = _load(BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = security["active_routes"]
    assert isinstance(routes, list) and len(routes) == 103
    assert all(
        not isinstance(item, dict) or item.get("implementation_status") != "IMPLEMENTED_G10"
        for item in routes
    )
    route_authority = _load(BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json")
    assert route_authority["reserved_routes"] == []


def test_g10_p3_report_governance_recorded_not_admitted() -> None:
    for name in (
        "GUI_P3_PROFILE_AUTHORITY.json",
        "GUI_REPORT_REVISION_AUTHORITY.json",
        "GUI_GOVERNANCE_AUTHORITY.json",
    ):
        authority = _load(BASELINE / "canonical" / name)
        assert authority["admission_status"] == "NOT_ADMITTED"
        assert authority["rules"]["controlled_unavailable_only"] is True
        assert authority["rules"]["no_synthetic_profile"] is True
        assert authority["release_claim"] is False


def test_g10_frontend_closure_covers_all_remaining_views() -> None:
    source = (ROOT / "frontend" / "gui-v33" / "src" / "main.ts").read_text(encoding="utf-8")
    for view_id in (
        "V02", "V07", "V09", "V10", "V11", "V12", "V13", "V14", "V15",
        "V16", "V17", "V18", "V19", "V22",
    ):
        assert view_id in source, f"missing closure renderer for {view_id}"
    for token in (
        "GUI_P3_PROFILE_AUTHORITY",
        "GUI_REPORT_REVISION_AUTHORITY",
        "GUI_GOVERNANCE_AUTHORITY",
        "G10_NOT_ADMITTED",
        "renderViewClosure",
    ):
        assert token in source
    # P3 未准入：不合成剖面
    assert "no_synthetic_profile" not in source  # 前端不内嵌 authority 原文，仅引用 ID
