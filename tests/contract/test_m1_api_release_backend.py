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
        raise AssertionError("M1 API contract must not call M0 storage baseline")


def _client() -> TestClient:
    m1 = M1PublicationService(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        repository=InMemorySessionPublicationRepository(),
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorageBaseline(),
        m1_publication=m1,
    )
    return TestClient(create_m1_app(application))


def _body(token: int = 0) -> dict[str, object]:
    return {
        "fixture_id": "BF_M1_NOMINAL_V1",
        "aircraft_model_id": str(uuid5(NAMESPACE_URL, "m1-api-model")),
        "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "m1-api-instance")),
        "subject_entity_id": str(uuid5(NAMESPACE_URL, "m1-api-entity")),
        "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
        "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
        "expected_version_token": token,
    }


def test_publish_and_release_bound_read_snapshot() -> None:
    client = _client()
    first = client.post(
        "/m1/commands/publish-session",
        json=_body(),
        headers={"Idempotency-Key": "api-publish"},
    )
    assert first.status_code == 201
    published = first.json()
    assert published["status"] == "PUBLISHED"
    assert published["reused"] is False
    assert len(published["request_hash"]) == 64
    release_id = published["release_id"]

    retry = client.post(
        "/m1/commands/publish-session",
        json=_body(),
        headers={"Idempotency-Key": "api-publish"},
    )
    assert retry.status_code == 200
    assert retry.json()["reused"] is True
    assert retry.json()["release_id"] == release_id

    release = client.get(f"/m1/releases/{release_id}")
    assert release.status_code == 200
    assert release.json()["release_id"] == release_id
    assert release.json()["status"] == "PUBLISHED"

    context = client.get(f"/m1/releases/{release_id}/context")
    assert context.status_code == 200
    assert context.json()["context_id"] == release.json()["context_id"]

    topology = client.get(f"/m1/releases/{release_id}/topology")
    assert topology.status_code == 200
    topo = topology.json()
    assert isinstance(topo["session"]["start_session_time_us"], str)
    assert isinstance(topo["session"]["end_session_time_us"], str)
    assert all(isinstance(item["start_session_time_us"], str) for item in topo["stages"])

    metrics = client.get(f"/m1/releases/{release_id}/metrics")
    assert metrics.status_code == 200
    assert [item["metric_code"] for item in metrics.json()["items"]] == [
        "P1-AIR-001",
        "P1-AIR-002",
        "P1-AIR-003",
        "P1-AIR-004",
        "P1-AIR-007",
    ]

    structured = client.get(f"/m1/releases/{release_id}/metrics/P1-AIR-007")
    assert structured.status_code == 200
    structured_payload = structured.json()
    assert structured_payload["value_kind"] == "STRUCTURED"
    assert isinstance(structured_payload["value"], dict)
    assert structured_payload["definition"]["publication_route"] == "CAPABILITY_OBSERVATION"

    observations = client.get(f"/m1/releases/{release_id}/observations")
    assert observations.status_code == 200
    observation_items = observations.json()["items"]
    assert len(observation_items) == 5
    assert all(
        isinstance(item["observation_start_session_time_us"], str)
        for item in observation_items
    )

    replay = client.post(f"/m1/releases/{release_id}/replay")
    assert replay.status_code == 200
    assert replay.json()["status"] == "PASS"
    assert replay.json()["current_latest_fallback_used"] is False

    start = topo["session"]["start_session_time_us"]
    end = topo["session"]["end_session_time_us"]
    series = client.get(
        f"/m1/releases/{release_id}/series",
        params={
            "start_session_time_us": start,
            "end_session_time_us": end,
            "limit": 2,
        },
    )
    assert series.status_code == 200
    assert series.json()["returned"] <= 2


def test_publish_requires_idempotency_key() -> None:
    response = _client().post("/m1/commands/publish-session", json=_body())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"



def test_import_and_compute_commands_are_idempotent_and_request_hashed() -> None:
    client = _client()
    for route, key, command in (
        ("/m1/commands/import-session", "api-import", "M1_IMPORT_SESSION"),
        ("/m1/commands/compute-session", "api-compute", "M1_COMPUTE_SESSION"),
    ):
        body = {"fixture_id": "BF_M1_NOMINAL_V1"}
        first = client.post(route, json=body, headers={"Idempotency-Key": key})
        assert first.status_code == 202
        first_payload = first.json()
        assert first_payload["command"] == command
        assert first_payload["reused"] is False
        assert len(first_payload["request_hash"]) == 64

        retry = client.post(route, json=body, headers={"Idempotency-Key": key})
        assert retry.status_code == 200
        assert retry.json()["reused"] is True
        assert retry.json()["job_id"] == first_payload["job_id"]
        assert retry.json()["request_hash"] == first_payload["request_hash"]

        conflict = client.post(
            route,
            json={"fixture_id": "BF_M1_REPLAY_V1"},
            headers={"Idempotency-Key": key},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_all_m1_commands_require_idempotency_key() -> None:
    client = _client()
    for route in (
        "/m1/commands/import-session",
        "/m1/commands/compute-session",
        "/m1/commands/publish-session",
    ):
        response = client.post(route, json=_body())
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_import_and_compute_commands_are_idempotent_and_hash_bound() -> None:
    client = _client()

    imported = client.post(
        "/m1/commands/import-session",
        json={"fixture_id": "BF_M1_NOMINAL_V1"},
        headers={"Idempotency-Key": "api-import"},
    )
    assert imported.status_code == 200
    import_payload = imported.json()
    assert len(import_payload["request_hash"]) == 64
    assert import_payload["status"] == "VALIDATED"
    assert import_payload["reused"] is False

    import_retry = client.post(
        "/m1/commands/import-session",
        json={"fixture_id": "BF_M1_NOMINAL_V1"},
        headers={"Idempotency-Key": "api-import"},
    )
    assert import_retry.status_code == 200
    assert import_retry.json()["request_hash"] == import_payload["request_hash"]
    assert import_retry.json()["reused"] is True

    computed = client.post(
        "/m1/commands/compute-session",
        json={"fixture_id": "BF_M1_NOMINAL_V1"},
        headers={"Idempotency-Key": "api-compute"},
    )
    assert computed.status_code == 200
    compute_payload = computed.json()
    assert len(compute_payload["request_hash"]) == 64
    assert len(compute_payload["world_logical_hash"]) == 64
    assert len(compute_payload["metric_batch_hash"]) == 64
    assert len(compute_payload["metric_results"]) == 5
    assert compute_payload["database_persistence_executed"] is False
    assert compute_payload["publication_executed"] is False
    assert compute_payload["reused"] is False

    compute_retry = client.post(
        "/m1/commands/compute-session",
        json={"fixture_id": "BF_M1_NOMINAL_V1"},
        headers={"Idempotency-Key": "api-compute"},
    )
    assert compute_retry.status_code == 200
    assert compute_retry.json()["metric_batch_hash"] == compute_payload["metric_batch_hash"]
    assert compute_retry.json()["reused"] is True
