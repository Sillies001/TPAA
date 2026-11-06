from __future__ import annotations

import os
from pathlib import Path

import pytest

from tpaa_runtime import (
    PostgreSQLServiceWriteDrain,
    create_managed_service_production_backup,
    restore_service_production_backup,
)
from tpaa_storage import (
    SERVICE_WRITE_GATE_LOCK_ID,
    LocalObjectStore,
    PostgreSQLRepositoryError,
    PostgreSQLServiceUnitOfWork,
)


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def test_managed_drain_pg_dump_and_pg_restore_against_real_postgres(
    tmp_path: Path,
) -> None:
    primary = _required_environment("TPAA_TEST_POSTGRES_CONNINFO")
    staging = _required_environment("TPAA_TEST_POSTGRES_RESTORE_CONNINFO")
    pg_dump = _required_environment("TPAA_TEST_PG_DUMP")
    pg_restore = _required_environment("TPAA_TEST_PG_RESTORE")
    object_root = tmp_path / "objects"
    store = LocalObjectStore(object_root)
    stored = store.put_bytes_immutable(
        "tpaa-object://qualification/recovery.bin",
        b"postgres-recovery-object",
    )

    with PostgreSQLServiceWriteDrain(primary) as receipt:
        assert receipt.state == "MANAGED_WRITES_BLOCKED"
        with pytest.raises(PostgreSQLRepositoryError) as blocked:
            with PostgreSQLServiceUnitOfWork(
                primary,
                write_gate_lock_id=SERVICE_WRITE_GATE_LOCK_ID,
            ):
                pass
        assert blocked.value.reason == "SERVICE_WRITE_DRAINED"

    backup = tmp_path / "service-backup"
    manifest, receipt = create_managed_service_production_backup(
        conninfo=primary,
        object_root=object_root,
        destination=backup,
        pg_dump_executable=pg_dump,
    )
    assert manifest.is_file()
    assert receipt.state == "MANAGED_WRITES_BLOCKED"

    restored_objects = tmp_path / "restored-objects"
    restored = restore_service_production_backup(
        backup=backup,
        staging_conninfo=staging,
        staging_object_root=restored_objects,
        staging_target_confirmed=True,
        pg_restore_executable=pg_restore,
    )

    assert restored["database_state"] == "VERIFIED_STAGING"
    assert restored["object_state"] == "VERIFIED_STAGING"
    restored_store = LocalObjectStore(restored_objects)
    assert restored_store.verify(stored)
