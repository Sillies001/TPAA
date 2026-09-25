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
        raise AssertionError("M1 API-005 contract must not call M0 storage baseline")


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
        headers={"Idempotency-Key": "api-005-range"},
        json={
            "fixture_id": "BF_M1_NOMINAL_V1",
            "aircraft_model_id": str(uuid5(NAMESPACE_URL, "api-005-model")),
            "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "api-005-instance")),
            "subject_entity_id": str(uuid5(NAMESPACE_URL, "api-005-entity")),
            "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
            "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
            "expected_version_token": 0,
        },
    )
    assert response.status_code == 201
    return str(response.json()["release_id"])


def test_series_query_requires_explicit_bounded_range_and_limit() -> None:
    client = _client()
    release_id = _publish(client)

    topology = client.get(f"/m1/releases/{release_id}/topology")
    assert topology.status_code == 200
    session = topology.json()["session"]
    start = int(session["start_session_time_us"])
    end = int(session["end_session_time_us"])

    missing_range = client.get(f"/m1/releases/{release_id}/series")
    assert missing_range.status_code == 422

    invalid_range = client.get(
        f"/m1/releases/{release_id}/series",
        params={
            "start_session_time_us": end,
            "end_session_time_us": start,
            "limit": 1,
        },
    )
    assert invalid_range.status_code == 422
    assert invalid_range.json()["error"]["code"] == "SERIES_RANGE_INVALID"

    oversized = client.get(
        f"/m1/releases/{release_id}/series",
        params={
            "start_session_time_us": start,
            "end_session_time_us": end,
            "limit": 5001,
        },
    )
    assert oversized.status_code == 422

    bounded = client.get(
        f"/m1/releases/{release_id}/series",
        params={
            "start_session_time_us": start,
            "end_session_time_us": end,
            "limit": 2,
        },
    )
    assert bounded.status_code == 200
    payload = bounded.json()
    assert payload["release_id"] == release_id
    assert payload["start_session_time_us"] == str(start)
    assert payload["end_session_time_us"] == str(end)
    assert payload["limit"] == 2
    assert payload["returned"] <= 2
    assert len(payload["rows"]) == payload["returned"]
    for row in payload["rows"]:
        session_time_us = int(row["session_time_us"])
        assert start <= session_time_us < end


def test_high_frequency_series_is_not_embedded_in_release_or_metric_json() -> None:
    client = _client()
    release_id = _publish(client)

    release = client.get(f"/m1/releases/{release_id}")
    metric = client.get(f"/m1/releases/{release_id}/metrics/P1-AIR-001")
    assert release.status_code == 200
    assert metric.status_code == 200

    for payload in (release.json(), metric.json()):
        assert "rows" not in payload
        assert "series" not in payload
        assert "canonical_rows" not in payload
