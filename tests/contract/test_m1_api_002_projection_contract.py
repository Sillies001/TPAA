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
        raise AssertionError("M1 API projection contract must not call M0 storage baseline")


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


def _publish(client: TestClient) -> str:
    response = client.post(
        "/m1/commands/publish-session",
        headers={"Idempotency-Key": "api-002-projection"},
        json={
            "fixture_id": "BF_M1_NOMINAL_V1",
            "aircraft_model_id": str(uuid5(NAMESPACE_URL, "api-002-model")),
            "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "api-002-instance")),
            "subject_entity_id": str(uuid5(NAMESPACE_URL, "api-002-entity")),
            "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
            "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
            "expected_version_token": 0,
        },
    )
    assert response.status_code == 201
    return str(response.json()["release_id"])


def test_context_query_is_generated_evaluation_context_dto_projection() -> None:
    client = _client()
    release_id = _publish(client)

    response = client.get(f"/m1/releases/{release_id}/context")
    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {
        "context_id",
        "session_id",
        "context_version",
        "revision_no",
        "rule_set_version",
        "metric_profile_version",
        "status",
    }
    assert isinstance(payload["context_id"], str)
    assert isinstance(payload["session_id"], str)
    assert isinstance(payload["context_version"], str)
    assert isinstance(payload["revision_no"], int)
    assert isinstance(payload["rule_set_version"], str)
    assert isinstance(payload["metric_profile_version"], str)
    assert isinstance(payload["status"], str)


def test_session_episode_stage_query_is_explicit_json_projection_only() -> None:
    client = _client()
    release_id = _publish(client)

    response = client.get(f"/m1/releases/{release_id}/topology")
    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {"release_id", "session", "episode", "stages"}
    assert payload["release_id"] == release_id

    assert set(payload["session"]) == {
        "session_id",
        "start_session_time_us",
        "end_session_time_us",
    }
    assert isinstance(payload["session"]["start_session_time_us"], str)
    assert isinstance(payload["session"]["end_session_time_us"], str)

    assert set(payload["episode"]) == {"episode_id", "session_id"}
    assert payload["episode"]["session_id"] == payload["session"]["session_id"]

    assert len(payload["stages"]) == 4
    expected_stage_keys = {
        "stage_id",
        "episode_id",
        "stage_type",
        "stage_order",
        "start_session_time_us",
        "end_session_time_us",
        "stage_status",
        "coverage",
        "confidence",
        "detector_version",
    }
    for stage in payload["stages"]:
        assert set(stage) == expected_stage_keys
        assert stage["episode_id"] == payload["episode"]["episode_id"]
        assert isinstance(stage["start_session_time_us"], str)
        assert isinstance(stage["end_session_time_us"], str)
        assert "canonical_rows" not in stage
        assert "evidence_refs" not in stage

    assert "canonical_rows" not in payload
    assert "world_product_id" not in payload
    assert "evidence_refs" not in payload
