"""M5 Batch 2 authority-driven package/performance/security qualification checks."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from .m5_profiles import M5QualificationAuthority, M5QualificationError

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be a mapping")
    return value


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    return float(value)


def _sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be lowercase SHA-256")
    return value


def validate_performance_measurements(
    authority: M5QualificationAuthority,
    profile_id: str,
    measurements: Mapping[str, object],
) -> None:
    """Apply every governed common/role threshold conjunctively."""

    profile = authority.certification_profile(profile_id)
    perf = authority.performance_resource_profile
    common = _mapping(perf.get("common_thresholds"), field="common_thresholds")
    role_key = "desktop_thresholds" if profile.role == "DESKTOP" else "service_thresholds"
    role = _mapping(perf.get(role_key), field=role_key)

    for key, raw_limit in (*common.items(), *role.items()):
        if key == "concurrency":
            actual = measurements.get(key)
            if actual != raw_limit:
                raise M5QualificationError(
                    authority.error_code("performance_threshold"),
                    f"{profile_id}:{key}:expected={raw_limit}:actual={actual}",
                )
            continue

        if key.endswith("_max"):
            metric = key.removesuffix("_max")
            actual = _number(measurements.get(metric), field=metric)
            limit = _number(raw_limit, field=key)
            if actual > limit:
                raise M5QualificationError(
                    authority.error_code("performance_threshold"),
                    f"{profile_id}:{metric}={actual}>{limit}",
                )
            continue

        if key.endswith("_min"):
            metric = key.removesuffix("_min")
            actual = _number(measurements.get(metric), field=metric)
            limit = _number(raw_limit, field=key)
            if actual < limit:
                raise M5QualificationError(
                    authority.error_code("performance_threshold"),
                    f"{profile_id}:{metric}={actual}<{limit}",
                )
            continue

        raise M5QualificationError(
            authority.error_code("authority_hash_mismatch"),
            f"unsupported performance threshold shape: {key}",
        )


def validate_package_qualification(
    authority: M5QualificationAuthority,
    profile_id: str,
    report: Mapping[str, object],
) -> None:
    """Validate one offline bundle and clean lifecycle against package authority."""

    authority.certification_profile(profile_id)
    package = authority.package_lifecycle_profile
    forms = _mapping(package.get("package_forms"), field="package_forms")
    expected_form = forms.get(profile_id)
    if report.get("package_form") != expected_form:
        raise M5QualificationError(
            authority.error_code("package_online_dependency"),
            f"{profile_id}: package form mismatch",
        )

    if report.get("source_revision") is None or _COMMIT_RE.fullmatch(
        str(report.get("source_revision"))
    ) is None:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            f"{profile_id}: source revision",
        )
    semantic = report.get("semantic_build_version")
    if not isinstance(semantic, str) or not semantic:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            f"{profile_id}: semantic build version",
        )

    prerequisites = _mapping(
        report.get("target_prerequisites"),
        field="target_prerequisites",
    )
    governed_prerequisites = _mapping(
        package.get("target_prerequisites"),
        field="package_lifecycle_profile.target_prerequisites",
    )
    if dict(prerequisites) != dict(governed_prerequisites) or any(
        value is not False for value in prerequisites.values()
    ):
        raise M5QualificationError(
            authority.error_code("package_online_dependency"),
            f"{profile_id}: target prerequisite drift",
        )

    required_evidence = package.get("required_package_evidence")
    if not isinstance(required_evidence, (list, tuple)):
        raise M5QualificationError(
            authority.error_code("authority_hash_mismatch"),
            "required_package_evidence",
        )
    evidence_hashes = _mapping(report.get("evidence_hashes"), field="evidence_hashes")
    for name in required_evidence:
        if not isinstance(name, str):
            raise M5QualificationError(
                authority.error_code("authority_hash_mismatch"),
                "required_package_evidence item",
            )
        _sha256(evidence_hashes.get(name), field=f"evidence_hashes.{name}")

    _sha256(report.get("package_sha256"), field="package_sha256")
    _sha256(report.get("package_manifest_sha256"), field="package_manifest_sha256")

    lifecycle = _mapping(report.get("lifecycle"), field="lifecycle")
    for key in (
        "clean_install_pass",
        "ready_start_pass",
        "component_smoke_pass",
        "graceful_stop_pass",
        "uninstall_pass",
        "no_residual_product_state",
    ):
        if lifecycle.get(key) is not True:
            raise M5QualificationError(
                authority.error_code("package_online_dependency"),
                f"{profile_id}: lifecycle {key}",
            )

    seconds = _mapping(report.get("lifecycle_seconds"), field="lifecycle_seconds")
    limits = _mapping(
        package.get("lifecycle_thresholds_seconds"),
        field="lifecycle_thresholds_seconds",
    )
    map_keys = {
        "build_max": "build",
        "clean_install_max": "clean_install",
        "ready_start_max": "ready_start",
        "graceful_stop_max": "graceful_stop",
        "uninstall_max": "uninstall",
    }
    for limit_key, result_key in map_keys.items():
        actual = _number(seconds.get(result_key), field=result_key)
        limit = _number(limits.get(limit_key), field=limit_key)
        if actual > limit:
            raise M5QualificationError(
                authority.error_code("package_online_dependency"),
                f"{profile_id}:{result_key}={actual}>{limit}",
            )


def _parse_utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be UTC Z timestamp")
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").astimezone(UTC)


def validate_security_qualification(
    authority: M5QualificationAuthority,
    profile_id: str,
    report: Mapping[str, object],
    *,
    evaluated_at_utc: str,
) -> None:
    """Validate SBOM/license/vulnerability/secret/auth/integrity evidence."""

    profile = authority.certification_profile(profile_id)
    security = authority.security_release_readiness_profile
    sbom = _mapping(security.get("sbom"), field="security.sbom")
    vulnerability = _mapping(
        security.get("vulnerability_acceptance"),
        field="security.vulnerability_acceptance",
    )
    secret = _mapping(
        security.get("secret_and_configuration"),
        field="security.secret_and_configuration",
    )
    integrity = _mapping(
        security.get("artifact_integrity"),
        field="security.artifact_integrity",
    )

    if report.get("severity_model") != vulnerability.get("severity_model"):
        raise M5QualificationError(
            authority.error_code("security_acceptance"),
            f"{profile_id}:severity model",
        )
    if report.get("unscored_advisory_count") != 0:
        raise M5QualificationError(
            authority.error_code("security_acceptance"),
            f"{profile_id}:unscored advisory",
        )

    exact_fields = {
        "sbom_format": sbom.get("format"),
        "sbom_spec_version": sbom.get("spec_version"),
        "dependency_authority": sbom.get("dependency_authority"),
    }
    for key, expected in exact_fields.items():
        if report.get(key) != expected:
            raise M5QualificationError(
                authority.error_code("security_acceptance"),
                f"{profile_id}:{key}",
            )
    if report.get("native_dependency_manifest_present") is not True:
        raise M5QualificationError(
            authority.error_code("security_acceptance"),
            f"{profile_id}:native dependency manifest",
        )

    maximums = {
        "unknown_unreviewed_license_count": sbom.get(
            "unknown_unreviewed_license_count_max"
        ),
        "critical_unwaived_count": vulnerability.get("critical_unwaived_count_max"),
        "high_unwaived_count": vulnerability.get("high_unwaived_count_max"),
        "medium_unwaived_count": vulnerability.get("medium_unwaived_count_max"),
        "high_confidence_secret_findings": secret.get(
            "high_confidence_secret_findings_max"
        ),
    }
    for key, raw_max in maximums.items():
        actual = _number(report.get(key), field=key)
        maximum = _number(raw_max, field=f"{key}_max")
        if actual > maximum:
            raise M5QualificationError(
                authority.error_code("security_acceptance"),
                f"{profile_id}:{key}={actual}>{maximum}",
            )

    _sha256(report.get("advisory_snapshot_sha256"), field="advisory_snapshot_sha256")
    if report.get("default_credentials_present") is not False:
        raise M5QualificationError(
            authority.error_code("security_acceptance"),
            f"{profile_id}:default credentials",
        )
    if profile.role == "SERVICE":
        if (
            report.get("service_authentication_required") is not True
            or report.get("service_default_deny_authorization") is not True
        ):
            raise M5QualificationError(
                authority.error_code("security_acceptance"),
                f"{profile_id}:service authentication/default-deny",
            )
    if profile.role == "DESKTOP" and report.get(
        "desktop_remote_bind_without_authentication"
    ) is not False:
        raise M5QualificationError(
            authority.error_code("security_acceptance"),
            f"{profile_id}:desktop remote bind",
        )

    if integrity.get("hash_algorithm") != "SHA-256":
        raise M5QualificationError(
            authority.error_code("authority_hash_mismatch"),
            "artifact_integrity.hash_algorithm",
        )
    artifact_hashes = _mapping(report.get("artifact_hashes"), field="artifact_hashes")
    if not artifact_hashes:
        raise M5QualificationError(
            authority.error_code("security_acceptance"),
            f"{profile_id}:artifact hashes empty",
        )
    for name, digest in artifact_hashes.items():
        _sha256(digest, field=f"artifact_hashes.{name}")
    for key in (
        "dependency_lock_sha256",
        "baseline_lock_sha256",
        "package_manifest_sha256",
    ):
        _sha256(report.get(key), field=key)

    waivers = report.get("waivers", ())
    if not isinstance(waivers, (list, tuple)):
        raise M5QualificationError(
            authority.error_code("security_acceptance"),
            f"{profile_id}:waivers shape",
        )
    now = _parse_utc(evaluated_at_utc, field="evaluated_at_utc")
    allowed = set(vulnerability.get("waiver_allowed_severities", ()))
    max_days = int(vulnerability.get("waiver_max_days", 0))
    required = vulnerability.get("waiver_required_fields", ())
    if not isinstance(required, (list, tuple)):
        raise M5QualificationError(
            authority.error_code("authority_hash_mismatch"),
            "waiver_required_fields",
        )
    for raw in waivers:
        waiver = _mapping(raw, field="waiver")
        if waiver.get("severity") not in allowed:
            raise M5QualificationError(
                authority.error_code("security_acceptance"),
                f"{profile_id}:waiver severity",
            )
        for field in required:
            if not isinstance(field, str) or not waiver.get(field):
                raise M5QualificationError(
                    authority.error_code("security_acceptance"),
                    f"{profile_id}:waiver missing {field}",
                )
        expires = _parse_utc(waiver.get("expires_at_utc"), field="expires_at_utc")
        issued = _parse_utc(waiver.get("issued_at_utc"), field="issued_at_utc")
        if (
            expires <= now
            or (expires - issued).total_seconds() > max_days * 86400
        ):
            raise M5QualificationError(
                authority.error_code("security_acceptance"),
                f"{profile_id}:waiver expiry/duration",
            )


def validate_four_profile_candidate(
    authority: M5QualificationAuthority,
    reports: Sequence[Mapping[str, object]],
) -> None:
    """Require one exact source/build across exactly the four mandatory profiles."""

    if len(reports) != len(authority.mandatory_profile_ids):
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "mandatory profile report count",
        )
    by_profile: dict[str, Mapping[str, object]] = {}
    for report in reports:
        profile_id = report.get("profile_id")
        if not isinstance(profile_id, str):
            raise M5QualificationError(
                authority.error_code("release_evidence_incomplete"),
                "profile_id",
            )
        authority.certification_profile(profile_id)
        if profile_id in by_profile:
            raise M5QualificationError(
                authority.error_code("release_evidence_incomplete"),
                f"duplicate profile {profile_id}",
            )
        by_profile[profile_id] = report

    if tuple(by_profile) != authority.mandatory_profile_ids:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "exact four-profile inventory/order mismatch",
        )
    revisions = {report.get("source_revision") for report in reports}
    builds = {report.get("semantic_build_version") for report in reports}
    if len(revisions) != 1 or len(builds) != 1:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "same candidate source/build required",
        )
    revision = next(iter(revisions))
    build = next(iter(builds))
    if not isinstance(revision, str) or _COMMIT_RE.fullmatch(revision) is None:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "candidate source revision",
        )
    if not isinstance(build, str) or not build:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "semantic build version",
        )
    if any(report.get("status") != "PASS" for report in reports):
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "mandatory profile failure blocks release candidate",
        )
