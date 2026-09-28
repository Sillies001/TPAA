from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_canonical import (
    EXPECTED_BASELINE_LOCK_SHA256,
    CanonicalArtifactLoader,
)
from tpaa_qualification import (
    M5QualificationError,
    build_result_binding,
    load_m5_qualification_authority,
    performance_thresholds_for_profile,
    validate_m5_formal_claim_prerequisites,
    validate_result_binding,
    validate_target_hardware,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_PATH = BASELINE / "canonical" / "M5_FORMAL_QUALIFICATION_AUTHORITY.json"


def _raw_authority() -> dict[str, object]:
    payload = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _identity(profile_id: str) -> dict[str, object]:
    authority = load_m5_qualification_authority(BASELINE)
    target = authority.target_hardware_profile
    profile = authority.certification_profile(profile_id)
    return {
        "certification_profile_id": profile_id,
        "os_family": profile.os_family,
        "os_release": "TEST",
        "os_build_or_kernel": "TEST",
        "machine_architecture": target["architecture"],
        "cpu_model": "TEST",
        "logical_cpu_count": target["logical_cpu_min"],
        "memory_gib": target["memory_gib_min"],
        "persistent_storage_class": target["persistent_storage_class"][0],
        "free_storage_gib": target["free_storage_gib_min"],
        "python_runtime_version": "3.13.5",
        "source_revision": "a" * 40,
        "semantic_build_version": "M5-BATCH-1-TEST",
    }


def test_m5_batch_1_projects_exact_authority_and_four_profiles() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    assert authority.version == "1.0.0"
    assert authority.db_schema_version == "1.6.0"
    assert authority.mandatory_profile_ids == (
        "WINDOWS_DESKTOP_X64",
        "LINUX_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
        "LINUX_SERVICE_X64",
    )
    assert authority.admitted_phases == ("P1",)
    assert authority.excluded_phases == ("P2", "P3", "P4", "P5", "P6")
    assert all(profile.required_components for profile in authority.mandatory_profiles)


def test_m5_batch_1_performance_projection_uses_canonical_thresholds() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    raw = _raw_authority()
    performance = raw["performance_resource_profile"]
    assert isinstance(performance, dict)

    for profile in authority.mandatory_profiles:
        projected = dict(
            performance_thresholds_for_profile(authority, profile.profile_id)
        )
        expected = dict(performance["common_thresholds"])
        role_key = (
            "desktop_thresholds" if profile.role == "DESKTOP" else "service_thresholds"
        )
        expected.update(performance[role_key])
        assert projected == expected


def test_m5_batch_1_hardware_boundary_and_below_minimum() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    profile_id = authority.mandatory_profile_ids[0]
    identity = _identity(profile_id)
    validate_target_hardware(authority, identity)

    identity["logical_cpu_count"] = (
        int(authority.target_hardware_profile["logical_cpu_min"]) - 1
    )
    with pytest.raises(M5QualificationError) as exc:
        validate_target_hardware(authority, identity)
    assert exc.value.code == authority.error_code("hardware_below_minimum")


def test_m5_batch_1_result_binding_rejects_stale_workload() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    profile_id = authority.mandatory_profile_ids[0]
    binding = build_result_binding(
        authority,
        source_revision="a" * 40,
        semantic_build_version="M5-BATCH-1-TEST",
        certification_profile_id=profile_id,
        generated_workload_manifest_sha256="b" * 64,
        dependency_lock_sha256="c" * 64,
        hardware_manifest_sha256="d" * 64,
    )
    validate_result_binding(authority, binding)
    assert binding.workload_id == authority.workload_profile["workload_id"]
    assert binding.workload_spec_hash == authority.performance_resource_profile[
        "workload_spec_hash"
    ]
    assert binding.baseline_lock_sha256 == authority.baseline_lock_sha256

    stale = replace(binding, workload_id="STALE")
    with pytest.raises(M5QualificationError) as exc:
        validate_result_binding(authority, stale)
    assert exc.value.code == authority.error_code("workload_mismatch")


def test_m5_batch_1_claim_guard_is_p1_exact_exit_only() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    revision = "a" * 40

    with pytest.raises(M5QualificationError) as p2_exc:
        validate_m5_formal_claim_prerequisites(
            authority,
            capability_phase=authority.excluded_phases[0],
            m5_exit_decision="GO",
            exact_evidence_manifest_accepted=True,
            candidate_source_revision=revision,
            exit_source_revision=revision,
        )
    assert p2_exc.value.code == authority.error_code("release_evidence_incomplete")

    with pytest.raises(M5QualificationError) as exit_exc:
        validate_m5_formal_claim_prerequisites(
            authority,
            capability_phase="P1",
            m5_exit_decision="NOT_GO",
            exact_evidence_manifest_accepted=True,
            candidate_source_revision=revision,
            exit_source_revision=revision,
        )
    assert exit_exc.value.code == authority.error_code("m5_exit_not_go")

    with pytest.raises(M5QualificationError) as evidence_exc:
        validate_m5_formal_claim_prerequisites(
            authority,
            capability_phase="P1",
            m5_exit_decision="GO",
            exact_evidence_manifest_accepted=False,
            candidate_source_revision=revision,
            exit_source_revision=revision,
        )
    assert evidence_exc.value.code == authority.error_code(
        "release_evidence_incomplete"
    )

    validate_m5_formal_claim_prerequisites(
        authority,
        capability_phase="P1",
        m5_exit_decision="GO",
        exact_evidence_manifest_accepted=True,
        candidate_source_revision=revision,
        exit_source_revision=revision,
    )


def test_m5_batch_1_missing_authority_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(M5QualificationError) as exc:
        load_m5_qualification_authority(tmp_path / "missing")
    assert exc.value.code == "FAIL_CLOSED_M5_QUALIFICATION_AUTHORITY_REQUIRED"


def test_m5_batch_1_mismatched_authority_bytes_fail_closed(tmp_path: Path) -> None:
    copied = tmp_path / "CB-1.4.0"
    shutil.copytree(BASELINE, copied)
    authority_path = copied / "canonical" / "M5_FORMAL_QUALIFICATION_AUTHORITY.json"
    authority_path.write_bytes(authority_path.read_bytes() + b"\n")

    loader = CanonicalArtifactLoader(
        copied,
        trusted_lock_sha256=EXPECTED_BASELINE_LOCK_SHA256,
    )
    with pytest.raises(M5QualificationError) as exc:
        load_m5_qualification_authority(loader=loader)
    assert exc.value.code == "FAIL_CLOSED_M5_AUTHORITY_HASH_MISMATCH"


def test_m5_batch_1_stale_authority_version_fails_closed(tmp_path: Path) -> None:
    copied = tmp_path / "CB-1.4.0"
    shutil.copytree(BASELINE, copied)

    authority_path = copied / "canonical" / "M5_FORMAL_QUALIFICATION_AUTHORITY.json"
    payload = json.loads(authority_path.read_text(encoding="utf-8"))
    payload["version"] = "0.9.0"
    rendered = (
        json.dumps(payload, indent=2, ensure_ascii=False, separators=(",", ": "))
        + "\n"
    )
    authority_path.write_text(rendered, encoding="utf-8", newline="\n")
    authority_bytes = authority_path.read_bytes()

    lock_path = copied / "BASELINE_LOCK.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    entry = next(
        item
        for item in lock["artifacts"]
        if item["file"] == "M5_FORMAL_QUALIFICATION_AUTHORITY.json"
    )
    entry["sha256"] = hashlib.sha256(authority_bytes).hexdigest()
    entry["bytes"] = len(authority_bytes)
    lock_rendered = (
        json.dumps(lock, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"
    )
    lock_path.write_text(lock_rendered, encoding="utf-8", newline="\n")
    trusted_lock = hashlib.sha256(lock_path.read_bytes()).hexdigest()

    loader = CanonicalArtifactLoader(
        copied,
        trusted_lock_sha256=trusted_lock,
    )
    with pytest.raises(M5QualificationError) as exc:
        load_m5_qualification_authority(loader=loader)
    assert exc.value.code == "FAIL_CLOSED_M5_AUTHORITY_HASH_MISMATCH"
