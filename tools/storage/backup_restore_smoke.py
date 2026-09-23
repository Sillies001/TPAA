#!/usr/bin/env python3
"""Disposable M0-STO-007 development backup/restore smoke."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_storage.backup_restore import (  # noqa: E402
    create_development_backup,
    restore_development_backup,
)
from tpaa_storage.bootstrap import bootstrap_sqlite, verify_sqlite  # noqa: E402
from tpaa_storage.object_store import LocalObjectStore  # noqa: E402


def run() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="tpaa-backup-") as raw:
        root = Path(raw)
        source_db = root / "source.sqlite3"
        bootstrap_sqlite(source_db)
        source_store = LocalObjectStore(root / "source-objects")
        source_object = source_store.put_bytes(
            "tpaa-object://fixture/M0/backup/payload.bin",
            b"synthetic-backup-payload",
        )
        backup_dir = root / "backup"
        manifest = create_development_backup(
            database=source_db,
            object_store=source_store,
            objects=(source_object,),
            destination=backup_dir,
        )

        restored_db = root / "restored.sqlite3"
        restored_store = LocalObjectStore(root / "restored-objects")
        restored_objects = restore_development_backup(
            backup=backup_dir,
            target_database=restored_db,
            target_object_store=restored_store,
        )
        verification = verify_sqlite(restored_db)
        checks = {
            "manifest": manifest.is_file(),
            "database_schema": verification.schema_version == "1.6.0",
            "database_core": verification.core_baseline == "CB-1.4.0",
            "object_count": len(restored_objects) == 1,
            "object_ref": restored_objects[0] == source_object,
            "object_bytes": restored_store.read_bytes(source_object.logical_uri)
            == b"synthetic-backup-payload",
        }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "TPAA_M0_BACKUP_RESTORE_SMOKE_V1",
        "task": "M0-STO-007",
        "status": status,
        "checks": checks,
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
