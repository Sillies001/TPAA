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
from pathlib import Path, PurePosixPath

from psycopg.conninfo import conninfo_to_dict

from tpaa_storage import PostgreSQLServiceUnitOfWork, verify_sqlite

_BACKUP_SCHEMA = "TPAA_PRCB_C3_PRODUCTION_BACKUP_V1"
CommandRunner = Callable[[tuple[str, ...], Mapping[str, str]], None]


class ProductionRecoveryError(RuntimeError):
    """Fail-closed production backup or restore error."""


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


def _verify_service_database(conninfo: str) -> None:
    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        metadata = uow.metadata.get()
        uow.commit()
    if (
        metadata.schema_version != "1.9.0"
        or metadata.core_baseline != "CB-1.4.0"
    ):
        raise ProductionRecoveryError("Service database authority mismatch")


def _object_members(root: Path) -> tuple[dict[str, object], ...]:
    if not root.is_dir():
        raise ProductionRecoveryError("object root is unavailable")
    members: list[dict[str, object]] = []
    for source in sorted(path for path in root.rglob("*") if path.is_file()):
        if source.name.startswith(".") and source.name.endswith(".lock"):
            continue
        relative = source.resolve().relative_to(root.resolve()).as_posix()
        members.append(
            {
                "path": relative,
                "sha256": _sha256(source),
                "size_bytes": source.stat().st_size,
            }
        )
    return tuple(members)


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
    return raw


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
) -> Path:
    payload = {
        "schema": _BACKUP_SCHEMA,
        "profile": profile,
        "canonical_baseline": "CB-1.4.0",
        "db_schema_version": "1.9.0",
        "database": {
            "file": database_file,
            "sha256": database_hash,
        },
        "objects": list(objects),
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
) -> Path:
    verification = verify_sqlite(database)
    if (
        verification.schema_version != "1.9.0"
        or verification.core_baseline != "CB-1.4.0"
    ):
        raise ProductionRecoveryError("Desktop database authority mismatch")
    staging = _staging_directory(destination)
    try:
        backup_database = staging / "database.sqlite3"
        with closing(sqlite3.connect(database)) as source, closing(
            sqlite3.connect(backup_database)
        ) as target:
            source.backup(target)
        objects = _copy_object_tree(object_root, staging / "objects")
        _write_manifest(
            staging,
            profile="DESKTOP",
            database_file="database.sqlite3",
            database_hash=_sha256(backup_database),
            objects=objects,
        )
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination / "manifest.json"


def restore_desktop_production_backup(
    *,
    backup: Path,
    target_database: Path,
    target_object_root: Path,
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
    db_staging = target_database.with_name(
        f".{target_database.name}.prcb-c3-restore"
    )
    object_staging = target_object_root.with_name(
        f".{target_object_root.name}.prcb-c3-restore"
    )
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
        verification = verify_sqlite(db_staging)
        if (
            verification.schema_version != "1.9.0"
            or verification.core_baseline != "CB-1.4.0"
        ):
            raise ProductionRecoveryError("restored Desktop authority mismatch")
        db_staging.replace(target_database)
        if target_object_root.exists():
            target_object_root.rmdir()
        object_staging.replace(target_object_root)
    except Exception:
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
) -> Path:
    _verify_service_database(conninfo)
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
        )
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination / "manifest.json"


def restore_service_production_backup(
    *,
    backup: Path,
    target_conninfo: str,
    target_object_root: Path,
    pg_restore_executable: str = "pg_restore",
    command_runner: CommandRunner = _default_runner,
) -> None:
    manifest = _load_verified_backup(backup, expected_profile="SERVICE")
    if target_object_root.exists() and any(target_object_root.iterdir()):
        raise ProductionRecoveryError("Service restore object target must be clean")
    environment, database = _service_environment(target_conninfo)
    database_info = manifest["database"]
    assert isinstance(database_info, dict)
    database_file = _validate_relative(database_info.get("file"))
    database_dump = backup / Path(*PurePosixPath(database_file).parts)
    object_staging = target_object_root.with_name(
        f".{target_object_root.name}.prcb-c3-restore"
    )
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
        _verify_service_database(target_conninfo)
        if target_object_root.exists():
            target_object_root.rmdir()
        object_staging.replace(target_object_root)
    except Exception:
        shutil.rmtree(object_staging, ignore_errors=True)
        raise
