from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tpaa_api.gui_batch import register_gui_batch_routes
from tpaa_api.unified import UnifiedPrincipal
from tpaa_application import (
    ApplicationService,
    BatchImportService,
    SourceWorkflowService,
    StorageBaselineStatus,
)
from tpaa_runtime.durable_batch import DurableBatchRepository
from tpaa_storage import LocalObjectStore, SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.9.0" / "canonical"
SESSION_ID = "d4300000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "d4300000-0000-4000-8000-000000000002"
CONTEXT_ID = "d4300000-0000-4000-8000-000000000003"


class _Status:
    def execute(self) -> StorageBaselineStatus:
        return StorageBaselineStatus(
            engine_profile="SQLITE_DESKTOP",
            schema_version="1.10.0",
            core_baseline="CB-1.6.0",
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
    database = tmp_path / "g4-api.sqlite3"
    bootstrap_sqlite(database, authority_root=AUTHORITY)

    def read() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, authority_root=AUTHORITY)

    def write() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, write=True, authority_root=AUTHORITY)

    with write() as uow:
        uow.canonical_rows.insert(
            "registry.training_session",
            {
                "session_id": SESSION_ID,
                "session_code": "G4-API-001",
                "session_type": "LIVE",
                "start_session_time_us": 0,
                "end_session_time_us": 1_000_000,
                "training_type_set": (),
                "data_status": "IMPORTED",
                "source_count": 1,
                "schema_version": "1.10.0",
            },
            field_kinds={"training_type_set": "text_array"},
        )
        uow.commit()
    source = SourceWorkflowService(LocalObjectStore(tmp_path / "objects"))
    application = ApplicationService(
        get_storage_baseline_status=_Status(),
        source_workflow=source,
        batch_import=BatchImportService(DurableBatchRepository(read, write), source),
    )
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.tpaa_principal = UnifiedPrincipal(
            role="ADMIN_AUDITOR",
            actor_id=None,
            scope_match=True,
            security_roles=("ADMINISTRATOR",),
            resource_scopes=("*",),
        )
        return await call_next(request)

    register_gui_batch_routes(app, application)
    return TestClient(app)


def test_v23_ticket_registration_v01_list_and_context_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ticket_response = client.post(
        "/api/v1/gui/import-tickets",
        content=_csv(),
        headers={
            "X-TPAA-Ticket-Kind": "FILE",
            "X-TPAA-Display-Name": "flight.csv",
            "Content-Type": "text/csv",
        },
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    assert ticket["local_path"] is None

    registered = client.post(
        "/api/v1/gui/batches",
        headers={"Idempotency-Key": "g4-api-register-001"},
        json={
            "ticket_id": ticket["ticket_id"],
            "session_id": SESSION_ID,
            "aircraft_id": AIRCRAFT_ID,
            "batch_date": "2026-11-06",
            "batch_training_type": "SIMPLE_OPPOSITION",
            "training_type_confirmed": True,
            "producer_system": "RECORDER_EXPORT",
            "session_code": "G4-API-001",
            "session_type": "LIVE",
            "context_id": CONTEXT_ID,
        },
    )
    assert registered.status_code == 201
    batch = registered.json()
    assert batch["qualification_status"] == "QUALIFIED"

    listing = client.get("/api/v1/gui/batches")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["batch_id"] == batch["batch_id"]
    assert client.get(f"/api/v1/gui/batches/{batch['batch_id']}").status_code == 200

    context = client.post(
        f"/api/v1/gui/contexts/{CONTEXT_ID}/force-formation-revisions",
        json={
            "valid_from_session_time_us": 0,
            "valid_to_session_time_us": 1_000_000,
            "source": "MANUAL_REVIEWED",
            "reason": "API reviewed context",
            "members": [
                {
                    "aircraft_id": AIRCRAFT_ID,
                    "formation_id": "BLUE-1",
                    "side": "BLUE",
                    "member_role": "LEAD",
                    "independent_target": False,
                }
            ],
        },
    )
    assert context.status_code == 201
    assert client.get(f"/api/v1/gui/contexts/{CONTEXT_ID}/force-formation").json() == context.json()


def test_registration_rejects_implicit_training_type_default(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ticket = client.post(
        "/api/v1/gui/import-tickets",
        content=_csv(),
        headers={"X-TPAA-Ticket-Kind": "FILE", "X-TPAA-Display-Name": "flight.csv"},
    ).json()
    response = client.post(
        "/api/v1/gui/batches",
        headers={"Idempotency-Key": "g4-api-invalid-default"},
        json={
            "ticket_id": ticket["ticket_id"],
            "session_id": SESSION_ID,
            "aircraft_id": AIRCRAFT_ID,
            "batch_date": "2026-11-06",
            "batch_training_type": "COMPREHENSIVE_OPPOSITION",
            "training_type_confirmed": False,
            "producer_system": "RECORDER_EXPORT",
            "session_code": "G4-API-001",
            "session_type": "LIVE",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "G4_TRAINING_TYPE_CONFIRMATION_REQUIRED"
