"""PIQB B1 product runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from tpaa_storage import ObjectStore

from .principal_policy import (
    PrincipalPolicyError,
    validate_production_principal_policy,
)


class RuntimeProfile(StrEnum):
    """Supported product runtime profiles."""

    DESKTOP = "DESKTOP"
    SERVICE = "SERVICE"


@dataclass(frozen=True, slots=True)
class OidcMtlsRuntimeConfig:
    issuer: str
    audience: str
    jwks_uri: str
    ca_bundle_path: Path
    allowed_spiffe_prefixes: tuple[str, ...]
    revocation_file: Path

    def __post_init__(self) -> None:
        if not self.issuer.startswith("https://") or not self.jwks_uri.startswith("https://"):
            raise ValueError("OIDC issuer and JWKS URI must use HTTPS")
        if not self.audience or not self.allowed_spiffe_prefixes:
            raise ValueError("OIDC audience and mTLS SPIFFE prefixes are required")
        if not self.ca_bundle_path.is_file():
            raise ValueError("mTLS CA bundle must exist")
        if not self.revocation_file.is_file():
            raise ValueError("identity revocation file must exist")


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
        if self.actor_id is not None and not self.actor_id.strip():
            raise ValueError("actor_id must be non-empty when configured")
        try:
            validate_production_principal_policy(
                role=self.role,
                privileged_identity_authorized=(self.privileged_identity_authorized),
                visibility_authorized=self.visibility_authorized,
                export_authorized=self.export_authorized,
            )
        except PrincipalPolicyError as exc:
            raise ValueError(str(exc)) from exc


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
class FormalQualificationEvidenceConfig:
    """Trust and exact-candidate binding for signed W7-W9 evidence."""

    manifest_path: Path
    trust_root_path: Path
    key_id: str
    candidate_identity_sha256: str
    source_revision: str

    def __post_init__(self) -> None:
        if not self.manifest_path.is_file():
            raise ValueError("formal qualification manifest must exist")
        if not self.trust_root_path.is_file():
            raise ValueError("formal qualification trust root must exist")
        if not self.key_id.strip():
            raise ValueError("formal qualification key_id must be non-empty")
        digest = self.candidate_identity_sha256
        if (
            len(digest) != 64
            or digest != digest.lower()
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("formal candidate identity must be lowercase SHA-256")
        revision = self.source_revision
        if (
            len(revision) != 40
            or revision != revision.lower()
            or any(character not in "0123456789abcdef" for character in revision)
        ):
            raise ValueError("formal source revision must be a lowercase Git SHA")


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
    service_identity: OidcMtlsRuntimeConfig | None = None
    object_store: ObjectStore | None = None
    migration_state_root: Path | None = None
    formal_qualification: FormalQualificationEvidenceConfig | None = None

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
            if self.service_identity is not None:
                raise ValueError("Desktop runtime forbids Service identity configuration")
            if self.object_store is not None:
                raise ValueError("Desktop runtime uses its governed local object store")
        else:
            if not self.service_conninfo or not self.service_conninfo.strip():
                raise ValueError("Service production runtime requires conninfo")
            if self.desktop_database_path is not None:
                raise ValueError("Service production runtime forbids desktop_database_path")
            if bool(self.service_principals) == (self.service_identity is not None):
                raise ValueError("Service runtime requires exactly one identity provider")
            digests = tuple(item.credential_sha256 for item in self.service_principals)
            if len(set(digests)) != len(digests):
                raise ValueError("Service principal credential fingerprints must be unique")
