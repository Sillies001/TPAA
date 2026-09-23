from __future__ import annotations

from fastapi.testclient import TestClient

from tpaa_api import create_app
from tpaa_application import ApplicationService, GetRuntimeBaselineStatus
from tpaa_canonical.runtime_handshake import (
    RuntimeBaselineIdentity,
    evaluate_runtime_baseline_handshake,
)


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage path is not used by M0 API job skeleton tests")


def _identity() -> RuntimeBaselineIdentity:
    return RuntimeBaselineIdentity(
        product_build_version="build-api-004",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="lock",
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="core",
        p1_metric_catalog_version="catalog",
        p1_metric_catalog_sha256="catalog-sha",
        dto_authority_sha256="dto",
    )


def _client() -> TestClient:
    identity = _identity()
    runtime = GetRuntimeBaselineStatus(
        lambda: evaluate_runtime_baseline_handshake(expected=identity, observed=identity)
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        get_runtime_baseline_status=runtime,
    )
    return TestClient(create_app(application))


def test_http_same_key_same_request_reuses_and_conflict_is_409() -> None:
    with _client() as client:
        first = client.post(
            "/jobs",
            headers={"Idempotency-Key": "abc", "X-TPAA-Actor": "test"},
            json={"command": "diagnostic", "payload": {"a": 1}},
        )
        second = client.post(
            "/jobs",
            headers={"Idempotency-Key": "abc", "X-TPAA-Actor": "test"},
            json={"command": "diagnostic", "payload": {"a": 1}},
        )
        conflict = client.post(
            "/jobs",
            headers={"Idempotency-Key": "abc", "X-TPAA-Actor": "test"},
            json={"command": "diagnostic", "payload": {"a": 2}},
        )

    assert first.status_code == 202
    assert first.json()["reused"] is False
    assert second.status_code == 200
    assert second.json()["reused"] is True
    assert second.json()["job_id"] == first.json()["job_id"]
    assert conflict.status_code == 409
    assert conflict.json()["outcome"] == "SYSTEM_ERROR"
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_job_query_cancel_and_not_found_mapping() -> None:
    with _client() as client:
        created = client.post(
            "/jobs",
            headers={"Idempotency-Key": "cancel-key"},
            json={"command": "diagnostic", "payload": {}},
        ).json()
        job_id = created["job_id"]
        queried = client.get(f"/jobs/{job_id}")
        cancelled = client.post(
            f"/jobs/{job_id}/cancel",
            json={"reason": "test cancellation"},
        )
        missing = client.get("/jobs/00000000-0000-0000-0000-000000000000")

    assert queried.status_code == 200
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert missing.status_code == 404
    assert missing.json()["outcome"] == "SYSTEM_ERROR"
    assert missing.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_idempotency_key_is_required() -> None:
    with _client() as client:
        response = client.post(
            "/jobs",
            json={"command": "diagnostic", "payload": {}},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
