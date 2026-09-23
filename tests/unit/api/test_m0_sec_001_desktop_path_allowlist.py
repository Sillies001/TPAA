from __future__ import annotations

from fastapi.testclient import TestClient

from tpaa_api import create_desktop_app
from tpaa_application import ApplicationService, GetRuntimeBaselineStatus
from tpaa_canonical.runtime_handshake import (
    RuntimeBaselineIdentity,
    evaluate_runtime_baseline_handshake,
)


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError


def _app():
    identity = RuntimeBaselineIdentity(
        product_build_version="sec-smoke",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="lock",
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="core",
        p1_metric_catalog_version="catalog",
        p1_metric_catalog_sha256="catalog-sha",
        dto_authority_sha256="dto",
    )
    runtime = GetRuntimeBaselineStatus(
        lambda: evaluate_runtime_baseline_handshake(expected=identity, observed=identity)
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        get_runtime_baseline_status=runtime,
    )
    return create_desktop_app(application=application, bearer_token="test-token")


def test_desktop_http_is_bearer_origin_and_path_allowlisted() -> None:
    with TestClient(_app()) as client:
        unauthorized = client.get("/health")
        allowed = client.get("/health", headers={"Authorization": "Bearer test-token"})
        origin = client.get(
            "/health",
            headers={"Authorization": "Bearer test-token", "Origin": "https://example.invalid"},
        )
        path = client.get(
            "/jobs",
            headers={"Authorization": "Bearer test-token"},
        )

    assert unauthorized.status_code == 401
    assert allowed.status_code == 200
    assert origin.status_code == 403
    assert origin.json() == {"detail": "ORIGIN_FORBIDDEN"}
    assert path.status_code == 404
    assert path.json() == {"detail": "PATH_NOT_ALLOWED"}


def test_missing_desktop_security_token_fails_closed() -> None:
    identity = RuntimeBaselineIdentity(
        product_build_version="sec-smoke",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="lock",
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="core",
        p1_metric_catalog_version="catalog",
        p1_metric_catalog_sha256="catalog-sha",
        dto_authority_sha256="dto",
    )
    runtime = GetRuntimeBaselineStatus(
        lambda: evaluate_runtime_baseline_handshake(expected=identity, observed=identity)
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        get_runtime_baseline_status=runtime,
    )
    try:
        create_desktop_app(application=application, bearer_token="")
    except ValueError as exc:
        assert "bearer_token" in str(exc)
    else:
        raise AssertionError("missing Desktop bearer token was accepted")
