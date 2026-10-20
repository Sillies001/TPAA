from __future__ import annotations

import json
from pathlib import Path

import pytest

import tpaa_runtime.recovery as recovery
from tpaa_runtime import (
    ProductionRecoveryError,
    create_service_migration_backup,
    create_service_production_backup,
    restore_service_production_backup,
)
from tpaa_storage import LocalObjectStore


def test_prcb_c3_service_backup_commands_keep_conninfo_secret_off_argv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        recovery,
        "_verify_service_database",
        lambda _value, **_kwargs: None,
    )
    object_root = tmp_path / "objects"
    LocalObjectStore(object_root).put_bytes(
        "tpaa-object://prcb-c3/service/state.bin",
        b"service-state",
    )
    calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def runner(
        command: tuple[str, ...],
        environment,
    ) -> None:
        env = dict(environment)
        calls.append((command, env))
        if command[0] == "pg_dump":
            output = Path(command[command.index("--file") + 1])
            output.write_bytes(b"fake-custom-dump")

    conninfo = (
        "host=localhost port=5432 dbname=tpaa user=tpaa password=super-secret sslmode=disable"
    )
    backup = tmp_path / "service-backup"
    manifest = create_service_production_backup(
        conninfo=conninfo,
        object_root=object_root,
        destination=backup,
        command_runner=runner,
        write_drain_confirmed=True,
    )
    payload = manifest.read_text(encoding="utf-8")
    assert "super-secret" not in payload
    dump_command, dump_env = calls[0]
    assert all("super-secret" not in item for item in dump_command)
    assert dump_env["PGPASSWORD"] == "super-secret"
    assert dump_env["PGDATABASE"] == "tpaa"

    restored_objects = tmp_path / "restored-objects"
    receipt = restore_service_production_backup(
        backup=backup,
        staging_conninfo=conninfo,
        staging_object_root=restored_objects,
        staging_target_confirmed=True,
        command_runner=runner,
    )
    assert receipt["database_state"] == "VERIFIED_STAGING"
    assert receipt["object_state"] == "VERIFIED_STAGING"
    assert receipt["activation_state"] == "NOT_ACTIVATED"
    assert receipt["activation_required"] is True
    restore_command, restore_env = calls[1]
    assert restore_command[0] == "pg_restore"
    assert all("super-secret" not in item for item in restore_command)
    assert restore_env["PGPASSWORD"] == "super-secret"
    assert json.loads(payload)["profile"] == "SERVICE"
    assert json.loads(payload)["consistency"]["mode"] == "SERVICE_EXTERNAL_WRITE_DRAIN"
    restored = LocalObjectStore(restored_objects)
    assert restored.read_bytes("tpaa-object://prcb-c3/service/state.bin") == b"service-state"


def test_prcb_c3_service_backup_requires_external_write_drain(
    tmp_path: Path,
) -> None:
    with pytest.raises(ProductionRecoveryError, match="write drain"):
        create_service_production_backup(
            conninfo="dbname=tpaa",
            object_root=tmp_path / "objects",
            destination=tmp_path / "backup",
        )


def test_w1_service_migration_backup_requires_and_records_managed_drain(
    tmp_path: Path,
) -> None:
    def runner(command: tuple[str, ...], _environment) -> None:
        output = Path(command[command.index("--file") + 1])
        output.write_bytes(b"migration-custom-dump")

    receipt = {
        "schema": "TPAA_SERVICE_WRITE_DRAIN_V1",
        "state": "MANAGED_WRITES_BLOCKED",
        "acquired_at_utc": "2026-10-19T00:00:00Z",
        "lock_id": 1,
        "database_identity_sha256": "a" * 64,
        "transaction_snapshot": "1:2:",
        "wal_lsn": "0/1",
    }
    (tmp_path / "objects").mkdir()
    backup = tmp_path / "migration-backup"
    dump = create_service_migration_backup(
        conninfo="dbname=tpaa",
        object_root=tmp_path / "objects",
        destination=backup,
        managed_drain_receipt=receipt,
        command_runner=runner,
    )
    assert dump.read_bytes() == b"migration-custom-dump"
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["consistency"]["mode"] == "SERVICE_MANAGED_WRITE_DRAIN"
    assert manifest["consistency"]["write_drain"] == receipt


def test_prcb_c3_service_restore_requires_confirmed_staging_target(
    tmp_path: Path,
) -> None:
    with pytest.raises(ProductionRecoveryError, match="clean staging target"):
        restore_service_production_backup(
            backup=tmp_path / "backup",
            staging_conninfo="dbname=tpaa_staging",
            staging_object_root=tmp_path / "staging-objects",
        )
