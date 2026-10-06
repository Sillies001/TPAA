"""PIQB B1 product runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

_PRODUCTION_ROLES = frozenset(
    {
        "SUBJECT_SELF",
        "INSTRUCTOR_EVALUATOR",
        "TEAM_LEAD",
        "ANALYST",
        "ADMIN_AUDITOR",
    }
)
_NO_PRIVILEGED_IDENTITY = frozenset({"TEAM_LEAD", "ANALYST"})
_NO_VISIBILITY = frozenset({"TEAM_LEAD", "ANALYST"})
_NO_EXPORT = frozenset(
    {
        "SUBJECT_SELF",
        "INSTRUCTOR_EVALUATOR",
        "TEAM_LEAD",
        "ANALYST",
    }
)


class RuntimeProfile(StrEnum):
    """Supported product runtime profiles."""

    DESKTOP = "DESKTOP"
    SERVICE = "SERVICE"


@dataclass(frozen=True, slots=True)
class ProductionPrincipalBinding:
    """Secret-free credential fingerprint mapped to one frozen least-privilege role."""

    credential_sha256: str
    role: str
    actor_id: str | None
    scope_match: bool
    validation_only: bool = False
    privileged_identity_authorized: bool = False
    visibility_authorized: bool = False
    export_authorized: bool = False

    def __post_init__(self) -> None:
        digest = self.credential_sha256
        if (
            len(digest) != 64
            or digest != digest.lower()
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError("credential_sha256 must be lowercase SHA-256")
        if self.role not in _PRODUCTION_ROLES:
            raise ValueError("production role is not in frozen role family")
        if self.actor_id is not None and not self.actor_id.strip():
            raise ValueError("actor_id must be non-empty when configured")
        if (
            self.role in _NO_PRIVILEGED_IDENTITY
            and self.privileged_identity_authorized
        ):
            raise ValueError("role cannot receive direct identity privilege")
        if self.role in _NO_VISIBILITY and self.visibility_authorized:
            raise ValueError("role cannot receive annotation visibility privilege")
        if self.role in _NO_EXPORT and self.export_authorized:
            raise ValueError("role cannot receive export privilege")


@dataclass(frozen=True, slots=True)
class ProductRuntimeConfig:
    """Engine-neutral composition inputs for one TPAA product runtime."""

    profile: RuntimeProfile
    product_build_version: str
    authority_root: Path
    m1_fixture_root: Path | None = None

    def __post_init__(self) -> None:
        if not self.product_build_version.strip():
            raise ValueError("product_build_version must be non-empty")
        if not self.authority_root.is_dir():
            raise ValueError("authority_root must exist")
        if self.m1_fixture_root is not None and not self.m1_fixture_root.is_dir():
            raise ValueError("m1_fixture_root must exist when configured")


@dataclass(frozen=True, slots=True)
class ProductionRuntimeConfig:
    """PRCB production-only runtime configuration with explicit persistence."""

    profile: RuntimeProfile
    product_build_version: str
    authority_root: Path
    object_root: Path
    desktop_database_path: Path | None = None
    service_conninfo: str | None = None
    service_principals: tuple[ProductionPrincipalBinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.product_build_version.strip():
            raise ValueError("product_build_version must be non-empty")
        if not self.authority_root.is_dir():
            raise ValueError("authority_root must exist")
        if self.profile is RuntimeProfile.DESKTOP:
            if self.desktop_database_path is None:
                raise ValueError("Desktop production runtime requires database_path")
            if not self.desktop_database_path.is_file():
                raise ValueError("Desktop production database_path must exist")
            if self.service_conninfo is not None:
                raise ValueError("Desktop production runtime forbids service_conninfo")
            if self.service_principals:
                raise ValueError("Desktop runtime forbids service principal bindings")
        else:
            if not self.service_conninfo or not self.service_conninfo.strip():
                raise ValueError("Service production runtime requires conninfo")
            if self.desktop_database_path is not None:
                raise ValueError(
                    "Service production runtime forbids desktop_database_path"
                )
            digests = tuple(
                item.credential_sha256 for item in self.service_principals
            )
            if len(set(digests)) != len(digests):
                raise ValueError(
                    "Service principal credential fingerprints must be unique"
                )
