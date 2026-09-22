"""Transport-neutral runtime baseline handshake model for M0-CORE-006.

The handshake is intentionally pure: it compares an expected build/baseline identity
with an observed runtime identity and returns a deterministic fail-closed readiness
result.  Transport, Repository, database-driver and GUI concerns remain outside this
module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .loader import CanonicalArtifactLoader


class RuntimeReadiness(StrEnum):
    """Business-command admission state owned by the runtime handshake."""

    READY = "READY"
    NOT_READY = "NOT_READY"


class RuntimeBaselineMismatch(StrEnum):
    """Deterministic engineering mismatch codes, not TPAA business reason codes."""

    PRODUCT_BUILD_VERSION = "PRODUCT_BUILD_VERSION_MISMATCH"
    CORE_BASELINE = "CORE_BASELINE_MISMATCH"
    BASELINE_LOCK_SHA256 = "BASELINE_LOCK_SHA256_MISMATCH"
    DB_SCHEMA_VERSION = "DB_SCHEMA_VERSION_MISMATCH"
    CORE_AUTHORITY = "CORE_AUTHORITY_MISMATCH"
    P1_METRIC_CATALOG_VERSION = "P1_METRIC_CATALOG_VERSION_MISMATCH"
    P1_METRIC_CATALOG_SHA256 = "P1_METRIC_CATALOG_SHA256_MISMATCH"
    DTO_AUTHORITY_SHA256 = "DTO_AUTHORITY_SHA256_MISMATCH"


@dataclass(frozen=True)
class RuntimeBaselineIdentity:
    """Version/hash identity exchanged by runtime readiness participants."""

    product_build_version: str
    core_baseline: str
    baseline_lock_sha256: str
    db_schema_version: str
    core_authority_artifact_id: str
    core_authority_sha256: str
    p1_metric_catalog_version: str
    p1_metric_catalog_sha256: str
    dto_authority_sha256: str

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True)
class RuntimeBaselineHandshake:
    """Fail-closed exact comparison result."""

    readiness: RuntimeReadiness
    mismatches: tuple[RuntimeBaselineMismatch, ...]
    expected: RuntimeBaselineIdentity
    observed: RuntimeBaselineIdentity

    @property
    def ready(self) -> bool:
        return self.readiness is RuntimeReadiness.READY


_COMPARISONS: tuple[tuple[str, RuntimeBaselineMismatch], ...] = (
    ("product_build_version", RuntimeBaselineMismatch.PRODUCT_BUILD_VERSION),
    ("core_baseline", RuntimeBaselineMismatch.CORE_BASELINE),
    ("baseline_lock_sha256", RuntimeBaselineMismatch.BASELINE_LOCK_SHA256),
    ("db_schema_version", RuntimeBaselineMismatch.DB_SCHEMA_VERSION),
    ("core_authority_artifact_id", RuntimeBaselineMismatch.CORE_AUTHORITY),
    ("core_authority_sha256", RuntimeBaselineMismatch.CORE_AUTHORITY),
    ("p1_metric_catalog_version", RuntimeBaselineMismatch.P1_METRIC_CATALOG_VERSION),
    ("p1_metric_catalog_sha256", RuntimeBaselineMismatch.P1_METRIC_CATALOG_SHA256),
    ("dto_authority_sha256", RuntimeBaselineMismatch.DTO_AUTHORITY_SHA256),
)


def evaluate_runtime_baseline_handshake(
    *,
    expected: RuntimeBaselineIdentity,
    observed: RuntimeBaselineIdentity,
) -> RuntimeBaselineHandshake:
    """Compare every governed identity dimension and fail closed on any mismatch."""

    mismatches: list[RuntimeBaselineMismatch] = []
    for field_name, mismatch in _COMPARISONS:
        if getattr(expected, field_name) != getattr(observed, field_name):
            if mismatch not in mismatches:
                mismatches.append(mismatch)
    frozen = tuple(mismatches)
    return RuntimeBaselineHandshake(
        readiness=(RuntimeReadiness.READY if not frozen else RuntimeReadiness.NOT_READY),
        mismatches=frozen,
        expected=expected,
        observed=observed,
    )


def load_trusted_runtime_baseline_identity(
    *,
    product_build_version: str,
    loader: CanonicalArtifactLoader | None = None,
) -> RuntimeBaselineIdentity:
    """Build the local trusted identity from the verified frozen Canonical baseline.

    ``product_build_version`` is explicit because M0-DEV-003 owns the future build
    manifest.  M0-CORE-006 defines comparison semantics without inventing that
    manifest or deriving a build identity from a filesystem path.
    """

    if not product_build_version:
        raise ValueError("product_build_version must be a non-empty string")

    canonical = loader or CanonicalArtifactLoader()
    baseline = canonical.baseline_metadata
    core_model = canonical.load("CORE_LOGICAL_MODEL")
    catalog = canonical.load("P1_METRIC_CATALOG")
    dto = canonical.load("CROSS_LAYER_DTO_CONTRACTS")

    core_baseline = baseline.get("core")
    db_schema = baseline.get("db_schema")
    if not isinstance(core_baseline, str) or not core_baseline:
        raise ValueError("verified baseline metadata must declare core")
    if not isinstance(db_schema, str) or not db_schema:
        raise ValueError("verified baseline metadata must declare db_schema")
    if catalog.declared_version is None:
        raise ValueError("P1_METRIC_CATALOG must declare catalog_version")

    return RuntimeBaselineIdentity(
        product_build_version=product_build_version,
        core_baseline=core_baseline,
        baseline_lock_sha256=core_model.baseline_lock_sha256,
        db_schema_version=db_schema,
        core_authority_artifact_id=core_model.artifact_id,
        core_authority_sha256=core_model.sha256,
        p1_metric_catalog_version=catalog.declared_version,
        p1_metric_catalog_sha256=catalog.sha256,
        dto_authority_sha256=dto.sha256,
    )
