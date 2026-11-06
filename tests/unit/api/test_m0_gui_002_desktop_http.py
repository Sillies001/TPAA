from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from tpaa_api import create_desktop_app
from tpaa_application import ApplicationService, GetRuntimeBaselineStatus
from tpaa_canonical import RuntimeBaselineIdentity, evaluate_runtime_baseline_handshake


class _UnusedStorageUseCase:
    def execute(self) -> object:
        raise AssertionError("storage use case must not be called")


def _identity() -> RuntimeBaselineIdentity:
    return RuntimeBaselineIdentity(
        product_build_version="0.0.0",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="lock",
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="core",
        p1_metric_catalog_version="1.14.0",
        p1_metric_catalog_sha256="catalog",
        dto_authority_sha256="dto",
    )


def _application(*, ready: bool = True) -> ApplicationService:
    expected = _identity()
    observed = expected if ready else replace(expected, db_schema_version="mismatch")
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorageUseCase(),  # type: ignore[arg-type]
        get_runtime_baseline_status=GetRuntimeBaselineStatus(
            lambda: evaluate_runtime_baseline_handshake(expected=expected, observed=observed)
        ),
    )


def test_desktop_http_requires_exact_bearer_on_every_route() -> None:
    with TestClient(create_desktop_app(application=_application(), bearer_token="secret")) as client:
        assert client.get("/health").status_code == 401
        assert client.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/health", headers={"Authorization": "Bearer secret"}).json() == {"status": "UP"}
        assert client.get("/readiness", headers={"Authorization": "Bearer secret"}).status_code == 200
        assert client.get("/version", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_desktop_http_rejects_origin_and_disables_docs_openapi() -> None:
    headers = {"Authorization": "Bearer secret"}
    with TestClient(create_desktop_app(application=_application(), bearer_token="secret")) as client:
        assert client.get("/health", headers={**headers, "Origin": "http://example.test"}).status_code == 403
        assert client.get("/docs", headers=headers).status_code == 404
        assert client.get("/redoc", headers=headers).status_code == 404
        assert client.get("/openapi.json", headers=headers).status_code == 404


def test_desktop_readiness_preserves_core_fail_closed_mismatch() -> None:
    headers = {"Authorization": "Bearer secret"}
    with TestClient(create_desktop_app(application=_application(ready=False), bearer_token="secret")) as client:
        response = client.get("/readiness", headers=headers)
    assert response.status_code == 503
    assert response.json()["ready"] is False
    assert response.json()["mismatches"] == ["DB_SCHEMA_VERSION_MISMATCH"]


def test_v33_webengine_origin_nonce_and_static_asset_gate(tmp_path: Path) -> None:
    assets = tmp_path / "dist"
    assets.mkdir()
    (assets / "index.html").write_text("<main>v33</main>", encoding="utf-8")
    app = create_desktop_app(
        application=_application(),
        bearer_token="secret",
        desktop_nonce="nonce",
        web_asset_root=assets,
    )
    authorization = {"Authorization": "Bearer secret"}
    browser = {
        **authorization,
        "Origin": "http://127.0.0.1:8765",
        "X-TPAA-Desktop-Nonce": "nonce",
    }
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        index = client.get("/ui", headers=authorization)
        allowed = client.get("/health", headers=browser)
        missing_nonce = client.get(
            "/health",
            headers={**authorization, "Origin": "http://127.0.0.1:8765"},
        )
        foreign_origin = client.get(
            "/health",
            headers={**browser, "Origin": "http://127.0.0.1:8766"},
        )

    assert index.status_code == 200
    assert index.headers["content-security-policy"].startswith("default-src 'self'")
    assert allowed.status_code == 200
    assert missing_nonce.status_code == 403
    assert foreign_origin.status_code == 403
