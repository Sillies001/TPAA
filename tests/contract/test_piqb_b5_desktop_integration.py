from __future__ import annotations

import ast
import json
from pathlib import Path

from tpaa_gui.product_shell import (
    PRODUCT_NAVIGATION,
    PRODUCT_SPINE,
    SEMANTIC_LAYERS,
    validate_product_navigation,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
SHELL = ROOT / "src" / "tpaa_gui" / "shell.py"
PRODUCT = ROOT / "src" / "tpaa_gui" / "product_shell.py"
VIS = ROOT / "src" / "tpaa_gui" / "visualization.py"
LOCAL = ROOT / "src" / "tpaa_gui" / "local_backend.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_b5_navigation_matches_frozen_p01_p13_contract() -> None:
    validate_product_navigation()
    contract = json.loads(
        (BASE / "B5_DESKTOP_NAVIGATION_CONTRACT.json").read_text(encoding="utf-8")
    )
    expected = [
        (
            item["slot"],
            item["key"],
            item["title"],
            item["surface"],
            item["semantic_class"],
        )
        for item in contract["slots"]
    ]
    actual = [
        (item.slot, item.key, item.title, item.surface, item.semantic_class)
        for item in PRODUCT_NAVIGATION
    ]
    assert actual == expected
    assert list(PRODUCT_SPINE) == contract["spine"]
    assert set(SEMANTIC_LAYERS) == set(contract["rules"].get("semantic_layers", SEMANTIC_LAYERS))


def test_product_shell_and_visualization_remain_presentation_only() -> None:
    forbidden = {
        "tpaa_api",
        "tpaa_application",
        "tpaa_storage",
        "tpaa_canonical",
        "tpaa_metric",
        "tpaa_world",
        "sqlite3",
        "psycopg",
        "fastapi",
    }
    for path in (PRODUCT, VIS):
        imports = _imports(path)
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            for name in imports
            for prefix in forbidden
        )


def test_real_desktop_shell_selects_product_composition_without_removing_m1_compatibility() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    assert "product_transport" in shell
    assert "create_product_workspace" in shell
    assert "elif m1_transport is not None" in shell
    local = LOCAL.read_text(encoding="utf-8")
    for method in (
        "m3_request_json",
        "m4_request_json",
        "m6_request_json",
        "m7_request_json",
        "m8_request_json",
        "m9_request_json",
        "runtime_request_json",
    ):
        assert f"def {method}" in local
    assert '"/runtime/qualification"' in local
    assert '"/runtime/observability"' in local


def test_b5_surface_contains_required_cross_cutting_views_and_semantic_separation() -> None:
    product = PRODUCT.read_text(encoding="utf-8")
    visualization = VIS.read_text(encoding="utf-8")
    for token in (
        "create_m1_workspace",
        "create_m3_workspace_navigation",
        "create_m4_workspace",
        "create_m6_workspace",
        "create_m7_workspace",
        "create_m8_workspace",
        "create_m9_workspace",
        "tpaaB5ProductSpine",
        "tpaaB5SemanticLegend",
        "Trajectory / Media",
    ):
        assert token in product
    for token in (
        "SESSION_TIME_RELATIVE_ONLY",
        "business_recompute",
        "persistence_access",
        "mutable_alias_resolution",
        "build_2d_polyline",
        "build_cesium_trajectory_packets",
    ):
        assert token in visualization
