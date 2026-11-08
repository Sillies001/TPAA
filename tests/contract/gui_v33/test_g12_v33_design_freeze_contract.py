"""G12 CB-1.17.0 design-freeze successor, W9 re-aggregation and route-stability contract."""

from __future__ import annotations

import json
from pathlib import Path

from tools.baseline.adopt_g12_successor import check_successor

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.17.0"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_g12_successor_locks_parent_and_freezes_routes() -> None:
    check_successor()
    baseline = _load(BASELINE / "BASELINE_LOCK.json")["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.17.0"
    assert baseline["db_schema"] == "1.10.0"
    lineage = baseline.get("lock_lineage_sha256")
    assert isinstance(lineage, list) and len(lineage) == 1
    security = _load(BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = security["active_routes"]
    assert isinstance(routes, list) and len(routes) == 103


def test_g12_design_freeze_authority() -> None:
    authority = _load(BASELINE / "canonical" / "G12_DESIGN_FREEZE_AUTHORITY.json")
    rules = authority["rules"]
    assert rules["view_registry_frozen_26"] is True
    assert rules["full_visual_matrix_required"] == "26x3x2"
    assert authority["activation_status"] == "ACTIVE"


def test_g12_w9_reaggregation_stays_no_go() -> None:
    document = _load(BASELINE / "canonical" / "W9_REAGGREGATION.json")
    assert document["w9_status"] == "NO_GO"
    assert document["product_complete"] is False
    assert document["release_ready"] is False
    doors = document["external_doors_open"]
    assert isinstance(doors, list) and len(doors) >= 4
