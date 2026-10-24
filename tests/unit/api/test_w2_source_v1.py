from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tpaa_api.source_v1 import register_source_v1_routes
from tpaa_application import ApplicationService, SourceWorkflowService, StorageBaselineStatus
from tpaa_storage import LocalObjectStore

SESSION_ID = "d2100000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "d2100000-0000-4000-8000-000000000002"


class _StorageStatus:
    def execute(self) -> StorageBaselineStatus:
        return StorageBaselineStatus(
            engine_profile="SQLITE_DESKTOP",
            schema_version="1.9.0",
            core_baseline="CB-1.5.0",
            authority_artifact_id="CORE_LOGICAL_MODEL",
            authority_sha256="a" * 64,
            baseline_lock_sha256="b" * 64,
            physical_schema_sha256="c" * 64,
        )


def _csv() -> bytes:
    return (
        b"source_time_us,session_time_us,p_deg_s,nz_g,heading_deg_true,"
        b"tas_kt,mach,quality_mask\n"
        b"0,0,0,1.0,0,200,0.60,0\n"
        b"100000,100000,5,1.1,10,201,0.61,0\n"
    )


def _client(tmp_path: Path) -> TestClient:
    application = ApplicationService(
        get_storage_baseline_status=_StorageStatus(),
        source_workflow=SourceWorkflowService(LocalObjectStore(tmp_path / "objects")),
    )
    return TestClient(register_source_v1_routes(FastAPI(), application))


def test_source_inspect_and_stage_transport(tmp_path: Path) -> None:
    client = _client(tmp_path)
    inventory = client.get("/api/v1/sources/adapters")
    assert inventory.status_code == 200
    assert any(
        item["adapter_id"] == "tpaa-flight-recorder-csv"
        for item in inventory.json()["items"]
    )

    inspect = client.post(
        "/api/v1/sources/flight-csv/inspect",
        params={
            "session_id": SESSION_ID,
            "aircraft_id": AIRCRAFT_ID,
            "source_ref": "file:///review/input.csv",
        },
        content=_csv(),
        headers={"content-type": "text/csv"},
    )
    assert inspect.status_code == 200
    assert inspect.json()["inspection"]["row_count"] == 2

    staged = client.post(
        "/api/v1/sources/flight-csv/stage",
        params={
            "session_id": SESSION_ID,
            "aircraft_id": AIRCRAFT_ID,
            "source_ref": "file:///review/input.csv",
            "raw_artifact_id": "d2100000-0000-4000-8000-000000000003",
            "canonical_artifact_id": "d2100000-0000-4000-8000-000000000004",
            "source_id": "d2100000-0000-4000-8000-000000000005",
            "source_stream_id": "d2100000-0000-4000-8000-000000000006",
            "producer_system": "RECORDER_EXPORT",
            "session_code": "W2-TRANSPORT-001",
            "session_type": "LIVE",
            "classification_label": "UNCLASSIFIED",
            "nominal_rate_hz": 10.0,
        },
        content=_csv(),
        headers={"content-type": "text/csv"},
    )
    assert staged.status_code == 201
    assert staged.json()["source_document"]["source_import"]["uri_kind"] == "MANAGED"


def test_source_transport_rejects_invalid_input(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/v1/sources/flight-csv/inspect",
        params={
            "session_id": SESSION_ID,
            "aircraft_id": AIRCRAFT_ID,
            "source_ref": "file:///review/input.csv",
        },
        content=b"wrong,header\n1,2\n",
        headers={"content-type": "text/csv"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "W2_FLIGHT_CSV_SCHEMA_UNSUPPORTED"


def test_w5_p1_request_manifest_stages_inline_sources_for_real_job(tmp_path: Path) -> None:
    artifact_id = "d2100000-0000-4000-8000-000000000007"
    manifest = {
        "schema": "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1",
        "source_documents": [
            {
                "source_import": {
                    "artifact_id": artifact_id,
                    "source_family": "FLIGHT",
                    "uri_kind": "EXTERNAL_FILE",
                    "source_ref": "file:///review/flight.json",
                },
                "source_json": '{"schema":"TPAA_PRODUCTION_FLIGHT_SOURCE_V1"}',
            }
        ],
    }
    response = _client(tmp_path).post(
        "/api/v1/sources/p1-request/stage",
        content=json.dumps(manifest).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "STAGED"
    assert result["source_families"] == ["FLIGHT"]
    document = result["payload"]["source_documents"][0]
    assert "source_json" not in document
    assert document["source_import"]["uri_kind"] == "MANAGED"
    assert document["source_artifact"]["logical_uri"].endswith(
        f"/{artifact_id}/source.json"
    )


def test_w5_p1_request_manifest_rejects_schema_drift(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/v1/sources/p1-request/stage",
        content=b'{"schema":"DRIFTED","source_documents":[]}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "W5_P1_MANIFEST_SCHEMA_INVALID"
