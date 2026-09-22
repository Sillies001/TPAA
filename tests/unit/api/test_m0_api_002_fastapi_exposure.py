from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from tpaa_api import create_app
from tpaa_application import ApplicationService, GetRuntimeBaselineStatus
from tpaa_canonical.runtime_handshake import (
    RuntimeBaselineIdentity,
    evaluate_runtime_baseline_handshake,
)


class _UnusedStorageUseCase:
    def execute(self) -> object:  # pragma: no cover - should not be touched by API-002 tests
        raise AssertionError("storage baseline use case must not be called by API-002 endpoints")


def _identity() -> RuntimeBaselineIdentity:
    return RuntimeBaselineIdentity(
        product_build_version="build-1",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="lock-sha",
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="core-sha",
        p1_metric_catalog_version="P1-1.0",
        p1_metric_catalog_sha256="catalog-sha",
        dto_authority_sha256="dto-sha",
    )


def _application(observed: RuntimeBaselineIdentity | None = None) -> ApplicationService:
    expected = _identity()
    actual = observed or expected
    runtime = GetRuntimeBaselineStatus(
        lambda: evaluate_runtime_baseline_handshake(expected=expected, observed=actual)
    )
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorageUseCase(),  # type: ignore[arg-type]
        get_runtime_baseline_status=runtime,
    )


def test_health_is_liveness_only_and_returns_200() -> None:
    app = create_app(_application())
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_readiness_ready_returns_200_without_recomputing_identity() -> None:
    app = create_app(_application())
    with TestClient(app) as client:
        response = client.get("/readiness")

    assert response.status_code == 200
    assert response.json() == {"status": "READY", "ready": True, "mismatches": []}


def test_readiness_not_ready_returns_503_and_core_mismatch_code() -> None:
    observed = replace(_identity(), db_schema_version="1.5.0")
    app = create_app(_application(observed))
    with TestClient(app) as client:
        response = client.get("/readiness")

    assert response.status_code == 503
    assert response.json() == {
        "status": "NOT_READY",
        "ready": False,
        "mismatches": ["DB_SCHEMA_VERSION_MISMATCH"],
    }


def test_version_exposes_expected_and_observed_diagnostic_identity() -> None:
    observed = replace(_identity(), product_build_version="build-other")
    app = create_app(_application(observed))
    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness"] == "NOT_READY"
    assert payload["expected"]["product_build_version"] == "build-1"
    assert payload["observed"]["product_build_version"] == "build-other"
    assert payload["observed"]["db_schema_version"] == "1.6.0"
    assert payload["observed"]["p1_metric_catalog_version"] == "P1-1.0"


def test_openapi_exposes_exact_m0_api_002_routes() -> None:
    schema = create_app(_application()).openapi()
    paths = schema["paths"]
    assert "/health" in paths
    assert "/readiness" in paths
    assert "/version" in paths
    assert set(paths["/health"]) == {"get"}
    assert set(paths["/readiness"]) == {"get"}
    assert set(paths["/version"]) == {"get"}
