from __future__ import annotations

import json
from pathlib import Path

import tpaa_runtime.recovery as recovery
from tpaa_runtime import (
    create_service_production_backup,
    restore_service_production_backup,
)
from tpaa_storage import LocalObjectStore


def test_prcb_c3_service_backup_commands_keep_conninfo_secret_off_argv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(recovery, "_verify_service_database", lambda _value: None)
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
        "host=localhost port=5432 dbname=tpaa "
        "user=tpaa password=super-secret sslmode=disable"
    )
    backup = tmp_path / "service-backup"
    manifest = create_service_production_backup(
        conninfo=conninfo,
        object_root=object_root,
        destination=backup,
        command_runner=runner,
    )
    payload = manifest.read_text(encoding="utf-8")
    assert "super-secret" not in payload
    dump_command, dump_env = calls[0]
    assert all("super-secret" not in item for item in dump_command)
    assert dump_env["PGPASSWORD"] == "super-secret"
    assert dump_env["PGDATABASE"] == "tpaa"

    restored_objects = tmp_path / "restored-objects"
    restore_service_production_backup(
        backup=backup,
        target_conninfo=conninfo,
        target_object_root=restored_objects,
        command_runner=runner,
    )
    restore_command, restore_env = calls[1]
    assert restore_command[0] == "pg_restore"
    assert all("super-secret" not in item for item in restore_command)
    assert restore_env["PGPASSWORD"] == "super-secret"
    assert json.loads(payload)["profile"] == "SERVICE"
    restored = LocalObjectStore(restored_objects)
    assert (
        restored.read_bytes("tpaa-object://prcb-c3/service/state.bin")
        == b"service-state"
    )
