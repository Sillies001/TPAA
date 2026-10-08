from __future__ import annotations

from pathlib import Path

from tools.packaging.prcb_runtime_entry import _desktop_e2e

ROOT = Path(__file__).resolve().parents[3]
SOURCE = (
    ROOT
    / "docs"
    / "baseline"
    / "PRCB-1.0"
    / "qualification"
    / "PRCB_C2_NOMINAL_FLIGHT.json"
)


def test_prcb_c5_installed_desktop_p1_p6_restart_recovery_audit(
    tmp_path: Path,
) -> None:
    result = _desktop_e2e(tmp_path / "installed-e2e", SOURCE)
    assert result["schema"] == "TPAA_PRCB_C5_INSTALLED_DESKTOP_P1_P6_E2E_V1"
    assert result["status"] == "PASS"
    assert result["product_version"] == "1.0.1"
    assert result["db_schema_version"] == "1.9.0"
    assert result["canonical_baseline"] == "CB-1.4.0"
    assert result["job_status"] == "SUCCEEDED"
    assert result["catalog_definition_count"] == 116
    assert result["metric_code_count"] == 116
    assert result["metric_count"] >= 116
    assert result["capability_observation_count"] > 0
    assert result["system_observation_count"] > 0
    assert result["evidence_only_metric_instance_count"] > 0
    assert result["p2_job_status"] == "SUCCEEDED"
    assert result["p2_qualification_as_of_utc"] == "2026-12-31T23:58:00Z"
    assert result["p2_execution_time_utc"] == "2026-12-31T23:59:00Z"
    assert result["p2_estimate_status"] in {"IDENTIFIABLE", "NOT_IDENTIFIABLE"}
    assert result["p3_job_status"] == "SUCCEEDED"
    assert result["p4_job_status"] == "SUCCEEDED"
    assert result["p5_job_status"] == "SUCCEEDED"
    assert result["p6_forecast_job_status"] == "SUCCEEDED"
    assert result["p6_counterfactual_job_status"] == "SUCCEEDED"
    assert result["p2_restart_exact_replay"] is True
    assert result["p2_backup_restore_exact_replay"] is True
    assert result["p3_p6_restart_exact_replay"] is True
    assert result["p3_p6_backup_restore_exact_replay"] is True
    assert result["restart_exact_replay"] is True
    assert result["backup_restore_exact_replay"] is True
    assert result["api_exact_read_verified"] is True
    assert result["desktop_discovery_verified"] is True
    assert result["desktop_authentication_verified"] is True
    assert result["desktop_latest_alias_rejected"] is True
    assert result["api_exact_read_restart_replay"] is True
    assert result["desktop_discovery_restart_replay"] is True
    assert result["api_exact_read_backup_restore_replay"] is True
    assert result["desktop_discovery_backup_restore_replay"] is True
    assert isinstance(result["api_discovery_fingerprint"], str)
    assert len(result["api_discovery_fingerprint"]) == 64
    assert result["persistent_audit_verified"] is True
    assert result["tests_fixture_dependency"] is False
    assert result["formal_release_claimed"] is False
