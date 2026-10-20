"""PRCB C3 production backup and recovery for Desktop and Service profiles."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import cast

from psycopg.conninfo import conninfo_to_dict

from tpaa_platform.filesync import InterProcessFileLock, atomic_replace_bytes
from tpaa_storage import PostgreSQLServiceUnitOfWork, verify_sqlite

from .consistency import desktop_write_quiescence_lock
from .service_drain import PostgreSQLServiceWriteDrain, ServiceWriteDrainReceipt

_BACKUP_SCHEMA = "TPAA_PRCB_C3_PRODUCTION_BACKUP_V2"
_BACKUP_STATUS_SCHEMA = "TPAA_DESKTOP_BACKUP_STATUS_V1"
_BACKUP_STATUS_NAME = ".tpaa-backup-status.json"
CommandRunner = Callable[[tuple[str, ...], Mapping[str, str]], None]


class ProductionRecoveryError(RuntimeError):
    """Fail-closed production backup or restore error."""


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _utc_instant(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProductionRecoveryError(f"backup {field} is invalid")
    try:
        instant = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProductionRecoveryError(f"backup {field} is invalid") from exc
    if instant.utcoffset() is None:
        raise ProductionRecoveryError(f"backup {field} is invalid")
    return instant.astimezone(UTC)


def _backup_status_path(database: Path) -> Path:
    return database.parent / _BACKUP_STATUS_NAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_runner(
    command: tuple[str, ...],
    environment: Mapping[str, str],
) -> None:
    merged = dict(os.environ)
    merged.update(environment)
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=merged,
        )
    except FileNotFoundError as exc:
        raise ProductionRecoveryError(
            f"required recovery executable unavailable: {command[0]}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ProductionRecoveryError(
            f"recovery command failed rc={exc.returncode}: {command[0]}"
        ) from exc


def _service_environment(conninfo: str) -> tuple[dict[str, str], str]:
    try:
        values = conninfo_to_dict(conninfo)
    except Exception as exc:
        raise ProductionRecoveryError("PostgreSQL conninfo is invalid") from exc
    if not isinstance(values, dict):
        raise ProductionRecoveryError("PostgreSQL conninfo projection is invalid")
    mapping = {
        "host": "PGHOST",
        "hostaddr": "PGHOSTADDR",
        "port": "PGPORT",
        "dbname": "PGDATABASE",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
    }
    environment = {
        env_name: str(values[key])
        for key, env_name in mapping.items()
        if values.get(key) is not None
    }
    database = environment.get("PGDATABASE", "")
    if not database:
        raise ProductionRecoveryError("PostgreSQL conninfo requires dbname")
    return environment, database


def _verify_service_database(
    conninfo: str,
    *,
    authority_root: Path | None = None,
) -> None:
    with PostgreSQLServiceUnitOfWork(
        conninfo,
        read_only=True,
        authority_root=authority_root,
    ) as uow:
        metadata = uow.metadata.get()
        uow.commit()
    if metadata.schema_version != "1.9.0" or metadata.core_baseline != "CB-1.5.0":
        raise ProductionRecoveryError("Service database authority mismatch")


def _object_members(root: Path) -> tuple[dict[str, object], ...]:
    if not root.is_dir():
        raise ProductionRecoveryError("object root is unavailable")
    members: list[dict[str, object]] = []
    for source in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = source.resolve().relative_to(root.resolve()).as_posix()
        logical = PurePosixPath(relative)
        if logical.parts[0] == ".locks" or source.name.endswith(".tmp"):
            continue
        members.append(
            {
                "path": relative,
                "sha256": _sha256(source),
                "size_bytes": source.stat().st_size,
            }
        )
    return tuple(members)


def _inventory_sha256(objects: tuple[dict[str, object], ...]) -> str:
    encoded = json.dumps(
        list(objects),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_sha256(
    *,
    database_sha256: str,
    object_inventory_sha256: str,
) -> str:
    encoded = json.dumps(
        {
            "database_sha256": database_sha256,
            "object_inventory_sha256": object_inventory_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _copy_object_tree(
    source_root: Path,
    destination_root: Path,
) -> tuple[dict[str, object], ...]:
    members = _object_members(source_root)
    for item in members:
        relative = str(item["path"])
        source = source_root / Path(*PurePosixPath(relative).parts)
        destination = destination_root / Path(*PurePosixPath(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return members


def _validate_relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ProductionRecoveryError("backup object path is invalid")
    logical = PurePosixPath(value)
    if logical.is_absolute() or any(part in {"", ".", ".."} for part in logical.parts):
        raise ProductionRecoveryError("backup object path is unsafe")
    return value


def _load_verified_backup(
    backup: Path,
    *,
    expected_profile: str,
) -> dict[str, object]:
    manifest_path = backup / "manifest.json"
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProductionRecoveryError("backup manifest unavailable/corrupt") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema") != _BACKUP_SCHEMA
        or raw.get("profile") != expected_profile
    ):
        raise ProductionRecoveryError("backup manifest schema/profile mismatch")
    database = raw.get("database")
    objects = raw.get("objects")
    if not isinstance(database, dict) or not isinstance(objects, list):
        raise ProductionRecoveryError("backup manifest shape invalid")
    database_file = _validate_relative(database.get("file"))
    database_path = backup / Path(*PurePosixPath(database_file).parts)
    expected_hash = database.get("sha256")
    if not isinstance(expected_hash, str) or _sha256(database_path) != expected_hash:
        raise ProductionRecoveryError("backup database hash mismatch")
    for item in objects:
        if not isinstance(item, dict):
            raise ProductionRecoveryError("backup object entry invalid")
        relative = _validate_relative(item.get("path"))
        expected = item.get("sha256")
        size = item.get("size_bytes")
        path = backup / "objects" / Path(*PurePosixPath(relative).parts)
        if (
            not isinstance(expected, str)
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
            or not path.is_file()
            or path.stat().st_size != size
            or _sha256(path) != expected
        ):
            raise ProductionRecoveryError(f"backup object mismatch: {relative}")
    consistency = raw.get("consistency")
    if not isinstance(consistency, dict):
        raise ProductionRecoveryError("backup consistency proof missing")
    expected_modes = (
        {"DESKTOP_WRITE_QUIESCENCE"}
        if expected_profile == "DESKTOP"
        else {"SERVICE_EXTERNAL_WRITE_DRAIN", "SERVICE_MANAGED_WRITE_DRAIN"}
    )
    if (
        consistency.get("mode") not in expected_modes
        or consistency.get("state") != "CAPTURED"
        or consistency.get("database_sha256") != expected_hash
    ):
        raise ProductionRecoveryError("backup consistency proof invalid")
    if consistency.get("mode") == "SERVICE_MANAGED_WRITE_DRAIN":
        _validated_service_drain_evidence(consistency.get("write_drain"))
    normalized_objects = tuple(cast(dict[str, object], item) for item in objects)
    inventory_sha256 = _inventory_sha256(normalized_objects)
    if consistency.get("object_inventory_sha256") != inventory_sha256:
        raise ProductionRecoveryError("backup object inventory hash mismatch")
    snapshot_sha256 = _snapshot_sha256(
        database_sha256=str(expected_hash),
        object_inventory_sha256=inventory_sha256,
    )
    if consistency.get("snapshot_sha256") != snapshot_sha256:
        raise ProductionRecoveryError("backup consistency watermark mismatch")
    return raw


def _write_desktop_backup_status(
    *,
    database: Path,
    manifest_path: Path,
    manifest: Mapping[str, object],
) -> None:
    consistency = manifest.get("consistency")
    created_at = manifest.get("created_at_utc")
    if not isinstance(consistency, Mapping):
        raise ProductionRecoveryError("backup consistency proof missing")
    snapshot_sha256 = consistency.get("snapshot_sha256")
    if not isinstance(snapshot_sha256, str) or len(snapshot_sha256) != 64:
        raise ProductionRecoveryError("backup consistency watermark invalid")
    _utc_instant(created_at, field="created_at_utc")
    payload = {
        "schema": _BACKUP_STATUS_SCHEMA,
        "profile": "DESKTOP",
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "snapshot_sha256": snapshot_sha256,
        "backup_created_at_utc": created_at,
        "verified_at_utc": _utc_now(),
    }
    atomic_replace_bytes(
        _backup_status_path(database),
        (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
    )


def desktop_backup_status(database: Path) -> dict[str, object]:
    """Return a path-free status after re-verifying the recorded V2 backup."""

    status_path = _backup_status_path(database)
    if not status_path.is_file():
        return {
            "schema": _BACKUP_STATUS_SCHEMA,
            "profile": "DESKTOP",
            "state": "NEVER_VERIFIED",
        }
    try:
        marker = json.loads(status_path.read_text(encoding="utf-8"))
        if (
            not isinstance(marker, dict)
            or marker.get("schema") != _BACKUP_STATUS_SCHEMA
            or marker.get("profile") != "DESKTOP"
        ):
            raise ProductionRecoveryError("backup status marker invalid")
        manifest_text = marker.get("manifest_path")
        if not isinstance(manifest_text, str):
            raise ProductionRecoveryError("backup status manifest path invalid")
        manifest_path = Path(manifest_text)
        if not manifest_path.is_absolute() or manifest_path.name != "manifest.json":
            raise ProductionRecoveryError("backup status manifest path invalid")
        if marker.get("manifest_sha256") != _sha256(manifest_path):
            raise ProductionRecoveryError("backup status manifest hash mismatch")
        manifest = _load_verified_backup(
            manifest_path.parent,
            expected_profile="DESKTOP",
        )
        consistency = manifest.get("consistency")
        if not isinstance(consistency, dict) or (
            consistency.get("snapshot_sha256") != marker.get("snapshot_sha256")
        ):
            raise ProductionRecoveryError("backup status snapshot mismatch")
        created_at = marker.get("backup_created_at_utc")
        created = _utc_instant(created_at, field="created_at_utc")
        verified_at = marker.get("verified_at_utc")
        _utc_instant(verified_at, field="verified_at_utc")
        age_seconds = max(0, int((datetime.now(tz=UTC) - created).total_seconds()))
        return {
            "schema": _BACKUP_STATUS_SCHEMA,
            "profile": "DESKTOP",
            "state": "VERIFIED",
            "backup_created_at_utc": created_at,
            "verified_at_utc": verified_at,
            "age_seconds": age_seconds,
            "snapshot_sha256": marker["snapshot_sha256"],
        }
    except Exception:
        return {
            "schema": _BACKUP_STATUS_SCHEMA,
            "profile": "DESKTOP",
            "state": "INVALID",
            "reason_code": "BACKUP_REFERENCE_INVALID",
        }


def _staging_directory(destination: Path) -> Path:
    if destination.exists():
        raise ProductionRecoveryError("backup destination must not already exist")
    staging = destination.with_name(f".{destination.name}.prcb-c3-staging")
    if staging.exists():
        raise ProductionRecoveryError("backup staging directory already exists")
    staging.mkdir(parents=True)
    return staging


def _write_manifest(
    staging: Path,
    *,
    profile: str,
    database_file: str,
    database_hash: str,
    objects: tuple[dict[str, object], ...],
    consistency_mode: str,
    consistency_evidence: Mapping[str, object] | None = None,
) -> Path:
    inventory_sha256 = _inventory_sha256(objects)
    consistency: dict[str, object] = {
        "mode": consistency_mode,
        "state": "CAPTURED",
        "database_sha256": database_hash,
        "object_inventory_sha256": inventory_sha256,
        "snapshot_sha256": _snapshot_sha256(
            database_sha256=database_hash,
            object_inventory_sha256=inventory_sha256,
        ),
    }
    if consistency_evidence is not None:
        consistency["write_drain"] = dict(consistency_evidence)
    payload = {
        "schema": _BACKUP_SCHEMA,
        "profile": profile,
        "canonical_baseline": "CB-1.5.0",
        "db_schema_version": "1.9.0",
        "created_at_utc": _utc_now(),
        "database": {
            "file": database_file,
            "sha256": database_hash,
        },
        "objects": list(objects),
        "consistency": consistency,
    }
    manifest = staging / "manifest.json"
    manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def create_desktop_production_backup(
    *,
    database: Path,
    object_root: Path,
    destination: Path,
    authority_root: Path | None = None,
) -> Path:
    staging = _staging_directory(destination)
    try:
        with InterProcessFileLock(desktop_write_quiescence_lock(object_root)):
            verification = verify_sqlite(database, authority_root=authority_root)
            if verification.schema_version != "1.9.0" or verification.core_baseline != "CB-1.5.0":
                raise ProductionRecoveryError("Desktop database authority mismatch")
            backup_database = staging / "database.sqlite3"
            with (
                closing(sqlite3.connect(database)) as source,
                closing(sqlite3.connect(backup_database)) as target,
            ):
                source.backup(target)
            objects = _copy_object_tree(object_root, staging / "objects")
            _write_manifest(
                staging,
                profile="DESKTOP",
                database_file="database.sqlite3",
                database_hash=_sha256(backup_database),
                objects=objects,
                consistency_mode="DESKTOP_WRITE_QUIESCENCE",
            )
            staging.replace(destination)
            manifest_path = destination / "manifest.json"
            manifest = _load_verified_backup(
                destination,
                expected_profile="DESKTOP",
            )
            _write_desktop_backup_status(
                database=database,
                manifest_path=manifest_path,
                manifest=manifest,
            )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination / "manifest.json"


def restore_desktop_production_backup(
    *,
    backup: Path,
    target_database: Path,
    target_object_root: Path,
    authority_root: Path | None = None,
) -> None:
    manifest = _load_verified_backup(backup, expected_profile="DESKTOP")
    if target_database.exists():
        raise ProductionRecoveryError("Desktop restore database target must be clean")
    if target_object_root.exists() and any(target_object_root.iterdir()):
        raise ProductionRecoveryError("Desktop restore object target must be clean")
    database = manifest["database"]
    assert isinstance(database, dict)
    database_file = _validate_relative(database.get("file"))
    source_database = backup / Path(*PurePosixPath(database_file).parts)
    db_staging = target_database.with_name(f".{target_database.name}.prcb-c3-restore")
    object_staging = target_object_root.with_name(f".{target_object_root.name}.prcb-c3-restore")
    if db_staging.exists() or object_staging.exists():
        raise ProductionRecoveryError("Desktop restore staging target exists")
    try:
        target_database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_database, db_staging)
        object_staging.mkdir(parents=True)
        objects = manifest["objects"]
        assert isinstance(objects, list)
        for item in objects:
            assert isinstance(item, dict)
            relative = _validate_relative(item.get("path"))
            source = backup / "objects" / Path(*PurePosixPath(relative).parts)
            target = object_staging / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        verification = verify_sqlite(
            db_staging,
            authority_root=authority_root,
        )
        if verification.schema_version != "1.9.0" or verification.core_baseline != "CB-1.5.0":
            raise ProductionRecoveryError("restored Desktop authority mismatch")
        _write_desktop_backup_status(
            database=target_database,
            manifest_path=backup / "manifest.json",
            manifest=manifest,
        )
        db_staging.replace(target_database)
        if target_object_root.exists():
            target_object_root.rmdir()
        object_staging.replace(target_object_root)
    except Exception:
        _backup_status_path(target_database).unlink(missing_ok=True)
        db_staging.unlink(missing_ok=True)
        shutil.rmtree(object_staging, ignore_errors=True)
        if target_database.exists():
            target_database.unlink(missing_ok=True)
        raise


def create_service_production_backup(
    *,
    conninfo: str,
    object_root: Path,
    destination: Path,
    pg_dump_executable: str = "pg_dump",
    command_runner: CommandRunner = _default_runner,
    authority_root: Path | None = None,
    write_drain_confirmed: bool = False,
    managed_drain_receipt: Mapping[str, object] | None = None,
) -> Path:
    if not write_drain_confirmed:
        raise ProductionRecoveryError("Service backup requires an externally enforced write drain")
    consistency_mode = "SERVICE_EXTERNAL_WRITE_DRAIN"
    if managed_drain_receipt is not None:
        _validated_service_drain_evidence(managed_drain_receipt)
        consistency_mode = "SERVICE_MANAGED_WRITE_DRAIN"
    _verify_service_database(conninfo, authority_root=authority_root)
    environment, _database = _service_environment(conninfo)
    staging = _staging_directory(destination)
    try:
        database_dump = staging / "database.dump"
        command_runner(
            (
                pg_dump_executable,
                "--format=custom",
                "--no-password",
                "--file",
                str(database_dump),
            ),
            environment,
        )
        if not database_dump.is_file() or database_dump.stat().st_size == 0:
            raise ProductionRecoveryError("pg_dump produced no database payload")
        objects = _copy_object_tree(object_root, staging / "objects")
        _write_manifest(
            staging,
            profile="SERVICE",
            database_file="database.dump",
            database_hash=_sha256(database_dump),
            objects=objects,
            consistency_mode=consistency_mode,
            consistency_evidence=managed_drain_receipt,
        )
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination / "manifest.json"


def create_service_migration_backup(
    *,
    conninfo: str,
    object_root: Path,
    destination: Path,
    managed_drain_receipt: Mapping[str, object],
    pg_dump_executable: str = "pg_dump",
    command_runner: CommandRunner = _default_runner,
) -> Path:
    """Capture a pre-migration Service backup under the migration-held write drain.

    Authority verification is deliberately owned by ``PostgreSQLMigrationService``
    because the source may be any governed 1.6--1.9 version rather than current head.
    """

    _validated_service_drain_evidence(managed_drain_receipt)
    environment, _database = _service_environment(conninfo)
    staging = _staging_directory(destination)
    try:
        database_dump = staging / "database.dump"
        command_runner(
            (
                pg_dump_executable,
                "--format=custom",
                "--no-password",
                "--file",
                str(database_dump),
            ),
            environment,
        )
        if not database_dump.is_file() or database_dump.stat().st_size == 0:
            raise ProductionRecoveryError("pg_dump produced no database payload")
        objects = _copy_object_tree(object_root, staging / "objects")
        _write_manifest(
            staging,
            profile="SERVICE",
            database_file="database.dump",
            database_hash=_sha256(database_dump),
            objects=objects,
            consistency_mode="SERVICE_MANAGED_WRITE_DRAIN",
            consistency_evidence=managed_drain_receipt,
        )
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination / "database.dump"


def _validated_service_drain_evidence(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProductionRecoveryError("Service managed write-drain evidence is missing")
    required_text = (
        "acquired_at_utc",
        "database_identity_sha256",
        "transaction_snapshot",
        "wal_lsn",
    )
    if (
        value.get("schema") != "TPAA_SERVICE_WRITE_DRAIN_V1"
        or value.get("state") != "MANAGED_WRITES_BLOCKED"
        or not all(isinstance(value.get(field), str) and value.get(field) for field in required_text)
    ):
        raise ProductionRecoveryError("Service managed write-drain evidence is invalid")
    digest = value.get("database_identity_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or digest != digest.lower()
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ProductionRecoveryError("Service managed write-drain database identity is invalid")
    return value


def create_managed_service_production_backup(
    *,
    conninfo: str,
    object_root: Path,
    destination: Path,
    pg_dump_executable: str = "pg_dump",
    command_runner: CommandRunner = _default_runner,
    authority_root: Path | None = None,
    drain_timeout_seconds: float = 30.0,
) -> tuple[Path, ServiceWriteDrainReceipt]:
    """Acquire the managed write gate and capture one Service V2 backup."""

    with PostgreSQLServiceWriteDrain(
        conninfo,
        timeout_seconds=drain_timeout_seconds,
    ) as receipt:
        manifest = create_service_production_backup(
            conninfo=conninfo,
            object_root=object_root,
            destination=destination,
            pg_dump_executable=pg_dump_executable,
            command_runner=command_runner,
            authority_root=authority_root,
            write_drain_confirmed=True,
            managed_drain_receipt=receipt.record(),
        )
    return manifest, receipt


def restore_service_production_backup(
    *,
    backup: Path,
    staging_conninfo: str,
    staging_object_root: Path,
    staging_target_confirmed: bool = False,
    pg_restore_executable: str = "pg_restore",
    command_runner: CommandRunner = _default_runner,
    authority_root: Path | None = None,
) -> dict[str, object]:
    if not staging_target_confirmed:
        raise ProductionRecoveryError("Service restore requires a confirmed clean staging target")
    manifest = _load_verified_backup(backup, expected_profile="SERVICE")
    if staging_object_root.exists() and any(staging_object_root.iterdir()):
        raise ProductionRecoveryError("Service staging object target must be clean")
    environment, database = _service_environment(staging_conninfo)
    database_info = manifest["database"]
    assert isinstance(database_info, dict)
    database_file = _validate_relative(database_info.get("file"))
    database_dump = backup / Path(*PurePosixPath(database_file).parts)
    object_staging = staging_object_root.with_name(f".{staging_object_root.name}.prcb-c3-restore")
    if object_staging.exists():
        raise ProductionRecoveryError("Service restore staging target exists")
    try:
        object_staging.mkdir(parents=True)
        objects = manifest["objects"]
        assert isinstance(objects, list)
        for item in objects:
            assert isinstance(item, dict)
            relative = _validate_relative(item.get("path"))
            source = backup / "objects" / Path(*PurePosixPath(relative).parts)
            target = object_staging / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        command_runner(
            (
                pg_restore_executable,
                "--exit-on-error",
                "--no-owner",
                "--no-password",
                "--dbname",
                database,
                str(database_dump),
            ),
            environment,
        )
        _verify_service_database(
            staging_conninfo,
            authority_root=authority_root,
        )
        if staging_object_root.exists():
            staging_object_root.rmdir()
        object_staging.replace(staging_object_root)
    except Exception:
        shutil.rmtree(object_staging, ignore_errors=True)
        raise
    consistency = manifest["consistency"]
    assert isinstance(consistency, dict)
    return {
        "schema": "TPAA_SERVICE_STAGING_RESTORE_V1",
        "profile": "SERVICE",
        "database_state": "VERIFIED_STAGING",
        "object_state": "VERIFIED_STAGING",
        "activation_state": "NOT_ACTIVATED",
        "activation_required": True,
        "snapshot_sha256": consistency["snapshot_sha256"],
    }
