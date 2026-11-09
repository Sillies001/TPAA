#!/usr/bin/env python3
"""Governed SQLite migration primitives for G1 DB 1.9.0 -> 1.10.0."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tpaa_canonical.byte_stability import match_governed_text_bytes
from tpaa_storage.bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    CORE_MODEL_ARTIFACT_ID,
    BootstrapError,
    BootstrapVerification,
    _bootstrap_connection,
    _configure_sqlite,
    _schema_fingerprint,
    _SchemaAuthority,
    _sqlite_create_statements,
    _verify_connection,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_CORE = ROOT / "baseline" / "CB-1.5.0" / "canonical" / "CORE_LOGICAL_MODEL.json"
TARGET_CORE = ROOT / "baseline" / "CB-1.6.0" / "canonical" / "CORE_LOGICAL_MODEL.json"
SOURCE_CORE_SHA256 = "85befeab110a9fd2476720f601920bd4ca5e0f72c8611f1ca3a8f3e90f53d7cb"
SOURCE_LOCK_SHA256 = "ecdb68d0aa17ad49b2b0b3bdbad0e82559cd455725a0eb2a2a4855feba99edab"
TARGET_CORE_SHA256 = "7bafa74416896909d75c5798b81bf59b643beb8897cc2c1bb61ba7cf901935d3"
TARGET_LOCK_SHA256 = "68ee3fc8f75e3435f2127b41eb1d933de79d1d70a5a9bd7a1c6295321160a731"
SOURCE_DB_SCHEMA_VERSION = "1.9.0"
TARGET_DB_SCHEMA_VERSION = "1.10.0"
NEW_RELATIONS = (
    "registry.batch_registration",
    "registry.batch_training_type_revision",
    "context.force_formation_context_revision",
    "context.force_formation_member",
)


class MigrationError(RuntimeError):
    """Fail-closed G1 migration error."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"G1_MIGRATION_FAIL reason={reason} detail={detail}")


def _authority(
    path: Path,
    *,
    expected_hash: str,
    schema: str,
    core: str,
    lock_hash: str,
) -> _SchemaAuthority:
    baseline_root = path.parent.parent
    lock_path = baseline_root / "BASELINE_LOCK.json"
    try:
        canonical_lock_bytes, _ = match_governed_text_bytes(
            lock_path.read_bytes(), lock_hash
        )
        lock_payload = json.loads(canonical_lock_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise MigrationError(
            "AUTHORITY_LOCK_HASH_MISMATCH", f"path={lock_path} detail={exc}"
        ) from exc
    baseline_metadata = lock_payload.get("baseline")
    if not isinstance(baseline_metadata, Mapping):
        raise MigrationError("AUTHORITY_LOCK_INVALID", f"path={lock_path}")
    if baseline_metadata.get("core") != core or baseline_metadata.get("db_schema") != schema:
        raise MigrationError(
            "AUTHORITY_LOCK_SCOPE_MISMATCH",
            f"path={lock_path} expected_core={core} expected_schema={schema}",
        )
    raw_entries = lock_payload.get("artifacts")
    if not isinstance(raw_entries, list):
        raise MigrationError("AUTHORITY_LOCK_INVALID", f"path={lock_path} artifacts")
    entry = next(
        (
            item
            for item in raw_entries
            if isinstance(item, Mapping) and item.get("file") == path.name
        ),
        None,
    )
    if not isinstance(entry, Mapping) or entry.get("sha256") != expected_hash:
        raise MigrationError("AUTHORITY_LOCK_ENTRY_MISMATCH", f"path={path}")
    expected_bytes = entry.get("bytes")
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise MigrationError("AUTHORITY_LOCK_ENTRY_MISMATCH", f"path={path} bytes")
    try:
        canonical_authority_bytes, _ = match_governed_text_bytes(
            path.read_bytes(), expected_hash, expected_bytes
        )
    except (OSError, ValueError) as exc:
        raise MigrationError(
            "AUTHORITY_HASH_MISMATCH", f"path={path} detail={exc}"
        ) from exc
    payload: Any = json.loads(canonical_authority_bytes.decode("utf-8"))
    if not isinstance(payload, Mapping) or payload.get("db_schema_version") != schema:
        raise MigrationError("AUTHORITY_SCHEMA_MISMATCH", f"path={path}")
    tables = payload.get("tables")
    if not isinstance(tables, Mapping) or not tables:
        raise MigrationError("AUTHORITY_TABLES_INVALID", f"path={path}")
    normalized: dict[str, Mapping[str, Any]] = {}
    for name, table in tables.items():
        if not isinstance(name, str) or not isinstance(table, Mapping):
            raise MigrationError("AUTHORITY_TABLE_INVALID", f"table={name!r}")
        normalized[name] = table
    return _SchemaAuthority(
        schema_version=schema,
        core_baseline=core,
        authority_sha256=expected_hash,
        baseline_lock_sha256=lock_hash,
        tables=normalized,
    )


def source_authority() -> _SchemaAuthority:
    return _authority(
        SOURCE_CORE,
        expected_hash=SOURCE_CORE_SHA256,
        schema=SOURCE_DB_SCHEMA_VERSION,
        core="CB-1.5.0",
        lock_hash=SOURCE_LOCK_SHA256,
    )


def target_authority() -> _SchemaAuthority:
    return _authority(
        TARGET_CORE,
        expected_hash=TARGET_CORE_SHA256,
        schema=TARGET_DB_SCHEMA_VERSION,
        core="CB-1.6.0",
        lock_hash=TARGET_LOCK_SHA256,
    )


def new_relation_names() -> tuple[str, ...]:
    source = source_authority()
    target = target_authority()
    actual = tuple(name for name in target.tables if name not in source.tables)
    if actual != NEW_RELATIONS:
        raise MigrationError("NEW_RELATION_INVENTORY_MISMATCH", f"actual={actual!r}")
    return actual


def _update_manifest(connection: sqlite3.Connection, authority: _SchemaAuthority) -> None:
    fingerprint = _schema_fingerprint(_sqlite_create_statements(authority))
    connection.execute(
        f'''UPDATE "{BOOTSTRAP_MANIFEST_TABLE}"
            SET schema_version=?, core_baseline=?, authority_artifact_id=?,
                authority_sha256=?, baseline_lock_sha256=?, physical_schema_sha256=?
            WHERE singleton=1''',
        (
            authority.schema_version,
            authority.core_baseline,
            CORE_MODEL_ARTIFACT_ID,
            authority.authority_sha256,
            authority.baseline_lock_sha256,
            fingerprint,
        ),
    )


def bootstrap_source_sqlite(path: Path) -> BootstrapVerification:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        return _bootstrap_connection(connection, authority=source_authority(), file_backed=True)
    except (sqlite3.DatabaseError, BootstrapError) as exc:
        raise MigrationError("SOURCE_BOOTSTRAP_FAILED", str(exc)) from exc
    finally:
        connection.close()


def verify_source_sqlite(path: Path) -> BootstrapVerification:
    connection = sqlite3.connect(str(path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        return _verify_connection(
            connection,
            authority=source_authority(),
            expected_journal_mode="wal",
        )
    except (sqlite3.DatabaseError, BootstrapError) as exc:
        raise MigrationError("SOURCE_VERIFY_FAILED", str(exc)) from exc
    finally:
        connection.close()


def verify_target_sqlite(path: Path) -> BootstrapVerification:
    connection = sqlite3.connect(str(path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        return _verify_connection(
            connection,
            authority=target_authority(),
            expected_journal_mode="wal",
        )
    except (sqlite3.DatabaseError, BootstrapError) as exc:
        raise MigrationError("TARGET_VERIFY_FAILED", str(exc)) from exc
    finally:
        connection.close()


def upgrade_sqlite(path: Path) -> BootstrapVerification:
    source, target = source_authority(), target_authority()
    statements = dict(zip(target.tables, _sqlite_create_statements(target), strict=True))
    connection = sqlite3.connect(str(path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        _verify_connection(connection, authority=source, expected_journal_mode="wal")
        connection.execute("BEGIN IMMEDIATE")
        for name in new_relation_names():
            connection.execute(statements[name])
        _update_manifest(connection, target)
        connection.commit()
        return _verify_connection(connection, authority=target, expected_journal_mode="wal")
    except (sqlite3.DatabaseError, BootstrapError, MigrationError) as exc:
        connection.rollback()
        if isinstance(exc, MigrationError):
            raise
        raise MigrationError("UPGRADE_FAILED", str(exc)) from exc
    finally:
        connection.close()


def downgrade_sqlite(path: Path) -> BootstrapVerification:
    source, target = source_authority(), target_authority()
    connection = sqlite3.connect(str(path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        _verify_connection(connection, authority=target, expected_journal_mode="wal")
        for name in reversed(new_relation_names()):
            count = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            if int(count) != 0:
                raise MigrationError("DOWNGRADE_NONEMPTY", f"relation={name}")
        connection.execute("BEGIN IMMEDIATE")
        for name in reversed(new_relation_names()):
            connection.execute(f'DROP TABLE "{name}"')
        _update_manifest(connection, source)
        connection.commit()
        return _verify_connection(connection, authority=source, expected_journal_mode="wal")
    except MigrationError:
        connection.rollback()
        raise
    except (sqlite3.DatabaseError, BootstrapError) as exc:
        connection.rollback()
        raise MigrationError("DOWNGRADE_FAILED", str(exc)) from exc
    finally:
        connection.close()


__all__ = [
    "MigrationError",
    "NEW_RELATIONS",
    "SOURCE_DB_SCHEMA_VERSION",
    "TARGET_DB_SCHEMA_VERSION",
    "bootstrap_source_sqlite",
    "downgrade_sqlite",
    "new_relation_names",
    "upgrade_sqlite",
    "verify_source_sqlite",
    "verify_target_sqlite",
]
