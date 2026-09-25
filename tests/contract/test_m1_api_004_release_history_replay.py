from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient

from tpaa_api import create_m1_app
from tpaa_application import ApplicationService, M1PublicationService
from tpaa_application.m1_repository import InMemorySessionPublicationRepository

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


class _UnusedStorageBaseline:
    def execute(self):
        raise AssertionError("M1 API-004 contract must not call M0 storage baseline")


def _client() -> TestClient:
    publication = M1PublicationService(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        repository=InMemorySessionPublicationRepository(),
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorageBaseline(),
        m1_publication=publication,
    )
    return TestClient(create_m1_app(application))


def _body(token: int, capability_type: str) -> dict[str, object]:
    return {
        "fixture_id": "BF_M1_NOMINAL_V1",
        "aircraft_model_id": str(uuid5(NAMESPACE_URL, "api-004-model")),
        "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "api-004-instance")),
        "subject_entity_id": str(uuid5(NAMESPACE_URL, "api-004-entity")),
        "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
        "capability_type": capability_type,
        "expected_version_token": token,
    }


def _publish(
    client: TestClient,
    *,
    token: int,
    key: str,
    capability_type: str,
) -> dict[str, object]:
    response = client.post(
        "/m1/commands/publish-session",
        headers={"Idempotency-Key": key},
        json=_body(token, capability_type),
    )
    assert response.status_code == 201
    return response.json()


def test_release_and_replay_expose_identity_provenance_and_status() -> None:
    client = _client()
    published = _publish(
        client,
        token=0,
        key="api-004-first",
        capability_type="TEST_CAPABILITY_A",
    )
    release_id = str(published["release_id"])

    release = client.get(f"/m1/releases/{release_id}")
    assert release.status_code == 200
    payload = release.json()

    assert payload["status"] == "PUBLISHED"
    assert payload["identity"] == {
        "release_id": release_id,
        "scope_type": "SESSION",
        "scope_key": payload["session_id"],
        "release_no": 1,
        "parent_release_id": None,
    }
    assert payload["provenance"] == {
        "fixture_id": payload["fixture_id"],
        "session_id": payload["session_id"],
        "context": {
            "context_id": payload["context_id"],
            "context_version": payload["context_version"],
            "context_binding_hash": payload["context_binding_hash"],
        },
        "catalog": {
            "catalog_version": payload["catalog_version"],
            "catalog_hash": payload["catalog_hash"],
        },
        "world": {
            "world_product_id": payload["world_product_id"],
            "world_logical_hash": payload["world_logical_hash"],
        },
        "request_hash": payload["request_hash"],
        "manifest_hash": payload["manifest_hash"],
    }

    replay = client.post(f"/m1/releases/{release_id}/replay")
    assert replay.status_code == 200
    replay_payload = replay.json()
    assert replay_payload["release_id"] == release_id
    assert replay_payload["release_status"] == "PUBLISHED"
    assert replay_payload["status"] == "PASS"
    assert replay_payload["provenance"] == payload["provenance"]
    assert replay_payload["exact_logical_products_equal"] is True
    assert replay_payload["current_latest_fallback_used"] is False


def test_historical_release_identity_and_provenance_survive_new_current_release() -> None:
    client = _client()
    first = _publish(
        client,
        token=0,
        key="api-004-history-first",
        capability_type="TEST_CAPABILITY_A",
    )
    first_id = str(first["release_id"])
    before = client.get(f"/m1/releases/{first_id}")
    assert before.status_code == 200
    before_payload = before.json()

    second = _publish(
        client,
        token=1,
        key="api-004-history-second",
        capability_type="TEST_CAPABILITY_B",
    )
    second_id = str(second["release_id"])
    assert second_id != first_id

    after = client.get(f"/m1/releases/{first_id}")
    assert after.status_code == 200
    after_payload = after.json()

    assert after_payload["identity"] == before_payload["identity"]
    assert after_payload["provenance"] == before_payload["provenance"]
    assert after_payload["status"] == "PUBLISHED"
    assert after_payload["version_token"] == before_payload["version_token"] == 1

    current = client.get(f"/m1/releases/{second_id}")
    assert current.status_code == 200
    assert current.json()["identity"]["parent_release_id"] == first_id
    assert current.json()["identity"]["release_no"] == 2
