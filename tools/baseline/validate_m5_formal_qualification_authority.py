#!/usr/bin/env python3
"""Validate M5 formal qualification C3 authority exactly and fail closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT = (
    REPO_ROOT
    / "baseline"
    / "CB-1.4.0"
    / "canonical"
    / "M5_FORMAL_QUALIFICATION_AUTHORITY.json"
)
EXPECTED_AUTHORITY_SHA256 = "e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1"
EXPECTED_PROFILE_HASHES = {
    "target_hardware_profile_sha256": "236e1e1d5c74ce68717f6808346b997f58df6c6c5bccbd37323fe82fa8339d92",
    "workload_profile_sha256": "1cb0b2d6b241262f2af6c7dd05abe300da724b4508a98c57c184a0cfcb70970f",
    "performance_profile_sha256": "4de0aa56f961994b2063e503e0f3128d37a8e743980f33dea900fab6af53ab1e",
    "security_profile_sha256": "ea999324ebc576c26fc905cf117f086eecc1389e9e3588cb303a4b3d3dd4c7b2",
    "package_profile_sha256": "698f918307cd68ae16be2224a3b82853c805d98744343722b3d23a02fee0bc2b",
    "recovery_profile_sha256": "c35c59fd29491c98e09c4ff3001adcd102003d8d735ba9727f35065900348350",
    "release_acceptance_profile_sha256": "5bbeb9e02d8426ad8983c027123c4f9f8ff364beeb38af1efb4998a75b566a3f"
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != EXPECTED_AUTHORITY_SHA256:
        raise ValueError(
            f"authority hash mismatch expected={EXPECTED_AUTHORITY_SHA256} actual={actual}"
        )
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("authority root must be object")
    return payload


def verify(path: Path = DEFAULT) -> dict[str, object]:
    p = _load(path)
    checks: dict[str, bool] = {
        "identity": p.get("authority_id") == "M5_FORMAL_QUALIFICATION_AUTHORITY",
        "version": p.get("version") == "1.0.0",
        "schema": p.get("db_schema_version") == "1.6.0",
        "core": p.get("core_baseline") == "CB-1.4.0",
        "milestone": p.get("effective_milestone") == "M5",
        "p1_only": p["scope"]["admitted_capability_phase"] == ["P1"]
        and p["scope"]["excluded_capability_phases"] == ["P2", "P3", "P4", "P5", "P6"],
        "profiles_exact": p["scope"]["mandatory_certification_profiles"]
        == [
            "WINDOWS_DESKTOP_X64",
            "LINUX_DESKTOP_X64",
            "WINDOWS_SERVICE_X64",
            "LINUX_SERVICE_X64",
        ],
        "no_schema_change": p["scope"]["db_schema_change"] is False
        and p["scope"]["shadow_schema_permitted"] is False,
        "hardware_min": p["target_hardware_profile"]["logical_cpu_min"] == 4
        and p["target_hardware_profile"]["memory_gib_min"] == 8
        and p["target_hardware_profile"]["free_storage_gib_min"] == 20,
        "workload_exact": p["workload_profile"]["session_count"] == 50
        and p["workload_profile"]["p1_metric_catalog_count"] == 116
        and p["workload_profile"]["longitudinal_eligible_metric_count"] == 104
        and p["workload_profile"]["total_observation_target"] == 5800,
        "performance_exact": p["performance_resource_profile"]["common_thresholds"]
        == {
            "full_workload_wall_seconds_max": 900.0,
            "replay_session_throughput_per_second_min": 0.1,
            "peak_rss_mib_max": 8192,
            "normalized_cpu_utilization_p95_pct_max": 95.0,
            "workspace_disk_growth_mib_max": 10240,
            "request_error_count_max": 0,
        },
        "security_exact": p["security_release_readiness_profile"]["vulnerability_acceptance"]["critical_unwaived_count_max"] == 0
        and p["security_release_readiness_profile"]["vulnerability_acceptance"]["high_unwaived_count_max"] == 0
        and p["security_release_readiness_profile"]["vulnerability_acceptance"]["medium_unwaived_count_max"] == 0
        and p["security_release_readiness_profile"]["vulnerability_acceptance"]["waiver_allowed_severities"] == ["MEDIUM"],
        "offline_package": all(
            value is False
            for value in p["package_lifecycle_profile"]["target_prerequisites"].values()
        ),
        "backup_rpo_zero": p["upgrade_backup_restore_profile"]["backup_restore"]["committed_published_release_rpo_seconds"] == 0,
        "restore_rto": p["upgrade_backup_restore_profile"]["backup_restore"]["restore_rto_seconds_max"] == 1800,
        "signoffs": p["formal_release_acceptance_profile"]["required_signoff_roles"]
        == ["RELEASE_MANAGER", "INDEPENDENT_QA", "SECURITY_APPROVER"]
        and p["formal_release_acceptance_profile"]["signoff_actor_ids_must_be_distinct"] is True,
        "m5_exit_required": p["formal_release_acceptance_profile"]["protected_main_m5_exit_go_required"] is True,
    }
    profile_map = {
        "target_hardware_profile_sha256": p["target_hardware_profile"],
        "workload_profile_sha256": p["workload_profile"],
        "performance_profile_sha256": p["performance_resource_profile"],
        "security_profile_sha256": p["security_release_readiness_profile"],
        "package_profile_sha256": p["package_lifecycle_profile"],
        "recovery_profile_sha256": p["upgrade_backup_restore_profile"],
        "release_acceptance_profile_sha256": p["formal_release_acceptance_profile"],
    }
    for name, value in profile_map.items():
        checks[f"hash:{name}"] = (
            p["profile_hashes"][name] == _hash(value)
            and p["profile_hashes"][name] == EXPECTED_PROFILE_HASHES[name]
        )
    golden = p["golden_vectors"]
    checks.update(
        {
            "golden_perf_boundary": golden["performance_boundary_pass"]["api_query_latency_p95_ms"]
            == p["performance_resource_profile"]["service_thresholds"]["api_query_latency_p95_ms_max"],
            "golden_perf_fail": golden["performance_over_limit_fail"]["expected_error"]
            == "FAIL_CLOSED_M5_PERFORMANCE_THRESHOLD",
            "golden_security_fail": golden["security_critical_fail"]["expected_error"]
            == "FAIL_CLOSED_M5_SECURITY_ACCEPTANCE",
            "golden_offline_fail": golden["package_network_dependency_fail"]["expected_error"]
            == "FAIL_CLOSED_M5_OFFLINE_PACKAGE_REQUIRED",
            "golden_restore_fail": golden["backup_corruption_fail"]["expected_error"]
            == "FAIL_CLOSED_M5_BACKUP_RESTORE_REQUIRED",
            "golden_exit_fail": golden["release_exit_not_go_fail"]["expected_error"]
            == "FAIL_CLOSED_M5_EXIT_GO_REQUIRED",
        }
    )
    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema": "TPAA_M5_C3_FORMAL_QUALIFICATION_AUTHORITY_EVIDENCE_V1",
        "tracking_issue": 136,
        "status": "PASS" if not failed else "FAIL",
        "authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "profile_hashes": p["profile_hashes"],
        "checks": checks,
        "failed_checks": failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, default=DEFAULT)
    args = parser.parse_args()
    try:
        result = verify(args.authority)
    except Exception as exc:
        result = {
            "schema": "TPAA_M5_C3_FORMAL_QUALIFICATION_AUTHORITY_EVIDENCE_V1",
            "tracking_issue": 136,
            "status": "FAIL",
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
