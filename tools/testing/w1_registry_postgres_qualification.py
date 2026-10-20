"""Qualify W1 registry and Release services on PostgreSQL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg

from tpaa_application import (
    ConfigurationRecord,
    GovernanceRegistryService,
    ReleaseManagementService,
)
from tpaa_storage import (
    SERVICE_WRITE_GATE_LOCK_ID,
    LocalObjectStore,
    PostgreSQLServiceUnitOfWork,
)

MODEL = "c1000000-0000-4000-8000-000000000001"
AIRCRAFT = "c1000000-0000-4000-8000-000000000002"
SESSION = "c1000000-0000-4000-8000-000000000003"
CONFIGURATION = "c1000000-0000-4000-8000-000000000004"
SOURCE = "c1000000-0000-4000-8000-000000000005"
JOB1 = "c1000000-0000-4000-8000-000000000011"
JOB2 = "c1000000-0000-4000-8000-000000000012"
RELEASE1 = "c1000000-0000-4000-8000-000000000021"
RELEASE2 = "c1000000-0000-4000-8000-000000000022"
SCOPE = "W1:POSTGRES:QUALIFICATION"


def _seed(conninfo: str) -> None:
    connection = psycopg.connect(conninfo, autocommit=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''INSERT INTO master.aircraft_model (
                       aircraft_model_id, type_code, model_name
                   ) VALUES (%s, 'W1', 'W1 PostgreSQL model')''',
                (MODEL,),
            )
            cursor.execute(
                '''INSERT INTO master.aircraft (
                       aircraft_id, aircraft_model_id, internal_code, master_data_status
                   ) VALUES (%s, %s, 'W1-PG-001', 'ACTIVE')''',
                (AIRCRAFT, MODEL),
            )
            cursor.execute(
                '''INSERT INTO registry.training_session (
                       session_id, session_code, session_type,
                       start_session_time_us, end_session_time_us,
                       training_type_set, data_status, source_count, schema_version
                   ) VALUES (%s, 'W1-PG-SESSION', 'SIM', 0, 1000000,
                             '{}', 'READY', 1, '1.9.0')''',
                (SESSION,),
            )
            for job, key in ((JOB1, "W1-PG-JOB-1"), (JOB2, "W1-PG-JOB-2")):
                cursor.execute(
                    '''INSERT INTO registry.compute_job (
                           job_id, job_type, job_key, status, component_version,
                           input_hash, progress, reason_codes, created_at,
                           started_at, finished_at
                       ) VALUES (%s, 'W1_RELEASE', %s, 'SUCCEEDED', 'W1',
                                 %s, 1.0, '{}', now(), now(), now())''',
                    (job, key, "1" * 64),
                )
            cursor.execute(
                '''INSERT INTO registry.analysis_release (
                       release_id, scope_type, scope_key, release_no, compute_job_id,
                       catalog_version, catalog_hash, context_binding_hash, status,
                       parent_release_id, manifest_hash, created_at, published_at
                   ) VALUES (%s, 'LONGITUDINAL', %s, 1, %s, '1', %s, %s,
                             'PUBLISHED', NULL, %s, now(), now())''',
                (RELEASE1, SCOPE, JOB1, "2" * 64, "3" * 64, "4" * 64),
            )
            cursor.execute(
                '''INSERT INTO registry.analysis_release (
                       release_id, scope_type, scope_key, release_no, compute_job_id,
                       catalog_version, catalog_hash, context_binding_hash, status,
                       parent_release_id, manifest_hash, created_at, published_at
                   ) VALUES (%s, 'LONGITUDINAL', %s, 2, %s, '1', %s, %s,
                             'PUBLISHED', %s, %s, now(), now())''',
                (RELEASE2, SCOPE, JOB2, "2" * 64, "3" * 64, RELEASE1, "5" * 64),
            )
            cursor.execute(
                '''INSERT INTO registry.release_scope_pointer (
                       scope_type, scope_key, current_release_id, version_token, updated_at
                   ) VALUES ('LONGITUDINAL', %s, %s, 2, now())''',
                (SCOPE, RELEASE2),
            )
        connection.commit()
    finally:
        connection.close()


def qualify(conninfo: str, authority_root: Path, object_root: Path) -> dict[str, object]:
    _seed(conninfo)

    def read_uow() -> PostgreSQLServiceUnitOfWork:
        return PostgreSQLServiceUnitOfWork(
            conninfo, read_only=True, authority_root=authority_root
        )

    def write_uow() -> PostgreSQLServiceUnitOfWork:
        return PostgreSQLServiceUnitOfWork(
            conninfo,
            write_gate_lock_id=SERVICE_WRITE_GATE_LOCK_ID,
            authority_root=authority_root,
        )

    registry = GovernanceRegistryService(
        read_uow,  # type: ignore[arg-type]
        write_uow,  # type: ignore[arg-type]
        LocalObjectStore(object_root),
        storage_backend="LOCAL_OBJECT_STORE",
    )
    context = registry.publish_context(
        artifact_kind="SCENARIO",
        logical_key="W1-PG-SCENARIO",
        artifact_version="1",
        schema_version="1",
        payload={"qualified": True},
        principal_key="LOCAL_ADMIN",
    )
    replay = registry.publish_context(
        artifact_kind="SCENARIO",
        logical_key="W1-PG-SCENARIO",
        artifact_version="1",
        schema_version="1",
        payload={"qualified": True},
        principal_key="LOCAL_ADMIN",
    )
    if replay != context:
        raise RuntimeError("PostgreSQL context replay mismatch")
    registry.retire_context(
        context.context_artifact_id,
        principal_key="LOCAL_ADMIN",
        reason="qualification retirement",
    )
    configuration = ConfigurationRecord(
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
    registry.create_configuration(configuration, principal_key="CONFIG_EDITOR")
    registry.review_configuration(
        CONFIGURATION,
        decision="APPROVED",
        principal_key="CONFIG_REVIEWER",
        reason="qualification approval",
    )
    snapshot = registry.snapshot_configuration(
        CONFIGURATION,
        session_id=SESSION,
        effective_session_time_us=100,
        principal_key="CONFIG_REVIEWER",
    )
    event = registry.record_lifecycle_event(
        aircraft_id=AIRCRAFT,
        event_type="MAINTENANCE_COMPLETE",
        source_ref=SOURCE,
        properties={"work_order": "WO-PG-1"},
        principal_key="MAINTENANCE_EDITOR",
    )

    releases = ReleaseManagementService(
        read_uow,  # type: ignore[arg-type]
        write_uow,  # type: ignore[arg-type]
    )
    releases.supersede(
        RELEASE1,
        successor_release_id=RELEASE2,
        expected_version_token=2,
        principal_key="LOCAL_ADMIN",
        reason="qualification successor",
    )
    releases.withdraw(
        RELEASE2,
        expected_version_token=2,
        principal_key="LOCAL_ADMIN",
        reason="qualification withdrawal",
    )
    final_releases = releases.list(scope_type="LONGITUDINAL", scope_key=SCOPE)
    with read_uow() as uow:
        audit_count = len(uow.audit_log.rows())
    return {
        "schema": "TPAA_W1_REGISTRY_POSTGRES_QUALIFICATION_V1",
        "status": "PASS",
        "context_status": registry.exact_context(context.context_artifact_id).status,
        "configuration_snapshot_id": snapshot.snapshot_id,
        "lifecycle_event_id": event.lifecycle_event_id,
        "release_statuses": [item.status for item in final_releases],
        "audit_count": audit_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conninfo", required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--object-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            qualify(
                args.conninfo,
                args.authority_root.resolve(),
                args.object_root.resolve(),
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
