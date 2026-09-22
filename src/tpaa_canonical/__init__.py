"""TPAA Canonical baseline trust boundary and runtime handshake model."""

from .loader import (
    EXPECTED_BASELINE_LOCK_SHA256,
    EXPECTED_CONTROLLED_ARTIFACT_COUNT,
    EXPECTED_CORE_BASELINE,
    UNVERSIONED_BY_AUTHORITY,
    ArtifactExpectation,
    CanonicalArtifact,
    CanonicalArtifactError,
    CanonicalArtifactLoader,
)
from .runtime_handshake import (
    RuntimeBaselineHandshake,
    RuntimeBaselineIdentity,
    RuntimeBaselineMismatch,
    RuntimeReadiness,
    evaluate_runtime_baseline_handshake,
    load_trusted_runtime_baseline_handshake,
    load_trusted_runtime_baseline_identity,
)

__all__ = [
    "EXPECTED_BASELINE_LOCK_SHA256",
    "EXPECTED_CONTROLLED_ARTIFACT_COUNT",
    "EXPECTED_CORE_BASELINE",
    "UNVERSIONED_BY_AUTHORITY",
    "ArtifactExpectation",
    "CanonicalArtifact",
    "CanonicalArtifactError",
    "CanonicalArtifactLoader",
    "RuntimeBaselineHandshake",
    "RuntimeBaselineIdentity",
    "RuntimeBaselineMismatch",
    "RuntimeReadiness",
    "evaluate_runtime_baseline_handshake",
    "load_trusted_runtime_baseline_handshake",
    "load_trusted_runtime_baseline_identity",
]
