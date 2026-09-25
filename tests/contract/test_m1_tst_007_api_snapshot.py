from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient

from tpaa_api import create_m1_app
from tpaa_application import ApplicationService, M1PublicationService
from tpaa_application.m1_repository import InMemorySessionPublicationRepository

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
DECIMAL_STRING = re.compile(r"^-?[0-9]+$")


class _UnusedStorageBaseline:
    def execute(self):
        raise AssertionError("M1 TST-007 contract must not call M0 storage baseline")


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
        headers={"Idempotency-Key": "tst-007-snapshot"},
        json={
            "fixture_id": "BF_M1_NOMINAL_V1",
            "aircraft_model_id": str(uuid5(NAMESPACE_URL, "tst-007-model")),
            "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "tst-007-instance")),
            "subject_entity_id": str(uuid5(NAMESPACE_URL, "tst-007-entity")),
            "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
            "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
            "expected_version_token": 0,
        },
    )
    assert response.status_code == 201
    return str(response.json()["release_id"])


def _authority_json(name: str) -> dict[str, object]:
    raw = json.loads((AUTHORITY / name).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def test_generated_dto_time_and_air_007_structured_snapshots_are_exact() -> None:
    dto_authority = _authority_json("CROSS_LAYER_DTO_CONTRACTS.json")
    catalog = _authority_json("P1_METRIC_CATALOG.json")

    client = _client()
    release_id = _publish(client)

    context_response = client.get(f"/m1/releases/{release_id}/context")
    assert context_response.status_code == 200
    context = context_response.json()

    contracts = dto_authority["contracts"]
    assert isinstance(contracts, dict)
    context_contract = contracts["EvaluationContextDTO"]
    assert isinstance(context_contract, dict)
    context_fields = context_contract["fields"]
    assert isinstance(context_fields, list)
    expected_context_fields = {
        item["field"]
        for item in context_fields
        if isinstance(item, dict) and item.get("required") is True
    }
    assert set(context) == expected_context_fields

    observations_response = client.get(f"/m1/releases/{release_id}/observations")
    assert observations_response.status_code == 200
    observations = observations_response.json()["items"]
    air_007 = next(item for item in observations if item["metric_code"] == "P1-AIR-007")

    observation_contract = contracts["CapabilityObservationDTO"]
    assert isinstance(observation_contract, dict)
    observation_fields = observation_contract["fields"]
    assert isinstance(observation_fields, list)
    required_observation_fields = {
        item["field"]
        for item in observation_fields
        if isinstance(item, dict) and item.get("required") is True
    }
    allowed_observation_fields = {
        item["field"] for item in observation_fields if isinstance(item, dict)
    }
    expected_air_007_fields = required_observation_fields | {
        "structured_output_schema_id",
        "value",
    }
    assert set(air_007) == expected_air_007_fields
    assert set(air_007) <= allowed_observation_fields
    assert air_007["structured_output_schema_id"] == "STRUCT_P1_AIR_007_V1"

    for field in (
        "observation_start_session_time_us",
        "observation_end_session_time_us",
    ):
        assert isinstance(air_007[field], str)
        assert DECIMAL_STRING.fullmatch(air_007[field])

    registry = catalog["structured_output_schema_registry"]
    assert isinstance(registry, dict)
    schema_entry = registry["STRUCT_P1_AIR_007_V1"]
    assert isinstance(schema_entry, dict)
    schema = schema_entry["json_schema"]
    assert isinstance(schema, dict)
    value = air_007["value"]
    assert isinstance(value, dict)
    assert set(value) == set(schema["required"])
    assert schema["additionalProperties"] is False

    properties = schema["properties"]
    assert isinstance(properties, dict)
    for subrecord_name in ("tas", "mach"):
        subrecord = value[subrecord_name]
        sub_schema = properties[subrecord_name]
        assert isinstance(subrecord, dict)
        assert isinstance(sub_schema, dict)
        assert set(subrecord) == set(sub_schema["required"])
        assert sub_schema["additionalProperties"] is False
        assert subrecord["status"] in {"VALID", "INSUFFICIENT_DATA"}
        assert isinstance(subrecord["n"], int)
        assert subrecord["n"] >= 0

    assert set(value["tas"]) == {
        "status",
        "n",
        "min_mps",
        "max_mps",
        "p05_mps",
        "p50_mps",
        "p95_mps",
    }
    assert set(value["mach"]) == {
        "status",
        "n",
        "min",
        "max",
        "p05",
        "p50",
        "p95",
    }
