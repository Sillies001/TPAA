from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tpaa_api import M5ServiceSecurityError, create_m5_service_app
from tpaa_application import (
    ApplicationService,
    GetRuntimeBaselineStatus,
    GetStorageBaselineStatus,
)
from tpaa_canonical.runtime_handshake import (
    RuntimeBaselineIdentity,
    evaluate_runtime_baseline_handshake,
)
from tpaa_qualification import (
    M5QualificationError,
    load_m5_qualification_authority,
    validate_four_profile_candidate,
    validate_package_qualification,
    validate_performance_measurements,
    validate_security_qualification,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
RUNTIME_ENTRY = ROOT / "tools" / "packaging" / "m5_runtime_entry.py"
REVISION = "a" * 40
BUILD = "0.0.0+m5.test"
H = "b" * 64


class _UnusedStorage:
    def execute(self) -> object:
        raise RuntimeError("not used")


def _identity() -> RuntimeBaselineIdentity:
    return RuntimeBaselineIdentity(
        product_build_version=BUILD,
        core_baseline="CB-1.4.0",
        baseline_lock_sha256=H,
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256=H,
        p1_metric_catalog_version="1.14.0",
        p1_metric_catalog_sha256=H,
        dto_authority_sha256=H,
    )


def _application() -> ApplicationService:
    expected = _identity()
    runtime = GetRuntimeBaselineStatus(
        lambda: evaluate_runtime_baseline_handshake(
            expected=expected,
            observed=expected,
        )
    )
    return ApplicationService(
        get_storage_baseline_status=cast(GetStorageBaselineStatus, _UnusedStorage()),
        get_runtime_baseline_status=runtime,
    )


def _performance(authority, profile_id: str) -> dict[str, object]:
    profile = authority.certification_profile(profile_id)
    common = authority.performance_resource_profile["common_thresholds"]
    role = authority.performance_resource_profile[
        "desktop_thresholds" if profile.role == "DESKTOP" else "service_thresholds"
    ]
    result: dict[str, object] = {}
    for key, value in (*common.items(), *role.items()):
        if key.endswith("_max"):
            result[key.removesuffix("_max")] = value
        elif key.endswith("_min"):
            result[key.removesuffix("_min")] = value
        else:
            result[key] = value
    return result


def _package(authority, profile_id: str) -> dict[str, object]:
    package = authority.package_lifecycle_profile
    required = package["required_package_evidence"]
    return {
        "profile_id": profile_id,
        "source_revision": REVISION,
        "semantic_build_version": BUILD,
        "package_form": package["package_forms"][profile_id],
        "package_sha256": H,
        "package_manifest_sha256": H,
        "target_prerequisites": dict(package["target_prerequisites"]),
        "evidence_hashes": {name: H for name in required},
        "lifecycle": {
            "clean_install_pass": True,
            "ready_start_pass": True,
            "component_smoke_pass": True,
            "graceful_stop_pass": True,
            "uninstall_pass": True,
            "no_residual_product_state": True,
        },
        "lifecycle_seconds": {
            "build": 1.0,
            "clean_install": 1.0,
            "ready_start": 1.0,
            "graceful_stop": 1.0,
            "uninstall": 1.0,
        },
    }


def _security(profile_id: str, *, service: bool) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "sbom_format": "CycloneDX JSON",
        "sbom_spec_version": "1.6",
        "dependency_authority": "uv.lock",
        "native_dependency_manifest_present": True,
        "severity_model": "CVSS_V3_1",
        "unscored_advisory_count": 0,
        "unknown_unreviewed_license_count": 0,
        "critical_unwaived_count": 0,
        "high_unwaived_count": 0,
        "medium_unwaived_count": 0,
        "advisory_snapshot_sha256": H,
        "high_confidence_secret_findings": 0,
        "default_credentials_present": False,
        "service_authentication_required": service,
        "service_default_deny_authorization": service,
        "desktop_remote_bind_without_authentication": False,
        "artifact_hashes": {"package": H, "manifest": H},
        "dependency_lock_sha256": H,
        "baseline_lock_sha256": H,
        "package_manifest_sha256": H,
        "waivers": [],
    }


def test_m5_batch_2_performance_boundary_and_over_limit() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    profile = "WINDOWS_SERVICE_X64"
    measurements = _performance(authority, profile)
    validate_performance_measurements(authority, profile, measurements)

    bad = dict(measurements)
    bad["api_query_latency_p95_ms"] = (
        float(measurements["api_query_latency_p95_ms"]) + 0.001
    )
    with pytest.raises(M5QualificationError) as exc:
        validate_performance_measurements(authority, profile, bad)
    assert exc.value.code == authority.error_code("performance_threshold")


def test_m5_batch_2_package_lifecycle_is_authority_driven() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    for profile_id in authority.mandatory_profile_ids:
        report = _package(authority, profile_id)
        validate_package_qualification(authority, profile_id, report)

        online = dict(report)
        prereq = dict(report["target_prerequisites"])
        prereq["network_access_required"] = True
        online["target_prerequisites"] = prereq
        with pytest.raises(M5QualificationError) as exc:
            validate_package_qualification(authority, profile_id, online)
        assert exc.value.code == authority.error_code("package_online_dependency")


def test_m5_batch_2_security_is_fail_closed() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    for profile_id in authority.mandatory_profile_ids:
        profile = authority.certification_profile(profile_id)
        report = _security(profile_id, service=profile.role == "SERVICE")
        validate_security_qualification(
            authority,
            profile_id,
            report,
            evaluated_at_utc="2026-09-28T00:00:00Z",
        )

        bad = dict(report)
        bad["critical_unwaived_count"] = 1
        with pytest.raises(M5QualificationError) as exc:
            validate_security_qualification(
                authority,
                profile_id,
                bad,
                evaluated_at_utc="2026-09-28T00:00:00Z",
            )
        assert exc.value.code == authority.error_code("security_acceptance")


def test_m5_service_wrapper_has_no_default_credential_and_default_denies() -> None:
    with pytest.raises(M5ServiceSecurityError):
        create_m5_service_app(_application(), bearer_token="")

    token = "m5-test-token-0123456789abcdef"
    with TestClient(create_m5_service_app(_application(), bearer_token=token)) as client:
        missing = client.get("/health")
        wrong = client.get(
            "/health",
            headers={"Authorization": "Bearer wrong-token-0123456789abcdef"},
        )
        allowed = client.get(
            "/health",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert missing.status_code == 401
    assert wrong.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json() == {"status": "UP"}


def test_m5_batch_2_exact_four_profile_same_candidate_guard() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    reports = [
        {
            "profile_id": profile_id,
            "source_revision": REVISION,
            "semantic_build_version": BUILD,
            "status": "PASS",
        }
        for profile_id in authority.mandatory_profile_ids
    ]
    validate_four_profile_candidate(authority, reports)

    stale = list(reports)
    stale[-1] = {**stale[-1], "source_revision": "c" * 40}
    with pytest.raises(M5QualificationError) as exc:
        validate_four_profile_candidate(authority, stale)
    assert exc.value.code == authority.error_code("release_evidence_incomplete")


def test_m5_cpu_p95_uses_fixed_interval_sampling_not_tiny_phase_ratios() -> None:
    source = RUNTIME_ENTRY.read_text(encoding="utf-8")
    assert "_CPU_SAMPLE_INTERVAL_SECONDS = 0.1" in source
    assert "target=_sample_normalized_cpu_utilization" in source
    assert '"normalized_cpu_sample_count": len(cpu_samples)' in source
    assert '"normalized_cpu_sample_interval_seconds": _CPU_SAMPLE_INTERVAL_SECONDS' in source
    assert "phase_cpu = time.process_time()" not in source
    assert "phase_wall = time.monotonic()" not in source
