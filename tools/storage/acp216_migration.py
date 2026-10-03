"""ACP-216 governed DB 1.6.0 -> 1.7.0 migration primitives.

The current Canonical model remains the target authority. The exact pre-adoption
CORE_LOGICAL_MODEL bytes are retained only as a historical migration source
snapshot; they are never treated as current authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tpaa_storage.bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    CORE_MODEL_ARTIFACT_ID,
    POSTGRES_ENGINE_PROFILE,
    BootstrapError,
    BootstrapVerification,
    _SchemaAuthority,
    _bootstrap_connection,
    _configure_sqlite,
    _load_authority,
    _postgres_catalog_hash_query,
    _postgres_create_statements,
    _postgres_manifest_create_statement,
    _postgres_manifest_qualified_name,
    _postgres_schema_inventory_guard,
    _postgres_target_empty_guard,
    _schema_fingerprint,
    _sql_literal,
    _sqlite_create_statements,
    _verify_connection,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_CORE = ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_6_0.json"
SOURCE_CORE_SHA256 = "cfde6638e6899167267375c899bff2f04a490ce12f32e0005be4e15dda956245"
SOURCE_LOCK_SHA256 = "9920b59601d8441f883879e813164f33ee5c02db81aa5e1b759e3a1772469e51"
SOURCE_DB_SCHEMA_VERSION = "1.6.0"
TARGET_DB_SCHEMA_VERSION = "1.7.0"
NEW_RELATIONS: tuple[str, ...] = (
    "capability.adjusted_capability_estimate_revision",
    "assessment.attribution_run_request_binding",
    "registry.mutation_idempotency",
    "assessment.p4_subject_context",
    "assessment.actor_assessment_revision",
    "assessment.actor_assessment_annotation_ref",
    "assessment.p5_composition_snapshot",
    "assessment.p5_composition_participant",
    "assessment.mission_assessment_revision",
    "intelligence.forecast_request",
    "capability.p6_model_revision",
    "intelligence.forecast_result_revision",
    "intelligence.counterfactual_request",
    "intelligence.counterfactual_revision",
    "intelligence.training_recommendation_revision",
)


class MigrationError(RuntimeError):
    """Fail-closed ACP-216 migration error."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"ACP216_MIGRATION_FAIL reason={reason} detail={detail}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def historical_authority() -> _SchemaAuthority:
    raw = SOURCE_CORE.read_bytes()
    actual_hash = _sha256_bytes(raw)
    if actual_hash != SOURCE_CORE_SHA256:
        raise MigrationError(
            "SOURCE_AUTHORITY_HASH_MISMATCH",
            f"expected={SOURCE_CORE_SHA256} actual={actual_hash}",
        )
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise MigrationError("SOURCE_AUTHORITY_INVALID", "root must be an object")
    if payload.get("db_schema_version") != SOURCE_DB_SCHEMA_VERSION:
        raise MigrationError(
            "SOURCE_SCHEMA_VERSION_MISMATCH",
            f"actual={payload.get('db_schema_version')!r}",
        )
    tables_raw = payload.get("tables")
    if not isinstance(tables_raw, dict) or not tables_raw:
        raise MigrationError("SOURCE_TABLES_INVALID", "tables must be non-empty")
    tables: dict[str, Mapping[str, Any]] = {}
    for name, raw_table in tables_raw.items():
        if not isinstance(name, str) or not isinstance(raw_table, dict):
            raise MigrationError("SOURCE_TABLE_INVALID", f"table={name!r}")
        tables[name] = raw_table
    core_baseline = payload.get("core_baseline")
    if not isinstance(core_baseline, str) or not core_baseline:
        raise MigrationError("SOURCE_CORE_BASELINE_INVALID", f"actual={core_baseline!r}")
    return _SchemaAuthority(
        schema_version=SOURCE_DB_SCHEMA_VERSION,
        core_baseline=core_baseline,
        authority_sha256=SOURCE_CORE_SHA256,
        baseline_lock_sha256=SOURCE_LOCK_SHA256,
        tables=tables,
    )


def target_authority() -> _SchemaAuthority:
    authority = _load_authority()
    if authority.schema_version != TARGET_DB_SCHEMA_VERSION:
        raise MigrationError(
            "TARGET_SCHEMA_VERSION_MISMATCH",
            f"actual={authority.schema_version}",
        )
    return authority


def new_relation_names() -> tuple[str, ...]:
    source = historical_authority()
    target = target_authority()
    actual = tuple(name for name in target.tables if name not in source.tables)
    if actual != NEW_RELATIONS:
        raise MigrationError(
            "NEW_RELATION_INVENTORY_MISMATCH",
            f"expected={NEW_RELATIONS!r} actual={actual!r}",
        )
    return actual


def bootstrap_historical_sqlite(path: Path) -> BootstrapVerification:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        return _bootstrap_connection(
            connection,
            authority=historical_authority(),
            file_backed=True,
        )
    except sqlite3.DatabaseError as exc:
        raise MigrationError("SQLITE_SOURCE_BOOTSTRAP_FAILED", str(exc)) from exc
    finally:
        connection.close()


def verify_historical_sqlite(path: Path) -> BootstrapVerification:
    connection = sqlite3.connect(str(path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        return _verify_connection(
            connection,
            authority=historical_authority(),
            expected_journal_mode="wal",
        )
    except (sqlite3.DatabaseError, BootstrapError) as exc:
        raise MigrationError("SQLITE_SOURCE_VERIFY_FAILED", str(exc)) from exc
    finally:
        connection.close()


def _update_sqlite_manifest(
    connection: sqlite3.Connection,
    authority: _SchemaAuthority,
) -> None:
    fingerprint = _schema_fingerprint(_sqlite_create_statements(authority))
    connection.execute(
        f"""UPDATE "{BOOTSTRAP_MANIFEST_TABLE}"
            SET schema_version=?,
                core_baseline=?,
                authority_artifact_id=?,
                authority_sha256=?,
                baseline_lock_sha256=?,
                physical_schema_sha256=?
            WHERE singleton=1""",
        (
            authority.schema_version,
            authority.core_baseline,
            CORE_MODEL_ARTIFACT_ID,
            authority.authority_sha256,
            authority.baseline_lock_sha256,
            fingerprint,
        ),
    )


def upgrade_sqlite(path: Path) -> BootstrapVerification:
    source = historical_authority()
    target = target_authority()
    names = new_relation_names()
    statements = dict(
        zip(target.tables, _sqlite_create_statements(target), strict=True)
    )
    connection = sqlite3.connect(str(path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        _verify_connection(
            connection,
            authority=source,
            expected_journal_mode="wal",
        )
        connection.execute("BEGIN IMMEDIATE")
        for name in names:
            connection.execute(statements[name])
        _update_sqlite_manifest(connection, target)
        connection.commit()
        return _verify_connection(
            connection,
            authority=target,
            expected_journal_mode="wal",
        )
    except (sqlite3.DatabaseError, BootstrapError) as exc:
        connection.rollback()
        raise MigrationError("SQLITE_UPGRADE_FAILED", str(exc)) from exc
    finally:
        connection.close()


def downgrade_sqlite(path: Path) -> BootstrapVerification:
    source = historical_authority()
    target = target_authority()
    names = new_relation_names()
    connection = sqlite3.connect(str(path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        _verify_connection(
            connection,
            authority=target,
            expected_journal_mode="wal",
        )
        nonempty: list[str] = []
        for name in names:
            row = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()
            if row is None or int(row[0]) != 0:
                nonempty.append(name)
        if nonempty:
            raise MigrationError(
                "DOWNGRADE_BLOCKED_NONEMPTY_RELATION",
                f"relations={nonempty!r}",
            )
        connection.execute("BEGIN IMMEDIATE")
        for name in reversed(names):
            connection.execute(f'DROP TABLE "{name}"')
        _update_sqlite_manifest(connection, source)
        connection.commit()
        return _verify_connection(
            connection,
            authority=source,
            expected_journal_mode="wal",
        )
    except MigrationError:
        connection.rollback()
        raise
    except (sqlite3.DatabaseError, BootstrapError) as exc:
        connection.rollback()
        raise MigrationError("SQLITE_DOWNGRADE_FAILED", str(exc)) from exc
    finally:
        connection.close()


def _render_psql(statements: list[str]) -> str:
    meta, *sql = statements
    return meta + "\n" + ";\n\n".join(sql) + ";\n"


def _postgres_manifest_guard(authority: _SchemaAuthority) -> str:
    manifest = _postgres_manifest_qualified_name()
    return f"""DO $$
DECLARE
  mismatch_count bigint;
BEGIN
  SELECT COUNT(*) INTO mismatch_count
  FROM {manifest}
  WHERE singleton <> 1
     OR engine_profile <> {_sql_literal(POSTGRES_ENGINE_PROFILE)}
     OR schema_version <> {_sql_literal(authority.schema_version)}
     OR core_baseline <> {_sql_literal(authority.core_baseline)}
     OR authority_artifact_id <> {_sql_literal(CORE_MODEL_ARTIFACT_ID)}
     OR authority_sha256 <> {_sql_literal(authority.authority_sha256)}
     OR baseline_lock_sha256 <> {_sql_literal(authority.baseline_lock_sha256)}
     OR physical_schema_sha256 <> {_sql_literal(_schema_fingerprint(_postgres_create_statements(authority)))};
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'ACP216_MANIFEST_MISMATCH';
  END IF;
END $$"""


def _postgres_catalog_guard() -> str:
    manifest = _postgres_manifest_qualified_name()
    query = _postgres_catalog_hash_query()
    return f"""DO $$
DECLARE
  expected_hash text;
  actual_hash text;
BEGIN
  SELECT catalog_schema_sha256 INTO expected_hash
  FROM {manifest} WHERE singleton = 1;
  actual_hash := ({query});
  IF expected_hash IS NULL OR actual_hash <> expected_hash THEN
    RAISE EXCEPTION 'ACP216_CATALOG_MISMATCH expected=% actual=%',
      expected_hash, actual_hash;
  END IF;
END $$"""


def _postgres_table_map(authority: _SchemaAuthority) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r'^CREATE TABLE "([^"]+)"\."([^"]+)"')
    for statement in _postgres_create_statements(authority):
        if not statement.startswith("CREATE TABLE"):
            continue
        match = pattern.match(statement)
        if match is None:
            raise MigrationError(
                "POSTGRES_CREATE_PARSE_FAILED",
                statement.splitlines()[0],
            )
        result[f"{match.group(1)}.{match.group(2)}"] = statement
    return result


def historical_postgres_bootstrap_script() -> str:
    authority = historical_authority()
    create_statements = _postgres_create_statements(authority)
    projection_hash = _schema_fingerprint(create_statements)
    statements = [
        r"\set ON_ERROR_STOP on",
        "BEGIN",
        _postgres_target_empty_guard(),
        *create_statements,
        _postgres_manifest_create_statement(),
        f"""INSERT INTO {_postgres_manifest_qualified_name()} (
  singleton, engine_profile, schema_version, core_baseline,
  authority_artifact_id, authority_sha256, baseline_lock_sha256,
  physical_schema_sha256, catalog_schema_sha256
)
SELECT 1, {_sql_literal(POSTGRES_ENGINE_PROFILE)},
       {_sql_literal(authority.schema_version)},
       {_sql_literal(authority.core_baseline)},
       {_sql_literal(CORE_MODEL_ARTIFACT_ID)},
       {_sql_literal(authority.authority_sha256)},
       {_sql_literal(authority.baseline_lock_sha256)},
       {_sql_literal(projection_hash)},
       ({_postgres_catalog_hash_query()})""",
        _postgres_schema_inventory_guard(authority),
        "COMMIT",
    ]
    return _render_psql(statements)


def historical_postgres_verify_script() -> str:
    authority = historical_authority()
    return _render_psql(
        [
            r"\set ON_ERROR_STOP on",
            "BEGIN READ ONLY",
            _postgres_schema_inventory_guard(authority),
            _postgres_manifest_guard(authority),
            _postgres_catalog_guard(),
            "COMMIT",
        ]
    )


def postgres_upgrade_script() -> str:
    source = historical_authority()
    target = target_authority()
    names = new_relation_names()
    table_map = _postgres_table_map(target)
    statements = [
        r"\set ON_ERROR_STOP on",
        "BEGIN",
        _postgres_schema_inventory_guard(source),
        _postgres_manifest_guard(source),
        _postgres_catalog_guard(),
    ]
    statements.extend(table_map[name] for name in names)
    statements.append(
        f"""UPDATE {_postgres_manifest_qualified_name()}
SET schema_version={_sql_literal(target.schema_version)},
    core_baseline={_sql_literal(target.core_baseline)},
    authority_artifact_id={_sql_literal(CORE_MODEL_ARTIFACT_ID)},
    authority_sha256={_sql_literal(target.authority_sha256)},
    baseline_lock_sha256={_sql_literal(target.baseline_lock_sha256)},
    physical_schema_sha256={_sql_literal(_schema_fingerprint(_postgres_create_statements(target)))},
    catalog_schema_sha256=({_postgres_catalog_hash_query()})
WHERE singleton=1"""
    )
    statements.extend(
        [
            _postgres_schema_inventory_guard(target),
            _postgres_catalog_guard(),
            "COMMIT",
        ]
    )
    return _render_psql(statements)


def postgres_downgrade_script() -> str:
    source = historical_authority()
    target = target_authority()
    names = new_relation_names()
    guards = "\n".join(
        (
            f"  IF EXISTS (SELECT 1 FROM \"{name.split('.', 1)[0]}\"."
            f"\"{name.split('.', 1)[1]}\" LIMIT 1) THEN\n"
            f"    RAISE EXCEPTION 'ACP216_DOWNGRADE_NONEMPTY relation={name}';\n"
            "  END IF;"
        )
        for name in names
    )
    statements = [
        r"\set ON_ERROR_STOP on",
        "BEGIN",
        _postgres_schema_inventory_guard(target),
        _postgres_manifest_guard(target),
        _postgres_catalog_guard(),
        f"""DO $$
BEGIN
{guards}
END $$""",
    ]
    for name in reversed(names):
        schema, relation = name.split(".", 1)
        statements.append(f'DROP TABLE "{schema}"."{relation}"')
    statements.append(
        f"""UPDATE {_postgres_manifest_qualified_name()}
SET schema_version={_sql_literal(source.schema_version)},
    core_baseline={_sql_literal(source.core_baseline)},
    authority_artifact_id={_sql_literal(CORE_MODEL_ARTIFACT_ID)},
    authority_sha256={_sql_literal(source.authority_sha256)},
    baseline_lock_sha256={_sql_literal(source.baseline_lock_sha256)},
    physical_schema_sha256={_sql_literal(_schema_fingerprint(_postgres_create_statements(source)))},
    catalog_schema_sha256=({_postgres_catalog_hash_query()})
WHERE singleton=1"""
    )
    statements.extend(
        [
            _postgres_schema_inventory_guard(source),
            _postgres_catalog_guard(),
            "COMMIT",
        ]
    )
    return _render_psql(statements)
