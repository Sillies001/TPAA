from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.gui.g2_v33_verify import G2VerificationError, _object_list

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend" / "gui-v33" / "src"
REGISTRY = ROOT / "docs" / "gui" / "demo-v33" / "V33_FINAL_VIEW_REGISTRY.json"
VIEW_CONTRACT = ROOT / "baseline" / "CB-1.6.0" / "canonical" / "GUI_VIEW_CONTRACT.json"
PERMISSIONS = ROOT / "baseline" / "CB-1.6.0" / "canonical" / "GUI_PERMISSION_AUDIT_AUTHORITY.json"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_g2_navigation_uses_frozen_v33_registry_and_machine_contract() -> None:
    registry = _load(REGISTRY)
    contract = _load(VIEW_CONTRACT)
    views = registry["views"]
    contracts = contract["views"]
    assert isinstance(views, list) and isinstance(contracts, list)
    ids = [f"V{index:02d}" for index in range(1, 27)]
    assert [item["id"] for item in views] == ids
    assert [item["view_id"] for item in contracts] == ids
    modules = {item["id"]: item for item in registry["modules"]}
    assert len(modules) == 5
    assert modules["training"]["landing"] == "V26"
    v24 = next(item for item in contracts if item["view_id"] == "V24")
    assert v24["entry_type"] == "CONDITIONAL_V08_ONLY"
    assert v24["allowed_predecessor"] == ["V08"]
    assert v24["return_target"] == "V08"


def test_g2_shell_is_fail_closed_and_has_no_browser_business_persistence() -> None:
    source = (FRONTEND / "main.ts").read_text(encoding="utf-8")
    css = (FRONTEND / "style.css").read_text(encoding="utf-8")
    assert "V33_FINAL_VIEW_REGISTRY.json" in source
    assert "GUI_VIEW_CONTRACT.json" in source
    assert "GUI_PERMISSION_AUDIT_AUTHORITY.json" in source
    assert 'view.id !== "V24"' in source
    assert "V24_REQUIRES_V08_CONTEXT" in source
    assert 'fetch("/security/session"' in source
    assert "required_permissions.every" in source
    assert 'unknown_policy === "DENY"' in source
    assert 'theme: "graphite"' in source
    assert all(token in source for token in ('"tactical"', '"graphite"', '"light"'))
    assert all(
        token in source
        for token in ("domainSelection", "replayState", "returnStack", "ribbonCollapsed")
    )
    assert all(
        token in source
        for token in (
            "sortieId", "formationId", "memberId", "evaluatedSide", "mediaId",
            "transcriptId", "expandedPanels", "reportZoom", "tableLayout",
            "approvedPredecessor", "deepLink",
        )
    )
    assert not re.search(
        r"\b(?:localStorage|sessionStorage)\.(?:setItem|removeItem|clear)\s*\(",
        source,
    )
    assert "Math.random(" not in source
    assert all(
        f':root[data-tpaa-theme="{theme}"]' in css
        for theme in ("tactical", "graphite", "light")
    )
    assert ":focus-visible" in css
    assert "focusTarget" in source and ".focus()" in source
    assert 'const root: HTMLDivElement = rootElement' in source
    assert re.search(r"@media\\s*\\(prefers-reduced-motion\\s*:\\s*reduce\\)", css)
    assert "@media(max-width:760px)" in css


def test_g2_permission_catalog_keeps_unknown_policy_default_deny() -> None:
    permissions = _load(PERMISSIONS)["permissions"]
    assert isinstance(permissions, list) and permissions
    assert all(item["unknown_policy"] == "DENY" for item in permissions)


def test_g2_verifier_rejects_missing_or_malformed_json_object_arrays() -> None:
    assert _object_list([{"view_id": "V24"}], "contract.views") == [{"view_id": "V24"}]
    with pytest.raises(G2VerificationError, match="contract.views"):
        _object_list(None, "contract.views")
    with pytest.raises(G2VerificationError, match="contract.views"):
        _object_list([None], "contract.views")
