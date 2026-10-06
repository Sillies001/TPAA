from __future__ import annotations

import hashlib

import pytest
from starlette.requests import Request

from tpaa_api import UnifiedPrincipal
from tpaa_application import RuntimeBaselineIdentityView, RuntimeBaselineStatus
from tpaa_runtime import (
    ConfiguredBearerIdentityProvider,
    ProductAdmissionResolver,
    ProductFeatureAvailability,
    ProductionIdentityError,
    ProductionPrincipalBinding,
    ProductionRuntimeReadiness,
    guard_production_principal_resolver,
)

_PHASES = ("P1", "P2", "P3", "P4", "P5", "P6")


def _request(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [
                (
                    b"authorization",
                    f"Bearer {token}".encode("ascii"),
                )
            ],
        }
    )


def _binding(token: str, role: str = "ANALYST") -> ProductionPrincipalBinding:
    return ProductionPrincipalBinding(
        credential_sha256=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        role=role,
        actor_id=None,
        scope_match=True,
    )


def _states(
    availability: ProductFeatureAvailability,
) -> set[object]:
    payload = availability.execute()
    items = payload["items"]
    assert isinstance(items, list)
    return {
        item["state"]
        for item in items
        if isinstance(item, dict)
    }


def test_prcb_c3_configured_identity_maps_secret_hash_to_least_privilege() -> None:
    provider = ConfiguredBearerIdentityProvider((_binding("analyst-secret"),))
    principal = provider.resolve(_request("analyst-secret"))

    assert principal.role == "ANALYST"
    assert principal.scope_match is True
    assert principal.privileged_identity_authorized is False
    assert principal.visibility_authorized is False
    assert principal.export_authorized is False
    with pytest.raises(ProductionIdentityError):
        provider.resolve(_request("wrong-secret"))


def test_prcb_c3_rejects_all_powerful_or_escalated_role_mapping() -> None:
    with pytest.raises(ValueError):
        _binding("system-secret", role="SYSTEM")
    with pytest.raises(ValueError):
        ProductionPrincipalBinding(
            credential_sha256=hashlib.sha256(b"analyst").hexdigest(),
            role="ANALYST",
            actor_id=None,
            scope_match=True,
            privileged_identity_authorized=True,
        )

    guarded = guard_production_principal_resolver(
        lambda _request: UnifiedPrincipal(
            role="SYSTEM",
            actor_id=None,
            scope_match=True,
            privileged_identity_authorized=True,
            visibility_authorized=True,
            export_authorized=True,
        )
    )
    with pytest.raises(ProductionIdentityError):
        guarded(_request("unused"))


def test_prcb_c3_feature_availability_rechecks_live_dependencies() -> None:
    live = {"ready": True}

    def dependency_flags() -> dict[str, bool]:
        return {phase: live["ready"] for phase in _PHASES}

    availability = ProductFeatureAvailability(
        ProductAdmissionResolver(),
        configured={phase: True for phase in _PHASES},
        dependency_ready=dependency_flags,
    )
    assert _states(availability) == {"AVAILABLE"}
    live["ready"] = False
    assert _states(availability) == {"DEPENDENCY_MISSING"}


def test_prcb_c3_runtime_readiness_fails_closed_on_dependency_loss() -> None:
    identity = RuntimeBaselineIdentityView(
        product_build_version="1.0.1",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="a",
        db_schema_version="1.9.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="b",
        p1_metric_catalog_version="1",
        p1_metric_catalog_sha256="c",
        dto_authority_sha256="d",
    )
    core = RuntimeBaselineStatus(
        readiness="READY",
        ready=True,
        mismatches=(),
        expected=identity,
        observed=identity,
    )

    class _Core:
        def execute(self) -> RuntimeBaselineStatus:
            return core

    availability = ProductFeatureAvailability(
        ProductAdmissionResolver(),
        configured={phase: True for phase in _PHASES},
        dependency_ready={phase: phase != "P6" for phase in _PHASES},
    )
    status = ProductionRuntimeReadiness(_Core(), availability).execute()
    assert status.ready is False
    assert status.readiness == "NOT_READY"
    assert status.mismatches == ("FEATURE_P6_DEPENDENCY_MISSING",)
