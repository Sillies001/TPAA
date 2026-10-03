"""M5 Batch 1 formal qualification authority projections and fail-closed guards.

The protected Canonical artifacts remain the only qualification authority. This
module validates their trust boundary and projects executable, immutable views
without restating qualification thresholds as implementation constants.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from tpaa_canonical import (
    ArtifactExpectation,
    CanonicalArtifactError,
    CanonicalArtifactLoader,
)

M5_AUTHORITY_ID = "M5_FORMAL_QUALIFICATION_AUTHORITY"
M5_AUTHORITY_VERSION = "1.0.0"
M5_DB_SCHEMA_VERSION = "1.6.0"
PLATFORM_REGISTRY_ID = "PLATFORM_COMPATIBILITY_REGISTRY"
PLATFORM_REGISTRY_VERSION = "1.0.0"

M5_AUTHORITY_MISSING_CODE = "FAIL_CLOSED_M5_QUALIFICATION_AUTHORITY_REQUIRED"
M5_AUTHORITY_MISMATCH_CODE = "FAIL_CLOSED_M5_AUTHORITY_HASH_MISMATCH"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class M5QualificationError(RuntimeError):
    """Fail-closed qualification error with a stable governed diagnostic code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True, slots=True)
class M5CertificationProfile:
    profile_id: str
    os_family: str
    role: str
    reference_environment: str
    required_components: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M5ResultBinding:
    source_revision: str
    semantic_build_version: str
    certification_profile_id: str
    workload_id: str
    workload_spec_hash: str
    generated_workload_manifest_sha256: str
    baseline_lock_sha256: str
    dependency_lock_sha256: str
    hardware_manifest_sha256: str

    def projection(self) -> dict[str, str]:
        return {
            "source_revision": self.source_revision,
            "semantic_build_version": self.semantic_build_version,
            "certification_profile_id": self.certification_profile_id,
            "workload_id": self.workload_id,
            "workload_spec_hash": self.workload_spec_hash,
            "generated_workload_manifest_sha256": self.generated_workload_manifest_sha256,
            "baseline_lock_sha256": self.baseline_lock_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "hardware_manifest_sha256": self.hardware_manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class M5QualificationAuthority:
    version: str
    authority_sha256: str
    baseline_lock_sha256: str
    db_schema_version: str
    admitted_phases: tuple[str, ...]
    excluded_phases: tuple[str, ...]
    mandatory_profiles: tuple[M5CertificationProfile, ...]
    target_hardware_profile: Mapping[str, Any]
    workload_profile: Mapping[str, Any]
    performance_resource_profile: Mapping[str, Any]
    security_release_readiness_profile: Mapping[str, Any]
    package_lifecycle_profile: Mapping[str, Any]
    upgrade_backup_restore_profile: Mapping[str, Any]
    formal_release_acceptance_profile: Mapping[str, Any]
    profile_hashes: Mapping[str, str]
    fail_closed_error_codes: Mapping[str, str]

    @property
    def mandatory_profile_ids(self) -> tuple[str, ...]:
        return tuple(profile.profile_id for profile in self.mandatory_profiles)

    def error_code(self, key: str) -> str:
        value = self.fail_closed_error_codes.get(key)
        if not isinstance(value, str) or not value:
            raise M5QualificationError(
                M5_AUTHORITY_MISMATCH_CODE,
                f"missing fail-closed error code {key}",
            )
        return value

    def certification_profile(self, profile_id: str) -> M5CertificationProfile:
        for profile in self.mandatory_profiles:
            if profile.profile_id == profile_id:
                return profile
        raise M5QualificationError(
            self.error_code("unsupported_profile"),
            profile_id,
        )


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise M5QualificationError(
            M5_AUTHORITY_MISMATCH_CODE,
            f"{field} must be an object",
        )
    return cast(Mapping[str, Any], value)


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M5QualificationError(
            M5_AUTHORITY_MISMATCH_CODE,
            f"{field} must be a non-empty-string sequence",
        )
    return tuple(cast(str, item) for item in value)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _frozen_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen = _freeze(value)
    assert isinstance(frozen, Mapping)
    return cast(Mapping[str, Any], frozen)


def _canonical_hash(value: object) -> str:
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _profile_hashes(value: object) -> Mapping[str, str]:
    raw = _mapping(value, field="profile_hashes")
    result: dict[str, str] = {}
    for key, digest in raw.items():
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise M5QualificationError(
                M5_AUTHORITY_MISMATCH_CODE,
                f"profile_hashes.{key}",
            )
        result[key] = digest
    return MappingProxyType(result)


def _error_codes(value: object) -> Mapping[str, str]:
    raw = _mapping(value, field="fail_closed_error_codes")
    result: dict[str, str] = {}
    for key, code in raw.items():
        if not isinstance(code, str) or not code.startswith("FAIL_CLOSED_M5_"):
            raise M5QualificationError(
                M5_AUTHORITY_MISMATCH_CODE,
                f"fail_closed_error_codes.{key}",
            )
        result[key] = code

    required = {
        "authority_missing",
        "authority_hash_mismatch",
        "unsupported_profile",
        "hardware_below_minimum",
        "workload_mismatch",
        "performance_threshold",
        "security_acceptance",
        "package_online_dependency",
        "upgrade_rollback",
        "backup_restore",
        "release_evidence_incomplete",
        "signoff_missing_or_not_distinct",
        "m5_exit_not_go",
    }
    missing = sorted(required - set(result))
    if missing:
        raise M5QualificationError(
            M5_AUTHORITY_MISMATCH_CODE,
            "missing fail-closed codes: " + ",".join(missing),
        )
    if (
        result["authority_missing"] != M5_AUTHORITY_MISSING_CODE
        or result["authority_hash_mismatch"] != M5_AUTHORITY_MISMATCH_CODE
    ):
        raise M5QualificationError(
            M5_AUTHORITY_MISMATCH_CODE,
            "bootstrap authority error-code mismatch",
        )
    return MappingProxyType(result)


def _map_canonical_error(exc: CanonicalArtifactError) -> M5QualificationError:
    missing_reasons = {
        "BASELINE_LOCK_READ_ERROR",
        "MISSING_CANONICAL_ROOT",
        "MISSING_CONTROLLED_ARTIFACT",
        "UNKNOWN_ARTIFACT",
    }
    code = (
        M5_AUTHORITY_MISSING_CODE
        if exc.reason in missing_reasons
        else M5_AUTHORITY_MISMATCH_CODE
    )
    return M5QualificationError(code, str(exc))


def load_m5_qualification_authority(
    baseline_root: Path | None = None,
    *,
    loader: CanonicalArtifactLoader | None = None,
) -> M5QualificationAuthority:
    """Load and project exact M5 qualification authority from the trusted baseline."""

    try:
        canonical = loader or CanonicalArtifactLoader(baseline_root)
        authority_artifact = canonical.load(
            M5_AUTHORITY_ID,
            expectation=ArtifactExpectation(
                version=M5_AUTHORITY_VERSION,
                schema_version=M5_DB_SCHEMA_VERSION,
                required_top_level_keys=(
                    "scope",
                    "source_basis",
                    "target_hardware_profile",
                    "workload_profile",
                    "performance_resource_profile",
                    "security_release_readiness_profile",
                    "package_lifecycle_profile",
                    "upgrade_backup_restore_profile",
                    "formal_release_acceptance_profile",
                    "profile_hashes",
                    "fail_closed_error_codes",
                ),
            ),
        )
        platform_artifact = canonical.load(
            PLATFORM_REGISTRY_ID,
            expectation=ArtifactExpectation(
                version=PLATFORM_REGISTRY_VERSION,
                required_top_level_keys=("certification_profiles",),
            ),
        )
    except CanonicalArtifactError as exc:
        raise _map_canonical_error(exc) from exc

    if (
        authority_artifact.declared_id != M5_AUTHORITY_ID
        or platform_artifact.declared_id != PLATFORM_REGISTRY_ID
    ):
        raise M5QualificationError(
            M5_AUTHORITY_MISMATCH_CODE,
            "controlled artifact identity mismatch",
        )

    payload = authority_artifact.payload
    scope = _mapping(payload["scope"], field="scope")
    source_basis = _mapping(payload["source_basis"], field="source_basis")
    hardware = _mapping(
        payload["target_hardware_profile"],
        field="target_hardware_profile",
    )
    workload = _mapping(payload["workload_profile"], field="workload_profile")
    performance = _mapping(
        payload["performance_resource_profile"],
        field="performance_resource_profile",
    )
    security = _mapping(
        payload["security_release_readiness_profile"],
        field="security_release_readiness_profile",
    )
    package = _mapping(payload["package_lifecycle_profile"], field="package_lifecycle_profile")
    recovery = _mapping(
        payload["upgrade_backup_restore_profile"],
        field="upgrade_backup_restore_profile",
    )
    release = _mapping(
        payload["formal_release_acceptance_profile"],
        field="formal_release_acceptance_profile",
    )
    hashes = _profile_hashes(payload["profile_hashes"])
    error_codes = _error_codes(payload["fail_closed_error_codes"])

    expected_hashes = {
        "target_hardware_profile_sha256": hardware,
        "workload_profile_sha256": workload,
        "performance_profile_sha256": performance,
        "security_profile_sha256": security,
        "package_profile_sha256": package,
        "recovery_profile_sha256": recovery,
        "release_acceptance_profile_sha256": release,
    }
    for hash_key, profile in expected_hashes.items():
        if hashes.get(hash_key) != _canonical_hash(profile):
            raise M5QualificationError(
                error_codes["authority_hash_mismatch"],
                hash_key,
            )

    platform_hash = source_basis.get("platform_compatibility_registry_sha256")
    if platform_hash != platform_artifact.sha256:
        raise M5QualificationError(
            error_codes["authority_hash_mismatch"],
            "PLATFORM_COMPATIBILITY_REGISTRY",
        )

    admitted = _strings(
        scope.get("admitted_capability_phase"),
        field="scope.admitted_capability_phase",
    )
    excluded = _strings(
        scope.get("excluded_capability_phases"),
        field="scope.excluded_capability_phases",
    )
    if set(admitted) & set(excluded):
        raise M5QualificationError(
            error_codes["authority_hash_mismatch"],
            "capability phase overlap",
        )

    mandatory_ids = _strings(
        scope.get("mandatory_certification_profiles"),
        field="scope.mandatory_certification_profiles",
    )
    platform_payload = platform_artifact.payload
    registry_profiles = _mapping(
        platform_payload["certification_profiles"],
        field="PLATFORM_COMPATIBILITY_REGISTRY.certification_profiles",
    )
    if tuple(registry_profiles) != mandatory_ids:
        raise M5QualificationError(
            error_codes["unsupported_profile"],
            "mandatory profile inventory does not exactly match platform registry",
        )

    profiles: list[M5CertificationProfile] = []
    for profile_id in mandatory_ids:
        raw_profile = _mapping(
            registry_profiles.get(profile_id),
            field=f"certification_profiles.{profile_id}",
        )
        if raw_profile.get("required") is not True:
            raise M5QualificationError(
                error_codes["unsupported_profile"],
                f"{profile_id} is not required",
            )
        os_family = raw_profile.get("os_family")
        role = raw_profile.get("role")
        reference_environment = raw_profile.get("reference_environment")
        if not all(
            isinstance(value, str) and value
            for value in (os_family, role, reference_environment)
        ):
            raise M5QualificationError(
                error_codes["authority_hash_mismatch"],
                profile_id,
            )
        profiles.append(
            M5CertificationProfile(
                profile_id=profile_id,
                os_family=cast(str, os_family),
                role=cast(str, role),
                reference_environment=cast(str, reference_environment),
                required_components=_strings(
                    raw_profile.get("required_components"),
                    field=f"certification_profiles.{profile_id}.required_components",
                ),
            )
        )

    release_profiles = _strings(
        release.get("required_certification_profiles"),
        field="formal_release_acceptance_profile.required_certification_profiles",
    )
    if release_profiles != mandatory_ids:
        raise M5QualificationError(
            error_codes["authority_hash_mismatch"],
            "formal release profile inventory mismatch",
        )

    workload_id = workload.get("workload_id")
    performance_workload_id = performance.get("workload_id")
    workload_hash = hashes.get("workload_profile_sha256")
    if (
        not isinstance(workload_id, str)
        or workload_id != performance_workload_id
        or performance.get("workload_spec_hash") != workload_hash
    ):
        raise M5QualificationError(
            error_codes["workload_mismatch"],
            "workload identity/profile hash mismatch",
        )

    workload_desktop_concurrency = workload.get("desktop_concurrency")
    workload_service_concurrency = workload.get("service_concurrency")
    desktop_thresholds = _mapping(
        performance.get("desktop_thresholds"),
        field="performance_resource_profile.desktop_thresholds",
    )
    service_thresholds = _mapping(
        performance.get("service_thresholds"),
        field="performance_resource_profile.service_thresholds",
    )
    if (
        desktop_thresholds.get("concurrency") != workload_desktop_concurrency
        or service_thresholds.get("concurrency") != workload_service_concurrency
    ):
        raise M5QualificationError(
            error_codes["workload_mismatch"],
            "workload/performance concurrency mismatch",
        )

    baseline_schema = canonical.baseline_metadata.get("db_schema")
    if (
        baseline_schema not in {authority_artifact.schema_version, "1.7.0"}
        or scope.get("db_schema_version") != authority_artifact.schema_version
        or scope.get("db_schema_change") is not False
        or scope.get("shadow_schema_permitted") is not False
    ):
        raise M5QualificationError(
            error_codes["authority_hash_mismatch"],
            "DB schema or shadow-schema scope drift",
        )

    if (
        scope.get("m5_formal_release_claim_active_before_exit_go") is not False
        or release.get("protected_main_m5_exit_go_required") is not True
        or release.get("exact_release_references_required") is not True
        or release.get("current_latest_substitution_forbidden") is not True
    ):
        raise M5QualificationError(
            error_codes["authority_hash_mismatch"],
            "formal claim guard authority drift",
        )

    return M5QualificationAuthority(
        version=authority_artifact.declared_version or "",
        authority_sha256=authority_artifact.sha256,
        baseline_lock_sha256=authority_artifact.baseline_lock_sha256,
        db_schema_version=authority_artifact.schema_version or "",
        admitted_phases=admitted,
        excluded_phases=excluded,
        mandatory_profiles=tuple(profiles),
        target_hardware_profile=_frozen_mapping(hardware),
        workload_profile=_frozen_mapping(workload),
        performance_resource_profile=_frozen_mapping(performance),
        security_release_readiness_profile=_frozen_mapping(security),
        package_lifecycle_profile=_frozen_mapping(package),
        upgrade_backup_restore_profile=_frozen_mapping(recovery),
        formal_release_acceptance_profile=_frozen_mapping(release),
        profile_hashes=hashes,
        fail_closed_error_codes=error_codes,
    )


def performance_thresholds_for_profile(
    authority: M5QualificationAuthority,
    profile_id: str,
) -> Mapping[str, int | float]:
    """Project the exact authority thresholds applicable to one mandatory profile."""

    profile = authority.certification_profile(profile_id)
    performance = authority.performance_resource_profile
    common = _mapping(
        performance.get("common_thresholds"),
        field="performance_resource_profile.common_thresholds",
    )
    if profile.role == "DESKTOP":
        role_thresholds = _mapping(
            performance.get("desktop_thresholds"),
            field="performance_resource_profile.desktop_thresholds",
        )
    elif profile.role == "SERVICE":
        role_thresholds = _mapping(
            performance.get("service_thresholds"),
            field="performance_resource_profile.service_thresholds",
        )
    else:
        raise M5QualificationError(
            authority.error_code("unsupported_profile"),
            f"{profile.profile_id} role={profile.role}",
        )

    merged: dict[str, int | float] = {}
    for source in (common, role_thresholds):
        for key, value in source.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise M5QualificationError(
                    authority.error_code("authority_hash_mismatch"),
                    f"performance threshold {key}",
                )
            merged[key] = value
    return MappingProxyType(merged)


def validate_target_hardware(
    authority: M5QualificationAuthority,
    identity: Mapping[str, object],
) -> None:
    """Validate a hardware identity manifest against the governed minimum profile."""

    hardware = authority.target_hardware_profile
    required_fields = _strings(
        hardware.get("identity_manifest_required_fields"),
        field="target_hardware_profile.identity_manifest_required_fields",
    )
    missing = tuple(field for field in required_fields if field not in identity)
    if missing:
        raise M5QualificationError(
            authority.error_code("hardware_below_minimum"),
            "missing identity fields: " + ",".join(missing),
        )

    profile_id = identity.get("certification_profile_id")
    if not isinstance(profile_id, str):
        raise M5QualificationError(
            authority.error_code("unsupported_profile"),
            "certification_profile_id",
        )
    authority.certification_profile(profile_id)

    if identity.get("machine_architecture") != hardware.get("architecture"):
        raise M5QualificationError(
            authority.error_code("hardware_below_minimum"),
            "machine_architecture",
        )

    numeric_checks = (
        ("logical_cpu_count", "logical_cpu_min"),
        ("memory_gib", "memory_gib_min"),
        ("free_storage_gib", "free_storage_gib_min"),
    )
    for identity_key, authority_key in numeric_checks:
        actual = identity.get(identity_key)
        minimum = hardware.get(authority_key)
        if (
            isinstance(actual, bool)
            or not isinstance(actual, (int, float))
            or isinstance(minimum, bool)
            or not isinstance(minimum, (int, float))
            or actual < minimum
        ):
            raise M5QualificationError(
                authority.error_code("hardware_below_minimum"),
                identity_key,
            )

    allowed_storage = hardware.get("persistent_storage_class")
    if not isinstance(allowed_storage, tuple) or identity.get(
        "persistent_storage_class"
    ) not in allowed_storage:
        raise M5QualificationError(
            authority.error_code("hardware_below_minimum"),
            "persistent_storage_class",
        )


def build_result_binding(
    authority: M5QualificationAuthority,
    *,
    source_revision: str,
    semantic_build_version: str,
    certification_profile_id: str,
    generated_workload_manifest_sha256: str,
    dependency_lock_sha256: str,
    hardware_manifest_sha256: str,
) -> M5ResultBinding:
    """Build the exact identity envelope required for future qualification results."""

    authority.certification_profile(certification_profile_id)
    workload_id = authority.workload_profile.get("workload_id")
    workload_spec_hash = authority.performance_resource_profile.get("workload_spec_hash")
    if not isinstance(workload_id, str) or not isinstance(workload_spec_hash, str):
        raise M5QualificationError(
            authority.error_code("workload_mismatch"),
            "workload identity is not a string",
        )
    binding = M5ResultBinding(
        source_revision=source_revision,
        semantic_build_version=semantic_build_version,
        certification_profile_id=certification_profile_id,
        workload_id=workload_id,
        workload_spec_hash=workload_spec_hash,
        generated_workload_manifest_sha256=generated_workload_manifest_sha256,
        baseline_lock_sha256=authority.baseline_lock_sha256,
        dependency_lock_sha256=dependency_lock_sha256,
        hardware_manifest_sha256=hardware_manifest_sha256,
    )
    validate_result_binding(authority, binding)
    return binding


def validate_result_binding(
    authority: M5QualificationAuthority,
    binding: M5ResultBinding,
) -> None:
    """Reject stale or incomplete performance/security result identity envelopes."""

    authority.certification_profile(binding.certification_profile_id)
    if not _COMMIT_RE.fullmatch(binding.source_revision):
        raise M5QualificationError(
            authority.error_code("workload_mismatch"),
            "source_revision",
        )
    if not binding.semantic_build_version.strip():
        raise M5QualificationError(
            authority.error_code("workload_mismatch"),
            "semantic_build_version",
        )
    for field_name in (
        "workload_spec_hash",
        "generated_workload_manifest_sha256",
        "baseline_lock_sha256",
        "dependency_lock_sha256",
        "hardware_manifest_sha256",
    ):
        if not _SHA256_RE.fullmatch(getattr(binding, field_name)):
            raise M5QualificationError(
                authority.error_code("workload_mismatch"),
                field_name,
            )

    expected_workload = authority.workload_profile.get("workload_id")
    expected_workload_hash = authority.performance_resource_profile.get(
        "workload_spec_hash"
    )
    if (
        binding.workload_id != expected_workload
        or binding.workload_spec_hash != expected_workload_hash
        or binding.baseline_lock_sha256 != authority.baseline_lock_sha256
    ):
        raise M5QualificationError(
            authority.error_code("workload_mismatch"),
            "stale qualification binding",
        )


def security_profile_for_profile(
    authority: M5QualificationAuthority,
    profile_id: str,
) -> Mapping[str, Any]:
    """Return the exact immutable security authority for a mandatory profile."""

    authority.certification_profile(profile_id)
    return authority.security_release_readiness_profile


def validate_m5_formal_claim_prerequisites(
    authority: M5QualificationAuthority,
    *,
    capability_phase: str,
    m5_exit_decision: str,
    exact_evidence_manifest_accepted: bool,
    candidate_source_revision: str,
    exit_source_revision: str,
) -> None:
    """Fail closed unless the Batch 1 prerequisites for a formal M5 claim are met."""

    if capability_phase not in authority.admitted_phases:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            f"capability_phase={capability_phase}",
        )
    if m5_exit_decision != "GO":
        raise M5QualificationError(
            authority.error_code("m5_exit_not_go"),
            m5_exit_decision,
        )
    if not exact_evidence_manifest_accepted:
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "exact evidence manifest not accepted",
        )
    if (
        not _COMMIT_RE.fullmatch(candidate_source_revision)
        or not _COMMIT_RE.fullmatch(exit_source_revision)
        or candidate_source_revision != exit_source_revision
    ):
        raise M5QualificationError(
            authority.error_code("release_evidence_incomplete"),
            "candidate/Exit source revision mismatch",
        )
