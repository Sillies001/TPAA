#!/usr/bin/env python3
"""M5 Batch 1 executable evidence for qualification authority/profile substrate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(REPO_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from tpaa_qualification import (  # noqa: E402
    M5QualificationAuthority,
    M5QualificationError,
    build_result_binding,
    load_m5_qualification_authority,
    performance_thresholds_for_profile,
    security_profile_for_profile,
    validate_m5_formal_claim_prerequisites,
    validate_result_binding,
    validate_target_hardware,
)

BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
TRACKING_ISSUE = 139
TASK_IDS = (
    "M5-GOV-001",
    "M5-GOV-002",
    "M5-PLAT-001",
    "M5-PERF-001",
    "M5-SEC-001",
    "M5-TST-001",
)


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _canonical_hash(value: object) -> str:
    rendered = json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _error_code(action: Callable[[], object]) -> str:
    try:
        action()
    except M5QualificationError as exc:
        return exc.code
    return "NO_ERROR"


def _identity(
    authority: M5QualificationAuthority,
    profile_id: str,
) -> dict[str, object]:
    target = authority.target_hardware_profile
    return {
        "certification_profile_id": profile_id,
        "os_family": authority.certification_profile(profile_id).os_family,
        "os_release": "BATCH_1_SYNTHETIC",
        "os_build_or_kernel": "BATCH_1_SYNTHETIC",
        "machine_architecture": target["architecture"],
        "cpu_model": "BATCH_1_SYNTHETIC",
        "logical_cpu_count": target["logical_cpu_min"],
        "memory_gib": target["memory_gib_min"],
        "persistent_storage_class": target["persistent_storage_class"][0],
        "free_storage_gib": target["free_storage_gib_min"],
        "python_runtime_version": "3.13.5",
        "source_revision": _git_revision(),
        "semantic_build_version": "M5-BATCH-1-SUBSTRATE",
    }


def verify(platform: str) -> dict[str, object]:
    authority = load_m5_qualification_authority(BASELINE)
    source_revision = _git_revision()
    dependency_lock_sha256 = _sha256_file(REPO_ROOT / "uv.lock")

    expected_os_family = {"windows": "WINDOWS", "linux": "LINUX"}[platform]
    platform_profiles = tuple(
        profile.profile_id
        for profile in authority.mandatory_profiles
        if profile.os_family == expected_os_family
    )

    identities: dict[str, dict[str, object]] = {}
    bindings: dict[str, dict[str, str]] = {}
    threshold_projections: dict[str, dict[str, int | float]] = {}
    security_hashes: dict[str, str] = {}
    for profile in authority.mandatory_profiles:
        identity = _identity(authority, profile.profile_id)
        validate_target_hardware(authority, identity)
        identities[profile.profile_id] = identity
        hardware_manifest_sha256 = _canonical_hash(identity)
        binding = build_result_binding(
            authority,
            source_revision=source_revision,
            semantic_build_version="M5-BATCH-1-SUBSTRATE",
            certification_profile_id=profile.profile_id,
            generated_workload_manifest_sha256=authority.profile_hashes[
                "workload_profile_sha256"
            ],
            dependency_lock_sha256=dependency_lock_sha256,
            hardware_manifest_sha256=hardware_manifest_sha256,
        )
        bindings[profile.profile_id] = binding.projection()
        threshold_projections[profile.profile_id] = dict(
            performance_thresholds_for_profile(authority, profile.profile_id)
        )
        security_hashes[profile.profile_id] = _canonical_hash(
            dict(security_profile_for_profile(authority, profile.profile_id))
        )

    first_profile = authority.mandatory_profiles[0]
    below_minimum = dict(identities[first_profile.profile_id])
    below_minimum["logical_cpu_count"] = (
        int(authority.target_hardware_profile["logical_cpu_min"]) - 1
    )
    below_minimum_error = _error_code(
        lambda: validate_target_hardware(authority, below_minimum)
    )
    unsupported_profile_error = _error_code(
        lambda: authority.certification_profile("UNAPPROVED_FIFTH_PROFILE")
    )

    binding = build_result_binding(
        authority,
        source_revision=source_revision,
        semantic_build_version="M5-BATCH-1-SUBSTRATE",
        certification_profile_id=first_profile.profile_id,
        generated_workload_manifest_sha256=authority.profile_hashes[
            "workload_profile_sha256"
        ],
        dependency_lock_sha256=dependency_lock_sha256,
        hardware_manifest_sha256=_canonical_hash(identities[first_profile.profile_id]),
    )
    stale_binding = replace(binding, workload_id="STALE_WORKLOAD")
    stale_binding_error = _error_code(
        lambda: validate_result_binding(authority, stale_binding)
    )

    excluded_phase = authority.excluded_phases[0]
    p2_p6_error = _error_code(
        lambda: validate_m5_formal_claim_prerequisites(
            authority,
            capability_phase=excluded_phase,
            m5_exit_decision="GO",
            exact_evidence_manifest_accepted=True,
            candidate_source_revision=source_revision,
            exit_source_revision=source_revision,
        )
    )
    pre_exit_error = _error_code(
        lambda: validate_m5_formal_claim_prerequisites(
            authority,
            capability_phase=authority.admitted_phases[0],
            m5_exit_decision="NOT_GO",
            exact_evidence_manifest_accepted=True,
            candidate_source_revision=source_revision,
            exit_source_revision=source_revision,
        )
    )
    missing_evidence_error = _error_code(
        lambda: validate_m5_formal_claim_prerequisites(
            authority,
            capability_phase=authority.admitted_phases[0],
            m5_exit_decision="GO",
            exact_evidence_manifest_accepted=False,
            candidate_source_revision=source_revision,
            exit_source_revision=source_revision,
        )
    )
    validate_m5_formal_claim_prerequisites(
        authority,
        capability_phase=authority.admitted_phases[0],
        m5_exit_decision="GO",
        exact_evidence_manifest_accepted=True,
        candidate_source_revision=source_revision,
        exit_source_revision=source_revision,
    )

    with tempfile.TemporaryDirectory(prefix="tpaa-m5-missing-authority-") as raw:
        missing_authority_error = _error_code(
            lambda: load_m5_qualification_authority(Path(raw) / "missing")
        )

    error_codes = authority.fail_closed_error_codes
    acceptance = {
        "authority_controlled_and_loadable": authority.version == "1.0.0",
        "authority_hash_bound": len(authority.authority_sha256) == 64,
        "baseline_lock_bound": len(authority.baseline_lock_sha256) == 64,
        "db_schema_unchanged": authority.db_schema_version == "1.6.0",
        "exact_four_profiles": len(authority.mandatory_profiles) == 4,
        "platform_has_exact_two_profiles": len(platform_profiles) == 2,
        "all_profile_components_projected": all(
            profile.required_components for profile in authority.mandatory_profiles
        ),
        "performance_thresholds_projected": all(
            threshold_projections[profile.profile_id]
            for profile in authority.mandatory_profiles
        ),
        "security_profile_bound_for_all_profiles": len(set(security_hashes.values())) == 1,
        "hardware_boundary_passes": len(identities) == 4,
        "hardware_below_minimum_fails_closed": (
            below_minimum_error == error_codes["hardware_below_minimum"]
        ),
        "unsupported_fifth_profile_fails_closed": (
            unsupported_profile_error == error_codes["unsupported_profile"]
        ),
        "stale_workload_binding_fails_closed": (
            stale_binding_error == error_codes["workload_mismatch"]
        ),
        "p2_p6_claim_fails_closed": (
            p2_p6_error == error_codes["release_evidence_incomplete"]
        ),
        "pre_exit_claim_fails_closed": (
            pre_exit_error == error_codes["m5_exit_not_go"]
        ),
        "missing_exact_evidence_fails_closed": (
            missing_evidence_error == error_codes["release_evidence_incomplete"]
        ),
        "missing_authority_fails_closed": (
            missing_authority_error
            == "FAIL_CLOSED_M5_QUALIFICATION_AUTHORITY_REQUIRED"
        ),
        "bindings_cover_exact_four_profiles": len(bindings) == 4,
        "bindings_use_exact_authority_workload": all(
            item["workload_id"] == authority.workload_profile["workload_id"]
            and item["workload_spec_hash"]
            == authority.performance_resource_profile["workload_spec_hash"]
            and item["baseline_lock_sha256"] == authority.baseline_lock_sha256
            for item in bindings.values()
        ),
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)

    logical_product = {
        "authority_sha256": authority.authority_sha256,
        "baseline_lock_sha256": authority.baseline_lock_sha256,
        "db_schema_version": authority.db_schema_version,
        "admitted_phases": list(authority.admitted_phases),
        "excluded_phases": list(authority.excluded_phases),
        "mandatory_profiles": [
            {
                "profile_id": profile.profile_id,
                "os_family": profile.os_family,
                "role": profile.role,
                "reference_environment": profile.reference_environment,
                "required_components": list(profile.required_components),
            }
            for profile in authority.mandatory_profiles
        ],
        "target_hardware_profile_hash": authority.profile_hashes[
            "target_hardware_profile_sha256"
        ],
        "workload_profile_hash": authority.profile_hashes["workload_profile_sha256"],
        "performance_profile_hash": authority.profile_hashes[
            "performance_profile_sha256"
        ],
        "security_profile_hash": authority.profile_hashes["security_profile_sha256"],
        "platform_profiles": list(platform_profiles),
        "threshold_projections": threshold_projections,
        "bindings": bindings,
    }
    return {
        "schema": "TPAA_M5_BATCH_1_QUALIFICATION_PROFILE_EVIDENCE_V1",
        "tracking_issue": TRACKING_ISSUE,
        "task_ids": list(TASK_IDS),
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": source_revision,
        "platform": platform,
        "logical_product": logical_product,
        "logical_product_hash": _canonical_hash(logical_product),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "formal_release_claimed": False,
            "db_schema_version": authority.db_schema_version,
            "shadow_schema_created": False,
            "package_execution_performed": False,
            "performance_execution_performed": False,
            "security_scanning_performed": False,
            "batch_2_work_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    try:
        payload = verify(args.platform)
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M5_BATCH_1_QUALIFICATION_PROFILE_EVIDENCE_V1",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": _git_revision(),
            "platform": args.platform,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2

    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
