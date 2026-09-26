from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_met_006_incremental_runtime_contract_is_honest_and_exact(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime-contract.json"
    completed = _run(
        "m2-runtime-contract-incremental-check",
        "--evidence",
        str(path),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(path.read_text(encoding="utf-8"))

    assert evidence["schema"] == (
        "TPAA_M2_MET_006_RUNTIME_CONTRACT_INCREMENTAL_EVIDENCE_V1"
    )
    assert evidence["task_id"] == "M2-MET-006"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["blocked_predecessors"] == ["M2-MET-002", "M2-MET-005"]
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    assert evidence["acceptance"]["structured_schema_closed_world_authority_enforced"]

    product = evidence["logical_product"]
    assert len(product["runtime_metric_codes"]) == 32
    assert len(product["subject_types"]) == 32
    assert set(product["subject_types"].values()) == {
        "AIRCRAFT",
        "MISSION_SYSTEM_INSTANCE",
        "TARGET_PAIR",
    }
    assert len(product["observation_lanes"]) == 32
    assert set(product["observation_lanes"].values()) == {
        "AIRCRAFT_CAP_L1_OBSERVATION",
        "SYSTEM_PERFORMANCE_OBSERVATION",
        "QUALITY_EVIDENCE_ONLY",
    }
    assert len(product["publication_routes"]) == 32
    assert set(product["publication_routes"].values()) == {
        "CAPABILITY_OBSERVATION",
        "SYSTEM_PERFORMANCE_OBSERVATION",
        "METRIC_INSTANCE_EVIDENCE_ONLY",
    }
    assert len(product["longitudinal_trend_eligibility"]) == 32
    assert sum(product["longitudinal_trend_eligibility"].values()) == 26
    assert len(product["default_aggregations"]) == 32
    assert list(product["default_aggregations"].values()).count("MEDIAN") == 26
    assert list(product["default_aggregations"].values()).count("NONE") == 6
    assert evidence["acceptance"]["target_pair_never_longitudinal"]
    assert evidence["acceptance"]["trend_subject_types_exact"]
    assert evidence["acceptance"]["profile_input_exact_name_contract_enforced"]
    assert evidence["acceptance"]["reference_match_profile_identity_binding_exact_17"]
    assert product["profile_parameter_bindings"] == {
        "P1-QA-005": ["max_gap_us"],
        "P1-AIR-001": ["max_gap_us", "min_coverage"],
        "P1-AIR-003": ["derivative_window_s", "max_gap_us"],
    }
    reference_match_bindings = product["reference_match_profile_identity_bindings"]
    assert set(reference_match_bindings) == {
        f"P1-SNS-{index:03d}" for index in range(5, 22)
    }
    assert all(
        {item["input_field"] for item in bindings}
        == {
            "reference_match_quality_profile_id",
            "reference_match_quality_profile_version",
            "reference_match_quality_profile_hash",
        }
        for bindings in reference_match_bindings.values()
    )
    assert all(
        not product["longitudinal_trend_eligibility"][code]
        for code, subject_type in product["subject_types"].items()
        if subject_type == "TARGET_PAIR"
    )
    assert product["negative_error_codes"]["observation_lane_mismatch"] == (
        "M2_METRIC_RUNTIME_OBSERVATION_LANE_MISMATCH"
    )
    assert product["negative_error_codes"]["publication_route_mismatch"] == (
        "M2_METRIC_RUNTIME_PUBLICATION_ROUTE_MISMATCH"
    )
    assert len(product["numeric_metric_codes"]) == 29
    assert set(product["structured_schema_hashes"]) == {
        "P1-QA-001",
        "P1-QA-002",
        "P1-QA-006",
    }
    assert len(product["sns_applicability_metric_codes"]) == 21
    assert len(product["core_logical_model_sha256"]) == 64
    assert len(product["core_rules_sha256"]) == 64
    assert product["negative_error_codes"]["radar_missing_applicable"] == (
        "M2_METRIC_APPLICABLE_OUTPUT_REJECTED"
    )
    assert product["negative_error_codes"]["non_radar_missing_subject_type"] == (
        "M2_METRIC_RUNTIME_SUBJECT_TYPE_MISMATCH"
    )
    assert product["allowed_result_statuses"] == [
        "VALID",
        "N_A",
        "INSUFFICIENT_DATA",
        "INVALID",
        "REVIEW_REQUIRED",
    ]
    assert product["allowed_mission_system_types"] == [
        "RADAR",
        "IRST",
        "EO",
        "RWR",
        "ESM",
        "DATALINK",
        "FUSION",
        "MISSION_COMPUTER",
        "OTHER",
    ]
    assert product["negative_error_codes"]["unknown_system_type"] == (
        "M2_METRIC_APPLICABILITY_INPUT_INVALID"
    )
    assert evidence["scope"] == {
        "business_metric_semantics_executed": False,
        "business_status_selection_semantics_executed": False,
        "subject_metadata_binding_only": True,
        "publication_metadata_binding_only": True,
        "longitudinal_metadata_binding_only": True,
        "profile_parameter_name_binding_only": True,
        "reference_match_profile_identity_binding_only": True,
        "authority_values_invented": False,
        "runtime_transport_contract_only": True,
    }


def test_m2_met_006_incremental_cross_platform_compare_is_revision_exact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-runtime-contract-incremental-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"

    completed = _run(
        "m2-runtime-contract-incremental-compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
