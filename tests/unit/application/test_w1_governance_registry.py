from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tpaa_application import (
    ConfigurationRecord,
    GovernanceRegistryError,
    GovernanceRegistryService,
)
from tpaa_storage import LocalObjectStore, SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.5.0" / "canonical"
MODEL = "b1000000-0000-4000-8000-000000000001"
AIRCRAFT = "b1000000-0000-4000-8000-000000000002"
SESSION = "b1000000-0000-4000-8000-000000000003"
CONFIGURATION = "b1000000-0000-4000-8000-000000000004"
SOURCE = "b1000000-0000-4000-8000-000000000005"


def _seed(database: Path) -> None:
    bootstrap_sqlite(database, authority_root=AUTHORITY)
    with sqlite3.connect(database) as connection:
        connection.execute(
            '''INSERT INTO "master.aircraft_model" (
                   aircraft_model_id, type_code, model_name
               ) VALUES (?, 'W1', 'W1 qualification model')''',
            (MODEL,),
        )
        connection.execute(
            '''INSERT INTO "master.aircraft" (
                   aircraft_id, aircraft_model_id, internal_code, master_data_status
               ) VALUES (?, ?, 'W1-001', 'ACTIVE')''',
            (AIRCRAFT, MODEL),
        )
        connection.execute(
            '''INSERT INTO "registry.training_session" (
                   session_id, session_code, session_type,
                   start_session_time_us, end_session_time_us,
                   training_type_set, data_status, source_count, schema_version
               ) VALUES (?, 'W1-SESSION', 'SIM', 0, 1000000, '[]', 'READY', 1, '1.9.0')''',
            (SESSION,),
        )
        connection.commit()


def _service(database: Path, objects: Path) -> GovernanceRegistryService:
    def read_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, authority_root=AUTHORITY)

    def write_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, write=True, authority_root=AUTHORITY)

    return GovernanceRegistryService(
        read_uow,
        write_uow,
        LocalObjectStore(objects),
        storage_backend="LOCAL_OBJECT_STORE",
    )


def _configuration() -> ConfigurationRecord:
    return ConfigurationRecord(
        aircraft_configuration_id=CONFIGURATION,
        aircraft_id=AIRCRAFT,
        block="B1",
        software_version="1.0",
        hardware_baseline="H1",
        sensor_configuration={"radar": "R1"},
        ew_configuration={},
        weapon_interface_configuration={},
        load_configuration={"fuel_kg": 1200},
        valid_from="2026-10-19T00:00:00Z",
        valid_to=None,
        source_ref=SOURCE,
        approval_status="DRAFT",
    )


def test_context_publish_replay_list_and_retire(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    _seed(database)
    service = _service(database, tmp_path / "objects")

    first = service.publish_context(
        artifact_kind="SCENARIO",
        logical_key="W1-SCENARIO",
        artifact_version="1",
        schema_version="1",
        payload={"name": "qualification"},
        principal_key="LOCAL_ADMIN",
    )
    replay = service.publish_context(
        artifact_kind="SCENARIO",
        logical_key="W1-SCENARIO",
        artifact_version="1",
        schema_version="1",
        payload={"name": "qualification"},
        principal_key="LOCAL_ADMIN",
    )
    assert replay == first
    assert service.exact_context(first.context_artifact_id) == first
    assert service.list_contexts(
        artifact_kind="SCENARIO", logical_key="W1-SCENARIO"
    ) == (first,)
    retired = service.retire_context(
        first.context_artifact_id,
        principal_key="LOCAL_ADMIN",
        reason="superseded by governed revision",
    )
    assert retired.status == "RETIRED"

    with pytest.raises(GovernanceRegistryError) as failure:
        service.retire_context(
            first.context_artifact_id,
            principal_key="LOCAL_ADMIN",
            reason="second retirement",
        )
    assert failure.value.code == "CONTEXT_NOT_ACTIVE"


def test_configuration_review_snapshot_lifecycle_and_audit(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    _seed(database)
    service = _service(database, tmp_path / "objects")
    draft = _configuration()

    assert service.create_configuration(draft, principal_key="CONFIG_EDITOR") == draft
    assert service.create_configuration(draft, principal_key="CONFIG_EDITOR") == draft
    approved = service.review_configuration(
        CONFIGURATION,
        decision="APPROVED",
        principal_key="CONFIG_REVIEWER",
        reason="review complete",
    )
    assert approved.approval_status == "APPROVED"
    assert service.list_configurations(AIRCRAFT) == (approved,)

    snapshot = service.snapshot_configuration(
        CONFIGURATION,
        session_id=SESSION,
        effective_session_time_us=100,
        principal_key="CONFIG_REVIEWER",
    )
    assert (
        service.snapshot_configuration(
            CONFIGURATION,
            session_id=SESSION,
            effective_session_time_us=100,
            principal_key="CONFIG_REVIEWER",
        )
        == snapshot
    )
    event = service.record_lifecycle_event(
        aircraft_id=AIRCRAFT,
        event_type="MAINTENANCE_COMPLETE",
        source_ref=SOURCE,
        start_occurred_at_utc="2026-10-19T01:00:00Z",
        flight_hours_total=42.5,
        properties={"work_order": "WO-1"},
        principal_key="MAINTENANCE_EDITOR",
    )
    assert service.list_lifecycle_events(AIRCRAFT) == (event,)

    with SQLiteDesktopUnitOfWork(database, authority_root=AUTHORITY) as uow:
        actions = [row.action for row in uow.audit_log.rows()]
    assert actions == [
        "CONFIGURATION_CREATE",
        "CONFIGURATION_CREATE_REPLAY",
        "CONFIGURATION_REVIEW",
        "CONFIGURATION_SNAPSHOT",
        "CONFIGURATION_SNAPSHOT_REPLAY",
        "LIFECYCLE_EVENT_RECORD",
    ]


def test_configuration_snapshot_requires_approval(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    _seed(database)
    service = _service(database, tmp_path / "objects")
    service.create_configuration(_configuration(), principal_key="CONFIG_EDITOR")
    with pytest.raises(GovernanceRegistryError) as failure:
        service.snapshot_configuration(
            CONFIGURATION,
            session_id=SESSION,
            effective_session_time_us=0,
            principal_key="CONFIG_EDITOR",
        )
    assert failure.value.code == "CONFIGURATION_NOT_APPROVED"
