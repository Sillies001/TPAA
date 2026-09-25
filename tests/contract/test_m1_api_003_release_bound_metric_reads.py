from __future__ import annotations

import importlib
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
        raise AssertionError("M1 API-003 contract must not call M0 storage baseline")


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
        headers={"Idempotency-Key": "api-003-release-bound"},
        json={
            "fixture_id": "BF_M1_NOMINAL_V1",
            "aircraft_model_id": str(uuid5(NAMESPACE_URL, "api-003-model")),
            "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "api-003-instance")),
            "subject_entity_id": str(uuid5(NAMESPACE_URL, "api-003-entity")),
            "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
            "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
            "expected_version_token": 0,
        },
    )
    assert response.status_code == 201
    return str(response.json()["release_id"])


def test_metric_list_detail_and_evidence_never_recompute_or_read_current_authority(
    monkeypatch,
) -> None:
    client = _client()
    release_id = _publish(client)

    publication_module = importlib.import_module("tpaa_application.m1_publication")

    def unexpected(*args, **kwargs):
        raise AssertionError("release-bound Metric read attempted current/recompute lookup")

    for name in (
        "resolve_evaluation_context",
        "build_metric_context",
        "compute_representative_metrics",
        "project_minimal_p1_world",
    ):
        monkeypatch.setattr(publication_module, name, unexpected)

    listed = client.get(f"/m1/releases/{release_id}/metrics")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert [item["metric_code"] for item in items] == [
        "P1-AIR-001",
        "P1-AIR-002",
        "P1-AIR-003",
        "P1-AIR-004",
        "P1-AIR-007",
    ]
    assert all(item["release_id"] == release_id for item in items)
    assert all(len(item["definition_hash"]) == 64 for item in items)

    detail = client.get(f"/m1/releases/{release_id}/metrics/P1-AIR-001")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["release_id"] == release_id
    assert detail_payload["metric_code"] == "P1-AIR-001"
    assert len(detail_payload["definition"]["definition_hash"]) == 64
    assert len(detail_payload["definition"]["catalog_hash"]) == 64
    assert detail_payload["definition"]["publication_route"] == "CAPABILITY_OBSERVATION"
    assert len(detail_payload["evidence"]["logical_hash"]) == 64

    evidence = client.get(
        f"/m1/releases/{release_id}/metrics/P1-AIR-001/evidence"
    )
    assert evidence.status_code == 200
    evidence_payload = evidence.json()
    assert evidence_payload["release_id"] == release_id
    assert evidence_payload["metric_code"] == "P1-AIR-001"
    assert evidence_payload["metric_instance_id"] == detail_payload["metric_instance_id"]
    assert (
        evidence_payload["metric_definition_id"]
        == detail_payload["definition"]["metric_definition_id"]
    )
    assert (
        evidence_payload["definition_hash"]
        == detail_payload["definition"]["definition_hash"]
    )
    assert (
        evidence_payload["evidence_set_id"]
        == detail_payload["evidence"]["evidence_set_id"]
    )
    assert evidence_payload["logical_hash"] == detail_payload["evidence"]["logical_hash"]


def test_metric_evidence_missing_metric_is_release_bound_not_found() -> None:
    client = _client()
    release_id = _publish(client)

    response = client.get(
        f"/m1/releases/{release_id}/metrics/P1-AIR-999/evidence"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "METRIC_NOT_FOUND"
