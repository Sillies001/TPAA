from __future__ import annotations

from tools.gui.g0r_v33_verify import verify


def test_g0r_v33_runtime_and_lineage_evidence_is_complete() -> None:
    result = verify()

    assert result["status"] == "PASS"
    assert result["baseline_id"] == "GUI-DEMO-V33-2026-11-05"
    assert result["view_count"] == 26
    assert result["theme_count"] == 3
    assert result["webengine_reference_screenshots"] == 81
    assert result["qml_contract_screenshots"] == 12
    assert result["v01_geometry_viewports"] == ["1600x900", "1280x720"]
    assert result["release_claim"] is False
    assert result["predecessor_manifest"]["status"] == "PASS"
    assert result["predecessor_manifest"]["artifacts"] >= 26
    assert all(item["status"] == "PASS" for item in result["source_checks"])
    assert all(item["status"] == "PASS" for item in result["runtime_evidence"])
