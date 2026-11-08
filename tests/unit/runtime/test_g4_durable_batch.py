from __future__ import annotations

from pathlib import Path

from tpaa_application import (
    BatchImportService,
    ForceFormationMember,
    SourceWorkflowService,
)
from tpaa_runtime.durable_batch import DurableBatchRepository
from tpaa_storage import LocalObjectStore, SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.9.0" / "canonical"
SESSION_ID = "d4200000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "d4200000-0000-4000-8000-000000000002"
CONTEXT_ID = "d4200000-0000-4000-8000-000000000003"


def _csv() -> bytes:
    return (
        b"source_time_us,session_time_us,p_deg_s,nz_g,heading_deg_true,"
        b"tas_kt,mach,quality_mask\n"
        b"0,0,0,1.0,0,200,0.60,0\n"
        b"100000,100000,5,1.1,10,201,0.61,0\n"
    )


def test_db_1_10_batch_and_context_are_durable_and_audited(tmp_path: Path) -> None:
    database = tmp_path / "g4.sqlite3"
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
                "session_code": "G4-DURABLE-001",
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

    service = BatchImportService(
        DurableBatchRepository(read, write),
        SourceWorkflowService(LocalObjectStore(tmp_path / "objects")),
    )
    ticket = service.issue_ticket(kind="FILE", name="flight.csv", data=_csv())
    batch = service.register_batch(
        idempotency_key="durable-001",
        actor="durable-reviewer",
        ticket_id=str(ticket["ticket_id"]),
        session_id=SESSION_ID,
        aircraft_id=AIRCRAFT_ID,
        batch_date="2026-11-06",
        batch_training_type="SIMPLE_OPPOSITION",
        training_type_confirmed=True,
        producer_system="RECORDER_EXPORT",
        session_code="G4-DURABLE-001",
        session_type="LIVE",
        context_id=CONTEXT_ID,
    )
    assert batch["qualification_status"] == "QUALIFIED"
    assert service.get_batch(str(batch["batch_id"]))["revision_no"] == 1

    revised = service.revise_training_type(
        str(batch["batch_id"]),
        training_type="MIXED_OPPOSITION",
        actor="durable-reviewer",
        reason="reviewed change",
    )
    assert revised["revision_no"] == 2

    context = service.revise_context(
        CONTEXT_ID,
        valid_from_session_time_us=0,
        valid_to_session_time_us=1_000_000,
        source="MANUAL_REVIEWED",
        reason="reviewed formation",
        actor="durable-reviewer",
        members=(
            ForceFormationMember(
                aircraft_id=AIRCRAFT_ID,
                formation_id="BLUE-1",
                side="BLUE",
                member_role="LEAD",
                independent_target=False,
            ),
        ),
    )
    assert context["revision_no"] == 1

    with read() as uow:
        audit = uow.audit_log.rows()
    assert [item.action for item in audit] == [
        "G4_BATCH_REGISTER",
        "G4_BATCH_QUALIFICATION_TRANSITION",
        "G4_BATCH_TRAINING_TYPE_REVISE",
        "G4_FORCE_FORMATION_CONTEXT_REVISE",
    ]
    assert all(item.principal_key == "durable-reviewer" for item in audit)
