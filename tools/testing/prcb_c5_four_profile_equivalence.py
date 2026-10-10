#!/usr/bin/env python3
"""PRCB C5 four-profile installed-chain logical-equivalence review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

MANDATORY_PROFILES = (
    "LINUX_DESKTOP_X64",
    "LINUX_SERVICE_X64",
    "WINDOWS_DESKTOP_X64",
    "WINDOWS_SERVICE_X64",
)


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root JSON object required")
    return cast(dict[str, Any], value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hex64(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _installed(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("installed_runtime")
    if not isinstance(value, dict):
        raise RuntimeError("installed_runtime evidence missing")
    return cast(dict[str, Any], value)


def _profile(
    path: Path,
    *,
    expected_profile: str,
    expected_revision: str,
) -> dict[str, Any]:
    report = _json(path)
    installed = _installed(report)
    if report.get("status") != "PASS":
        raise RuntimeError(f"{expected_profile}: installed qualification is not PASS")
    if report.get("profile_id") != expected_profile:
        raise RuntimeError(f"{expected_profile}: profile identity mismatch")
    if report.get("source_revision") != expected_revision:
        raise RuntimeError(f"{expected_profile}: source revision mismatch")
    if report.get("product_version") != "1.0.1":
        raise RuntimeError(f"{expected_profile}: product version mismatch")
    if report.get("formal_release_claimed") is not False:
        raise RuntimeError(f"{expected_profile}: premature formal release claim")
    if report.get("tests_packaged") is not False:
        raise RuntimeError(f"{expected_profile}: tests packaged")
    if report.get("fixtures_packaged") is not False:
        raise RuntimeError(f"{expected_profile}: fixtures packaged")
    if not _hex64(report.get("package_sha256")):
        raise RuntimeError(f"{expected_profile}: package SHA256 invalid")
    if installed.get("status") != "PASS":
        raise RuntimeError(f"{expected_profile}: installed runtime is not PASS")
    if installed.get("product_version") != "1.0.1":
        raise RuntimeError(f"{expected_profile}: installed product version mismatch")
    if installed.get("db_schema_version") != "1.9.0":
        raise RuntimeError(f"{expected_profile}: DB schema drift")
    if installed.get("canonical_baseline") != "CB-1.4.0":
        raise RuntimeError(f"{expected_profile}: canonical baseline drift")
    if installed.get("restart_exact_replay") is not True:
        raise RuntimeError(f"{expected_profile}: restart exact replay missing")
    if installed.get("backup_restore_exact_replay") is not True:
        raise RuntimeError(f"{expected_profile}: backup/restore exact replay missing")
    if installed.get("api_exact_read_verified") is not True:
        raise RuntimeError(f"{expected_profile}: exact API read missing")
    if installed.get("persistent_audit_verified") is not True:
        raise RuntimeError(f"{expected_profile}: persistent audit missing")
    if installed.get("tests_fixture_dependency") is not False:
        raise RuntimeError(f"{expected_profile}: runtime fixture dependency")
    if installed.get("formal_release_claimed") is not False:
        raise RuntimeError(f"{expected_profile}: installed formal release claim")
    return report


def _ed2_b3(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("ed2_b3_upper_runtime")
    if not isinstance(value, dict):
        raise RuntimeError("ED2 B3 installed upper evidence missing")
    payload = cast(dict[str, Any], value)
    if (
        payload.get("schema") != "TPAA_ED2_B3_UPPER_QUALIFICATION_RESULT_V1"
        or payload.get("status") != "PASS"
        or payload.get("snapshot_count") != 8
        or payload.get("restart_exact_replay") is not True
        or payload.get("backup_restore_exact_replay") is not True
        or payload.get("api_exact_read_verified") is not True
        or payload.get("api_latest_alias_rejected") is not True
        or payload.get("privacy_boundaries_verified") is not True
        or payload.get("training_plugin_contracts_verified") is not True
        or payload.get("joint_lvc_boundary_verified") is not True
        or payload.get("mutable_latest_fallback_used") is not False
        or payload.get("formal_release_claimed") is not False
    ):
        raise RuntimeError("ED2 B3 installed upper evidence invalid")
    return payload


def _ed2_b3_projection(report: dict[str, Any]) -> dict[str, object]:
    payload = _ed2_b3(report)
    snapshots = payload.get("snapshot_ids")
    layers = payload.get("semantic_layers")
    if not isinstance(snapshots, dict) or len(snapshots) != 8:
        raise RuntimeError("ED2 B3 snapshot identity set invalid")
    if not all(
        isinstance(key, str)
        and isinstance(value, str)
        and bool(value)
        for key, value in snapshots.items()
    ):
        raise RuntimeError("ED2 B3 snapshot identity invalid")
    if layers != ["W", "P", "A", "J", "M"]:
        raise RuntimeError("ED2 B3 semantic layer set drift")
    return {
        "snapshot_ids": dict(sorted(snapshots.items())),
        "source_release_ids": payload.get("source_release_ids"),
        "event_availability": payload.get("event_availability"),
        "objective_availability": payload.get("objective_availability"),
        "semantic_layers": layers,
        "media_uri": payload.get("media_uri"),
        "transcript_uri": payload.get("transcript_uri"),
    }


def _p2_semantics(report: dict[str, Any]) -> dict[str, object]:
    installed = _installed(report)
    reasons = installed.get("p2_reason_codes")
    if not isinstance(reasons, list) or not all(
        isinstance(item, str) for item in reasons
    ):
        raise RuntimeError("P2 reason-code evidence invalid")
    result = {
        "p2_release_id": installed.get("p2_release_id"),
        "source_observation_id": installed.get("p2_source_observation_id"),
        "status": installed.get("p2_estimate_status"),
        "reason_codes": reasons,
        "claim_level": installed.get("p2_claim_level"),
        "adjusted_value": installed.get("p2_adjusted_value"),
        "unit": installed.get("p2_unit"),
        "job_status": installed.get("p2_job_status"),
    }
    for field in (
        "p2_release_id",
        "source_observation_id",
        "status",
        "claim_level",
        "unit",
        "job_status",
    ):
        if not isinstance(result[field], str) or not cast(str, result[field]):
            raise RuntimeError(f"P2 semantic field invalid: {field}")
    return result


def _shared_exact_projection(report: dict[str, Any]) -> dict[str, object]:
    installed = _installed(report)
    identity_fields = (
        "release_id",
        "p3_estimate_id",
        "p4_revision_id",
        "p5_revision_id",
        "p6_forecast_result_id",
        "p6_counterfactual_run_id",
    )
    count_fields = (
        "metric_count",
        "catalog_definition_count",
        "metric_code_count",
        "capability_observation_count",
        "system_observation_count",
        "evidence_only_metric_instance_count",
        "world_product_count",
        "stage_count",
        "world_relation_count",
    )
    result = {
        field: installed.get(field)
        for field in (*identity_fields, *count_fields)
    }
    if not all(
        isinstance(result[field], str) and bool(cast(str, result[field]))
        for field in identity_fields
    ):
        raise RuntimeError("shared exact product identity evidence invalid")
    if not all(
        isinstance(result[field], int)
        and not isinstance(result[field], bool)
        and cast(int, result[field]) > 0
        for field in count_fields
    ):
        raise RuntimeError("shared exact P1 membership evidence invalid")
    if (
        result["catalog_definition_count"] != 116
        or result["metric_code_count"] != 116
        or result["world_product_count"] != 4
        or result["stage_count"] != 4
        or result["world_relation_count"] != 3
    ):
        raise RuntimeError(
            "shared exact P1 Catalog/World/Stage membership drift"
        )
    return result


def _desktop_acceptance(report: dict[str, Any]) -> bool:
    installed = _installed(report)
    return all(
        installed.get(field) is True
        for field in (
            "desktop_discovery_verified",
            "desktop_authentication_verified",
            "desktop_latest_alias_rejected",
            "api_exact_read_restart_replay",
            "desktop_discovery_restart_replay",
            "api_exact_read_backup_restore_replay",
            "desktop_discovery_backup_restore_replay",
        )
    )


def _service_acceptance(report: dict[str, Any]) -> bool:
    installed = _installed(report)
    return (
        report.get("real_postgresql_executed") is True
        and report.get("pg_dump_restore_executed") is True
        and isinstance(report.get("postgres_server_version"), str)
        and bool(cast(str, report.get("postgres_server_version")))
        and installed.get("service_authentication_verified") is True
        and installed.get("service_rbac_verified") is True
        and installed.get("service_latest_alias_rejected") is True
        and installed.get("api_exact_read_restart_replay") is True
        and installed.get("api_exact_read_backup_restore_replay") is True
        and installed.get("security_audit_verified") is True
        and installed.get("model_reviewer_service_role_configured") is False
    )


def review(
    *,
    linux_desktop: Path,
    windows_desktop: Path,
    linux_service: Path,
    windows_service: Path,
    expected_revision: str,
) -> dict[str, object]:
    by_profile = {
        "LINUX_DESKTOP_X64": _profile(
            linux_desktop,
            expected_profile="LINUX_DESKTOP_X64",
            expected_revision=expected_revision,
        ),
        "WINDOWS_DESKTOP_X64": _profile(
            windows_desktop,
            expected_profile="WINDOWS_DESKTOP_X64",
            expected_revision=expected_revision,
        ),
        "LINUX_SERVICE_X64": _profile(
            linux_service,
            expected_profile="LINUX_SERVICE_X64",
            expected_revision=expected_revision,
        ),
        "WINDOWS_SERVICE_X64": _profile(
            windows_service,
            expected_profile="WINDOWS_SERVICE_X64",
            expected_revision=expected_revision,
        ),
    }
    evidence_sha256 = {
        "LINUX_DESKTOP_X64": _sha256_file(linux_desktop),
        "WINDOWS_DESKTOP_X64": _sha256_file(windows_desktop),
        "LINUX_SERVICE_X64": _sha256_file(linux_service),
        "WINDOWS_SERVICE_X64": _sha256_file(windows_service),
    }
    desktop_semantics = {
        key: _p2_semantics(by_profile[key])
        for key in ("LINUX_DESKTOP_X64", "WINDOWS_DESKTOP_X64")
    }
    service_semantics = {
        key: _p2_semantics(by_profile[key])
        for key in ("LINUX_SERVICE_X64", "WINDOWS_SERVICE_X64")
    }
    shared_exact = {
        profile: _shared_exact_projection(report)
        for profile, report in by_profile.items()
    }
    ed2_b3_exact = {
        profile: _ed2_b3_projection(report)
        for profile, report in by_profile.items()
    }
    package_hashes = {
        profile: str(report["package_sha256"])
        for profile, report in by_profile.items()
    }
    p2_provenance = {
        profile: {
            "estimate_id": _installed(report).get("p2_estimate_id"),
            "knowledge_time_utc": _installed(report).get(
                "p2_source_knowledge_time_utc"
            ),
        }
        for profile, report in by_profile.items()
    }
    acceptance = {
        "exact_four_profiles": (
            len(by_profile) == len(MANDATORY_PROFILES)
            and set(by_profile) == set(MANDATORY_PROFILES)
        ),
        "same_candidate_source_revision": all(
            report.get("source_revision") == expected_revision
            for report in by_profile.values()
        ),
        "immutable_package_sha256_all_profiles": (
            len(set(package_hashes.values())) == 4
            and all(_hex64(value) for value in package_hashes.values())
        ),
        "desktop_windows_linux_p2_semantic_equivalence": (
            desktop_semantics["LINUX_DESKTOP_X64"]
            == desktop_semantics["WINDOWS_DESKTOP_X64"]
        ),
        "service_windows_linux_p2_semantic_equivalence": (
            service_semantics["LINUX_SERVICE_X64"]
            == service_semantics["WINDOWS_SERVICE_X64"]
        ),
        "shared_p1_p3_p6_exact_identity_all_profiles": (
            len(
                {
                    json.dumps(value, sort_keys=True, separators=(",", ":"))
                    for value in shared_exact.values()
                }
            )
            == 1
        ),
        "ed2_b3_upper_exact_identity_all_profiles": (
            len(
                {
                    json.dumps(value, sort_keys=True, separators=(",", ":"))
                    for value in ed2_b3_exact.values()
                }
            )
            == 1
        ),
        "ed2_b3_restart_backup_api_all_profiles": all(
            _ed2_b3(report).get("restart_exact_replay") is True
            and _ed2_b3(report).get("backup_restore_exact_replay") is True
            and _ed2_b3(report).get("api_exact_read_verified") is True
            for report in by_profile.values()
        ),
        "desktop_installed_discovery_auth_replay_all_os": all(
            _desktop_acceptance(by_profile[profile])
            for profile in ("LINUX_DESKTOP_X64", "WINDOWS_DESKTOP_X64")
        ),
        "service_real_postgres_rbac_recovery_all_os": all(
            _service_acceptance(by_profile[profile])
            for profile in ("LINUX_SERVICE_X64", "WINDOWS_SERVICE_X64")
        ),
        "restart_backup_restore_exact_all_profiles": all(
            _installed(report).get("restart_exact_replay") is True
            and _installed(report).get("backup_restore_exact_replay") is True
            for report in by_profile.values()
        ),
        "formal_release_not_claimed": all(
            report.get("formal_release_claimed") is False
            and _installed(report).get("formal_release_claimed") is False
            for report in by_profile.values()
        ),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    return {
        "schema": "TPAA_PRCB_C5_FOUR_PROFILE_LOGICAL_EQUIVALENCE_V1",
        "status": "PASS" if not failed else "FAIL",
        "qualification": "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED",
        "formal_release_claimed": False,
        "source_revision": expected_revision,
        "mandatory_profiles": list(MANDATORY_PROFILES),
        "package_sha256_by_profile": package_hashes,
        "installed_evidence_sha256_by_profile": evidence_sha256,
        "postgres_server_version_by_service_profile": {
            profile: by_profile[profile].get("postgres_server_version")
            for profile in ("LINUX_SERVICE_X64", "WINDOWS_SERVICE_X64")
        },
        "p2_semantics_by_profile_family": {
            "desktop": desktop_semantics,
            "service": service_semantics,
        },
        "p2_runtime_provenance_by_profile": p2_provenance,
        "p2_identity_interpretation": (
            "P2 exact identity is verified within each installed profile across "
            "restart and restore; cross-OS equivalence compares governed business "
            "semantics while retaining explicit runtime knowledge-time provenance."
        ),
        "shared_exact_projection_by_profile": shared_exact,
        "ed2_b3_upper_projection_by_profile": ed2_b3_exact,
        "acceptance": acceptance,
        "failed_acceptance": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--linux-desktop", type=Path, required=True)
    parser.add_argument("--windows-desktop", type=Path, required=True)
    parser.add_argument("--linux-service", type=Path, required=True)
    parser.add_argument("--windows-service", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            linux_desktop=args.linux_desktop,
            windows_desktop=args.windows_desktop,
            linux_service=args.linux_service,
            windows_service=args.windows_service,
            expected_revision=args.expected_revision,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_PRCB_C5_FOUR_PROFILE_LOGICAL_EQUIVALENCE_V1",
            "status": "FAIL",
            "qualification": "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED",
            "formal_release_claimed": False,
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
