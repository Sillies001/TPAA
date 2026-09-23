"""Development backup/restore smoke primitives for M0-STO-007."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .bootstrap import verify_sqlite
from .object_store import LocalObjectStore, StoredObject


class BackupRestoreError(RuntimeError):
    pass


def _sqlite_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def create_development_backup(
    *,
    database: Path,
    object_store: LocalObjectStore,
    objects: tuple[StoredObject, ...],
    destination: Path,
) -> Path:
    verification = verify_sqlite(database)
    destination.mkdir(parents=True, exist_ok=False)
    backup_db = destination / "database.sqlite3"
    _sqlite_backup(database, backup_db)

    object_entries: list[dict[str, object]] = []
    object_dir = destination / "objects"
    object_dir.mkdir()
    for index, stored in enumerate(objects):
        if not object_store.verify(stored):
            raise BackupRestoreError(f"source object verification failed: {stored.logical_uri}")
        data = object_store.read_bytes(stored.logical_uri)
        backup_name = f"{index:04d}-{stored.artifact_sha256}.bin"
        backup_path = object_dir / backup_name
        backup_path.write_bytes(data)
        object_entries.append(
            {
                **asdict(stored),
                "backup_file": f"objects/{backup_name}",
            }
        )

    manifest = {
        "schema": "TPAA_M0_DEVELOPMENT_BACKUP_V1",
        "qualification": "DEVELOPMENT_FIXTURE_ONLY",
        "database": {
            "file": "database.sqlite3",
            "schema_version": verification.schema_version,
            "core_baseline": verification.core_baseline,
            "authority_sha256": verification.authority_sha256,
            "baseline_lock_sha256": verification.baseline_lock_sha256,
            "physical_schema_sha256": verification.physical_schema_sha256,
        },
        "objects": object_entries,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def restore_development_backup(
    *,
    backup: Path,
    target_database: Path,
    target_object_store: LocalObjectStore,
) -> tuple[StoredObject, ...]:
    manifest_path = backup / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupRestoreError(f"backup manifest unavailable/corrupt: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != "TPAA_M0_DEVELOPMENT_BACKUP_V1":
        raise BackupRestoreError("unsupported backup manifest")

    db = manifest.get("database")
    objects = manifest.get("objects")
    if not isinstance(db, dict) or not isinstance(objects, list):
        raise BackupRestoreError("backup manifest shape invalid")
    source_db = backup / str(db.get("file"))
    if target_database.exists():
        raise BackupRestoreError("restore target database must not already exist")
    _sqlite_backup(source_db, target_database)
    verification = verify_sqlite(target_database)
    for key, actual in (
        ("schema_version", verification.schema_version),
        ("core_baseline", verification.core_baseline),
        ("authority_sha256", verification.authority_sha256),
        ("baseline_lock_sha256", verification.baseline_lock_sha256),
        ("physical_schema_sha256", verification.physical_schema_sha256),
    ):
        if db.get(key) != actual:
            raise BackupRestoreError(f"restored database provenance mismatch: {key}")

    restored: list[StoredObject] = []
    for raw in objects:
        if not isinstance(raw, dict):
            raise BackupRestoreError("backup object entry invalid")
        logical_uri = raw.get("logical_uri")
        digest = raw.get("artifact_sha256")
        byte_size = raw.get("byte_size")
        backup_file = raw.get("backup_file")
        if (
            not isinstance(logical_uri, str)
            or not isinstance(digest, str)
            or not isinstance(byte_size, int)
            or not isinstance(backup_file, str)
        ):
            raise BackupRestoreError("backup object metadata invalid")
        data = (backup / backup_file).read_bytes()
        stored = target_object_store.put_bytes(logical_uri, data)
        if stored.artifact_sha256 != digest or stored.byte_size != byte_size:
            raise BackupRestoreError(f"restored object hash mismatch: {logical_uri}")
        restored.append(stored)
    return tuple(restored)
