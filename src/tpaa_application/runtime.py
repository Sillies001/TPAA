"""Application projection of the M0 runtime baseline handshake.

The Application layer consumes the Core handshake result and exposes a transport-neutral
view for REST/GUI adapters. READY semantics remain owned by ``tpaa_canonical``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tpaa_canonical.runtime_handshake import (
    RuntimeBaselineHandshake,
    RuntimeBaselineIdentity,
    load_trusted_runtime_baseline_handshake,
)


@dataclass(frozen=True)
class RuntimeBaselineIdentityView:
    """Transport-neutral baseline/build identity projected by the Application layer."""

    product_build_version: str
    core_baseline: str
    baseline_lock_sha256: str
    db_schema_version: str
    core_authority_artifact_id: str
    core_authority_sha256: str
    p1_metric_catalog_version: str
    p1_metric_catalog_sha256: str
    dto_authority_sha256: str


@dataclass(frozen=True)
class RuntimeBaselineStatus:
    """Application-facing result of the authoritative Core handshake."""

    readiness: str
    ready: bool
    mismatches: tuple[str, ...]
    expected: RuntimeBaselineIdentityView
    observed: RuntimeBaselineIdentityView


RuntimeBaselineHandshakeProvider = Callable[[], RuntimeBaselineHandshake]


def _project_identity(identity: RuntimeBaselineIdentity) -> RuntimeBaselineIdentityView:
    return RuntimeBaselineIdentityView(
        product_build_version=identity.product_build_version,
        core_baseline=identity.core_baseline,
        baseline_lock_sha256=identity.baseline_lock_sha256,
        db_schema_version=identity.db_schema_version,
        core_authority_artifact_id=identity.core_authority_artifact_id,
        core_authority_sha256=identity.core_authority_sha256,
        p1_metric_catalog_version=identity.p1_metric_catalog_version,
        p1_metric_catalog_sha256=identity.p1_metric_catalog_sha256,
        dto_authority_sha256=identity.dto_authority_sha256,
    )


class GetRuntimeBaselineStatus:
    """Project the Core-owned handshake result without reimplementing READY rules."""

    def __init__(self, handshake_provider: RuntimeBaselineHandshakeProvider) -> None:
        self._handshake_provider = handshake_provider

    def execute(self) -> RuntimeBaselineStatus:
        handshake = self._handshake_provider()
        return RuntimeBaselineStatus(
            readiness=handshake.readiness.value,
            ready=handshake.ready,
            mismatches=tuple(mismatch.value for mismatch in handshake.mismatches),
            expected=_project_identity(handshake.expected),
            observed=_project_identity(handshake.observed),
        )


def build_trusted_runtime_status_use_case(*, product_build_version: str) -> GetRuntimeBaselineStatus:
    """Wire the local trusted Core identity into the Application readiness use case.

    This remains transport-neutral; Desktop/API adapters consume the returned use case
    without importing Canonical directly. M0-DEV-003 may later supply the product build
    version from a governed build manifest.
    """

    return GetRuntimeBaselineStatus(
        lambda: load_trusted_runtime_baseline_handshake(
            product_build_version=product_build_version
        )
    )
