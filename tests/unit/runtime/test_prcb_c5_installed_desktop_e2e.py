from __future__ import annotations

from pathlib import Path

from tools.packaging.prcb_runtime_entry import _desktop_p1_e2e

ROOT = Path(__file__).resolve().parents[3]
SOURCE = (
    ROOT
    / "docs"
    / "baseline"
    / "PRCB-1.0"
    / "qualification"
    / "PRCB_C2_NOMINAL_FLIGHT.json"
)


def test_prcb_c5_installed_desktop_p1_restart_recovery_audit(
    tmp_path: Path,
) -> None:
    result = _desktop_p1_e2e(tmp_path / "installed-e2e", SOURCE)
    assert result["schema"] == "TPAA_PRCB_C5_INSTALLED_DESKTOP_P1_P2_E2E_V1"
    assert result["status"] == "PASS"
    assert result["product_version"] == "1.0.1"
    assert result["db_schema_version"] == "1.9.0"
    assert result["canonical_baseline"] == "CB-1.4.0"
    assert result["job_status"] == "SUCCEEDED"
    assert result["metric_count"] == 5
    assert result["p2_job_status"] == "SUCCEEDED"
    assert result["p2_estimate_status"] in {"IDENTIFIABLE", "NOT_IDENTIFIABLE"}
    assert result["p2_restart_exact_replay"] is True
    assert result["p2_backup_restore_exact_replay"] is True
    assert result["restart_exact_replay"] is True
    assert result["backup_restore_exact_replay"] is True
    assert result["persistent_audit_verified"] is True
    assert result["tests_fixture_dependency"] is False
    assert result["formal_release_claimed"] is False
