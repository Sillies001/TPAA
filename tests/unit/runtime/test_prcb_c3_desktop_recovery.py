from __future__ import annotations

import json
from pathlib import Path

from tpaa_runtime import (
    create_desktop_production_backup,
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
    assert manifest["schema"] == "TPAA_PRCB_C3_PRODUCTION_BACKUP_V1"
    assert manifest["profile"] == "DESKTOP"
    assert manifest["db_schema_version"] == "1.9.0"

    restored_db = tmp_path / "restored.sqlite3"
    restored_objects = tmp_path / "restored-objects"
    restore_desktop_production_backup(
        backup=backup,
        target_database=restored_db,
        target_object_root=restored_objects,
    )
    verification = verify_sqlite(restored_db)
    assert verification.schema_version == "1.9.0"
    assert verification.core_baseline == "CB-1.4.0"
    restored_store = LocalObjectStore(restored_objects)
    assert restored_store.verify(stored) is True
    assert restored_store.read_bytes(stored.logical_uri) == b"production-state"
