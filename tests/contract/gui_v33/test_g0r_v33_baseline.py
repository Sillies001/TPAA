from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = REPO_ROOT / "docs" / "gui" / "demo-v33" / "DEMO_TARGET_BASELINE.json"
REGISTRY_PATH = REPO_ROOT / "docs" / "gui" / "demo-v33" / "V33_FINAL_VIEW_REGISTRY.json"
MATRIX_PATH = REPO_ROOT / "docs" / "compliance" / "GUI_V33_CONFORMANCE_MATRIX.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_source(source: dict[str, Any]) -> Path:
    return REPO_ROOT / source["repository_mirror_path"]


def test_v33_demo_and_design_inputs_match_frozen_hashes() -> None:
    baseline = _load(BASELINE_PATH)
    sources = [baseline["source"], *baseline["design_inputs"]]

    for source in sources:
        path = _repository_source(source)
        assert path.is_file(), path
        assert path.stat().st_size == source["bytes"]
        assert _sha256(path) == source["sha256"]
        workspace_path = (REPO_ROOT / source["workspace_relative_path"]).resolve()
        if workspace_path.is_file():
            assert workspace_path.read_bytes() == path.read_bytes()


def test_v33_registry_freezes_all_26_views_and_landings() -> None:
    registry = _load(REGISTRY_PATH)
    views = registry["views"]
    by_id = {view["id"]: view for view in views}
    modules = {module["id"]: module for module in registry["modules"]}

    assert registry["view_count"] == 26
    assert tuple(by_id) == tuple(f"V{index:02d}" for index in range(1, 27))
    assert modules["training"]["landing"] == "V26"
    assert by_id["V24"]["entry"] == "CONDITIONAL_V08_ONLY"
    assert by_id["V25"]["title"] == "主题管理"
    assert by_id["V26"]["entry"] == "MODULE_LANDING_AND_V01_DEEPLINK"
    assert by_id["V04"]["perspectives"] == ["shooter", "target"]
    assert by_id["V08"]["perspectives"] == ["shooter", "target"]
    assert by_id["V06"]["perspectives"] == ["shooter"]
    assert by_id["V21"]["perspectives"] == ["shooter"]


def test_v33_conformance_matrix_has_exact_registry_parity() -> None:
    registry = _load(REGISTRY_PATH)
    matrix = _load(MATRIX_PATH)

    registry_ids = {view["id"] for view in registry["views"]}
    matrix_ids = {view["id"] for view in matrix["views"]}
    assert registry_ids == matrix_ids
    assert matrix["coverage"]["views"] == 26
    assert matrix["coverage"]["reference_screenshots_required"] == 78
    assert any(item["id"] == "V33-C02" for item in matrix["conflict_decisions"])


def test_v19_target_is_explicitly_superseded_not_deleted() -> None:
    notice = REPO_ROOT / "docs" / "gui" / "demo-v19" / "SUPERSEDED.md"
    text = notice.read_text(encoding="utf-8")

    assert "SUPERSEDED_REFERENCE_ONLY" in text
    assert "7AA5FF433FCAA49C3A54AC592ACB43C42EE98FD944D4FB66DE6E75BAC2401A9A" in text
    assert (REPO_ROOT / "docs" / "gui" / "demo-v19" / "DEMO_TARGET_BASELINE.json").is_file()


def test_v33_demo_contains_court_of_record_markers() -> None:
    demo = REPO_ROOT / "docs" / "gui" / "demo-v33" / "source" / "TPAA_训练复盘交互Demo_v33.html"
    text = demo.read_text(encoding="utf-8")

    assert "T.V25='主题管理'" in text
    assert "T.V26='批次发射事件总览'" in text
    assert "window.TPAA_V33={version:'V33'" in text
    assert "V.V26=" in text
    assert "data-batch-perspective" in text
    assert "T0-S" in text and "T0-T" in text and "T3" in text
