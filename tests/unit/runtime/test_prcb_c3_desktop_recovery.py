from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_runtime import (
    ProductionRecoveryError,
    create_desktop_production_backup,
    desktop_backup_status,
    restore_desktop_production_backup,
)
from tpaa_storage import LocalObjectStore, bootstrap_sqlite, verify_sqlite


def test_prcb_c3_desktop_backup_restore_preserves_db_and_object_hashes(
    tmp_path: Path,
) -> None:
    source_db = tmp_path / "source.sqlite3"
    source_objects = tmp_path / "source-objects"
    bootstrap_sqlite(source_db)
    store = LocalObjectStore(source_objects)
    stored = store.put_bytes(
        "tpaa-object://prcb-c3/runtime/state.bin",
        b"production-state",
    )

    backup = tmp_path / "backup"
    manifest_path = create_desktop_production_backup(
        database=source_db,
        object_root=source_objects,
        destination=backup,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "TPAA_PRCB_C3_PRODUCTION_BACKUP_V2"
    assert manifest["profile"] == "DESKTOP"
    assert manifest["db_schema_version"] == "1.9.0"
    assert manifest["consistency"]["mode"] == "DESKTOP_WRITE_QUIESCENCE"
    assert manifest["consistency"]["state"] == "CAPTURED"
    assert len(manifest["consistency"]["snapshot_sha256"]) == 64
    assert all(not item["path"].startswith(".locks/") for item in manifest["objects"])
    backup_status = desktop_backup_status(source_db)
    assert backup_status["state"] == "VERIFIED"
    assert backup_status["snapshot_sha256"] == manifest["consistency"]["snapshot_sha256"]

    restored_db = tmp_path / "restored.sqlite3"
    restored_objects = tmp_path / "restored-objects"
    restore_desktop_production_backup(
        backup=backup,
        target_database=restored_db,
        target_object_root=restored_objects,
    )
    verification = verify_sqlite(restored_db)
    assert verification.schema_version == "1.9.0"
    assert verification.core_baseline == "CB-1.5.0"
    restored_store = LocalObjectStore(restored_objects)
    assert restored_store.verify(stored) is True
    assert restored_store.read_bytes(stored.logical_uri) == b"production-state"
    assert desktop_backup_status(restored_db)["state"] == "VERIFIED"


def test_prcb_c3_desktop_restore_rejects_tampered_consistency_watermark(
    tmp_path: Path,
) -> None:
    source_db = tmp_path / "source.sqlite3"
    source_objects = tmp_path / "source-objects"
    bootstrap_sqlite(source_db)
    LocalObjectStore(source_objects).put_bytes(
        "tpaa-object://prcb-c3/runtime/state.bin",
        b"production-state",
    )
    backup = tmp_path / "backup"
    manifest_path = create_desktop_production_backup(
        database=source_db,
        object_root=source_objects,
        destination=backup,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["consistency"]["snapshot_sha256"] = "0" * 64
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True),
        encoding="utf-8",
    )
    assert desktop_backup_status(source_db) == {
        "schema": "TPAA_DESKTOP_BACKUP_STATUS_V1",
        "profile": "DESKTOP",
        "state": "INVALID",
        "reason_code": "BACKUP_REFERENCE_INVALID",
    }

    target_database = tmp_path / "restored.sqlite3"
    target_objects = tmp_path / "restored-objects"
    with pytest.raises(ProductionRecoveryError, match="watermark mismatch"):
        restore_desktop_production_backup(
            backup=backup,
            target_database=target_database,
            target_object_root=target_objects,
        )
    assert not target_database.exists()
    assert not target_objects.exists()
