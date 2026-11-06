from __future__ import annotations

from pathlib import Path

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


def _application() -> ApplicationService:
    identity = RuntimeBaselineIdentity(
        product_build_version="g2-v33-guard-test",
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
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        get_runtime_baseline_status=runtime,
    )


def _client(asset_root: Path) -> TestClient:
    (asset_root / "index.html").write_text("<!doctype html><title>TPAA</title>", encoding="utf-8")
    return TestClient(
        create_desktop_app(
            application=_application(),
            bearer_token="g2-test-token",
            desktop_nonce="g2-test-nonce",
            web_asset_root=asset_root,
        )
    )


def test_desktop_server_rejects_direct_v24_path_and_query(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        headers = {"Authorization": "Bearer g2-test-token"}
        allowed = client.get("/ui?view=V08", headers=headers)
        denied_query = client.get("/ui?view=V24", headers=headers)
        denied_alias = client.get("/ui?route=V24", headers=headers)
        denied_path = client.get("/ui/views/V24", headers=headers)
    assert allowed.status_code == 200
    assert denied_query.status_code == 403
    assert denied_alias.status_code == 403
    assert denied_path.status_code == 403
    assert denied_query.json() == {"detail": "V24_REQUIRES_V08_CONTEXT"}


def test_direct_v24_guard_does_not_bypass_desktop_bearer_auth(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/ui?view=V24")
    assert response.status_code == 401
