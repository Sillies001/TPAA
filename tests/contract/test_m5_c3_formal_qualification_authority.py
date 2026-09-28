from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY = BASELINE / "canonical" / "M5_FORMAL_QUALIFICATION_AUTHORITY.json"
VALIDATOR_PATH = ROOT / "tools" / "baseline" / "validate_m5_formal_qualification_authority.py"

SPEC = importlib.util.spec_from_file_location("m5_c3_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _payload() -> dict[str, object]:
    value = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m5_c3_authority_is_controlled_and_loadable() -> None:
    raw = AUTHORITY.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1"
    artifact = CanonicalArtifactLoader(BASELINE).load(
        "M5_FORMAL_QUALIFICATION_AUTHORITY",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "target_hardware_profile",
                "workload_profile",
                "performance_resource_profile",
                "security_release_readiness_profile",
                "package_lifecycle_profile",
                "upgrade_backup_restore_profile",
                "formal_release_acceptance_profile",
                "profile_hashes",
                "golden_vectors",
            ),
        ),
    )
    assert artifact.sha256 == "e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1"


def test_m5_c3_validator_passes_all_frozen_profiles() -> None:
    result = VALIDATOR.verify(AUTHORITY)
    assert result["status"] == "PASS"
    assert result["failed_checks"] == []
    assert result["task_complete"] is False
    assert all(result["checks"].values())


def test_m5_c3_exact_four_profiles_and_p1_only() -> None:
    p = _payload()
    assert p["scope"]["mandatory_certification_profiles"] == [
        "WINDOWS_DESKTOP_X64",
        "LINUX_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
        "LINUX_SERVICE_X64",
    ]
    assert p["scope"]["admitted_capability_phase"] == ["P1"]
    assert p["scope"]["excluded_capability_phases"] == [
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
    ]
    assert p["scope"]["db_schema_change"] is False
    assert p["scope"]["shadow_schema_permitted"] is False


def test_m5_c3_performance_boundary_and_fail_closed_delta() -> None:
    p = _payload()
    service = p["performance_resource_profile"]["service_thresholds"]
    golden = p["golden_vectors"]
    assert golden["performance_boundary_pass"]["api_query_latency_p95_ms"] == service[
        "api_query_latency_p95_ms_max"
    ]
    assert golden["performance_boundary_pass"]["api_query_throughput_per_second"] == service[
        "api_query_throughput_per_second_min"
    ]
    assert golden["performance_over_limit_fail"]["api_query_latency_p95_ms"] > service[
        "api_query_latency_p95_ms_max"
    ]
    assert golden["performance_over_limit_fail"]["expected_error"] == (
        "FAIL_CLOSED_M5_PERFORMANCE_THRESHOLD"
    )


def test_m5_c3_security_and_offline_package_are_fail_closed() -> None:
    p = _payload()
    vuln = p["security_release_readiness_profile"]["vulnerability_acceptance"]
    assert vuln["critical_unwaived_count_max"] == 0
    assert vuln["high_unwaived_count_max"] == 0
    assert vuln["medium_unwaived_count_max"] == 0
    assert vuln["waiver_allowed_severities"] == ["MEDIUM"]
    prereq = p["package_lifecycle_profile"]["target_prerequisites"]
    assert prereq == {
        "preexisting_project_virtualenv_required": False,
        "preexisting_uv_required": False,
        "preexisting_python_required": False,
        "network_access_required": False,
    }
    assert (
        p["golden_vectors"]["package_network_dependency_fail"]["expected_error"]
        == "FAIL_CLOSED_M5_OFFLINE_PACKAGE_REQUIRED"
    )


def test_m5_c3_recovery_and_release_acceptance_are_exact() -> None:
    p = _payload()
    recovery = p["upgrade_backup_restore_profile"]
    assert (
        recovery["backup_restore"]["committed_published_release_rpo_seconds"]
        == 0
    )
    assert recovery["backup_restore"]["restore_rto_seconds_max"] == 1800
    release = p["formal_release_acceptance_profile"]
    assert release["required_signoff_roles"] == [
        "RELEASE_MANAGER",
        "INDEPENDENT_QA",
        "SECURITY_APPROVER",
    ]
    assert release["signoff_actor_ids_must_be_distinct"] is True
    assert release["protected_main_m5_exit_go_required"] is True


def test_m5_c3_profile_hashes_reject_local_threshold_mutation() -> None:
    p = _payload()
    mutated = copy.deepcopy(p["performance_resource_profile"])
    mutated["service_thresholds"]["api_query_latency_p95_ms_max"] = 1000.001
    assert VALIDATOR._hash(mutated) != p["profile_hashes"]["performance_profile_sha256"]


@pytest.mark.parametrize(
    ("vector", "expected"),
    [
        ("security_critical_fail", "FAIL_CLOSED_M5_SECURITY_ACCEPTANCE"),
        ("package_network_dependency_fail", "FAIL_CLOSED_M5_OFFLINE_PACKAGE_REQUIRED"),
        ("backup_corruption_fail", "FAIL_CLOSED_M5_BACKUP_RESTORE_REQUIRED"),
        ("release_missing_profile_fail", "FAIL_CLOSED_M5_RELEASE_EVIDENCE_INCOMPLETE"),
        ("release_duplicate_signoff_actor_fail", "FAIL_CLOSED_M5_SIGNOFF_REQUIRED"),
        ("release_exit_not_go_fail", "FAIL_CLOSED_M5_EXIT_GO_REQUIRED"),
    ],
)
def test_m5_c3_negative_discriminators(vector: str, expected: str) -> None:
    p = _payload()
    assert p["golden_vectors"][vector]["expected_error"] == expected
