"""Fail-closed DB 1.6.0 clean-bootstrap kernel.

The logical schema remains owned by the frozen ``CORE_LOGICAL_MODEL`` Canonical
artifact.  This module only projects that authority into a concrete engine DDL
and records/verifies bootstrap provenance.
"""

from __future__ import annotations

import hashlib
import heapq
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tpaa_canonical.loader import ArtifactExpectation, CanonicalArtifactLoader

EXPECTED_DB_SCHEMA_VERSION = "1.6.0"
CORE_MODEL_ARTIFACT_ID = "CORE_LOGICAL_MODEL"
BOOTSTRAP_MANIFEST_TABLE = "_tpaa_bootstrap_manifest"
SQLITE_ENGINE_PROFILE = "sqlite-desktop"
POSTGRES_ENGINE_PROFILE = "postgresql-service"
POSTGRES_MANIFEST_SCHEMA = "public"

_REFERENCE_RE = re.compile(
    r"\bREFERENCES\s+([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE
)
_WHITESPACE_RE = re.compile(r"\s+")

_SQLITE_TYPE_MAP: Mapping[str, str] = {
    "uuid": "TEXT",
    "text": "TEXT",
    "timestamptz": "TEXT",
    "bigint": "INTEGER",
    "integer": "INTEGER",
    "bigserial": "INTEGER",
    "double precision": "REAL",
    "jsonb": "TEXT",
    "char(64)": "TEXT",
    "text[]": "TEXT",
    "uuid[]": "TEXT",
    "boolean": "INTEGER",
    "date": "TEXT",
}


class BootstrapError(RuntimeError):
    """Deterministic engineering failure for DB bootstrap/readiness checks."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"DB_BOOTSTRAP_FAIL reason={reason} detail={detail}")


@dataclass(frozen=True)
class _SchemaAuthority:
    schema_version: str
    core_baseline: str
    authority_sha256: str
    baseline_lock_sha256: str
    tables: Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class BootstrapVerification:
    engine_profile: str
    schema_version: str
    core_baseline: str
    authority_artifact_id: str
    authority_sha256: str
    baseline_lock_sha256: str
    physical_schema_sha256: str
    table_count: int
    journal_mode: str
    catalog_schema_sha256: str | None = None


def _normalize_sql(sql: str) -> str:
    return _WHITESPACE_RE.sub(" ", sql.strip().rstrip(";")).strip()


def _schema_fingerprint(statements: Sequence[str]) -> str:
    payload = "\n".join(_normalize_sql(statement) for statement in statements).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_authority(loader: CanonicalArtifactLoader | None = None) -> _SchemaAuthority:
    canonical_loader = loader or CanonicalArtifactLoader()
    artifact = canonical_loader.load(
        CORE_MODEL_ARTIFACT_ID,
        expectation=ArtifactExpectation(
            schema_version=EXPECTED_DB_SCHEMA_VERSION,
            required_top_level_keys=(
                "authority_id",
                "core_baseline",
                "db_schema_version",
                "tables",
            ),
        ),
    )
    payload = artifact.payload
    authority_id = payload.get("authority_id")
    if authority_id != CORE_MODEL_ARTIFACT_ID:
        raise BootstrapError(
            "AUTHORITY_ID_MISMATCH",
            f"expected={CORE_MODEL_ARTIFACT_ID} actual={authority_id!r}",
        )
    schema_version = payload.get("db_schema_version")
    lock_schema_version = canonical_loader.baseline_metadata.get("db_schema")
    if schema_version != EXPECTED_DB_SCHEMA_VERSION or lock_schema_version != schema_version:
        raise BootstrapError(
            "SCHEMA_VERSION_MISMATCH",
            (
                f"expected={EXPECTED_DB_SCHEMA_VERSION} "
                f"core_model={schema_version!r} baseline_lock={lock_schema_version!r}"
            ),
        )
    core_baseline = payload.get("core_baseline")
    if not isinstance(core_baseline, str) or not core_baseline:
        raise BootstrapError("CORE_BASELINE_INVALID", f"actual={core_baseline!r}")
    tables = payload.get("tables")
    if not isinstance(tables, Mapping) or not tables:
        raise BootstrapError("TABLE_CATALOG_INVALID", "tables must be a non-empty object")
    for table_name, raw_table in tables.items():
        if not isinstance(table_name, str) or "." not in table_name:
            raise BootstrapError("TABLE_ID_INVALID", f"table={table_name!r}")
        if not isinstance(raw_table, Mapping):
            raise BootstrapError("TABLE_DECLARATION_INVALID", f"table={table_name}")
        if raw_table.get("schema_version") != schema_version:
            raise BootstrapError(
                "TABLE_SCHEMA_VERSION_MISMATCH",
                (
                    f"table={table_name} expected={schema_version} "
                    f"actual={raw_table.get('schema_version')!r}"
                ),
            )
        fields = raw_table.get("fields")
        if not isinstance(fields, list) or not fields:
            raise BootstrapError("FIELD_CATALOG_INVALID", f"table={table_name}")
        seen: set[str] = set()
        for raw_field in fields:
            if not isinstance(raw_field, Mapping):
                raise BootstrapError("FIELD_DECLARATION_INVALID", f"table={table_name}")
            field_name = raw_field.get("name")
            field_type = raw_field.get("type")
            field_sql = raw_field.get("sql")
            if not isinstance(field_name, str) or not field_name:
                raise BootstrapError("FIELD_NAME_INVALID", f"table={table_name}")
            if field_name in seen:
                raise BootstrapError(
                    "DUPLICATE_FIELD", f"table={table_name} field={field_name}"
                )
            seen.add(field_name)
            if not isinstance(field_type, str) or not field_type.strip():
                raise BootstrapError(
                    "FIELD_TYPE_INVALID",
                    f"table={table_name} field={field_name} type={field_type!r}",
                )
            if not isinstance(field_sql, str) or not field_sql.strip():
                raise BootstrapError(
                    "FIELD_SQL_INVALID", f"table={table_name} field={field_name}"
                )
    return _SchemaAuthority(
        schema_version=schema_version,
        core_baseline=core_baseline,
        authority_sha256=artifact.sha256,
        baseline_lock_sha256=artifact.baseline_lock_sha256,
        tables=tables,
    )


def _canonical_field_sql(table_name: str, raw_field: Mapping[str, Any]) -> str:
    field_name = str(raw_field["name"])
    field_type = str(raw_field["type"])
    raw_sql = str(raw_field["sql"])
    sql = raw_sql.split("--", 1)[0].strip().rstrip(",").strip()
    prefix = f"{field_name} {field_type}"
    if not sql.lower().startswith(prefix.lower()):
        raise BootstrapError(
            "FIELD_SQL_PREFIX_MISMATCH",
            f"table={table_name} field={field_name} sql={raw_sql!r}",
        )
    return sql


def _sqlite_field_sql(table_name: str, raw_field: Mapping[str, Any]) -> str:
    field_name = str(raw_field["name"])
    field_type = str(raw_field["type"])
    if field_type not in _SQLITE_TYPE_MAP:
        raise BootstrapError(
            "SQLITE_UNSUPPORTED_FIELD_TYPE",
            f"table={table_name} field={field_name} type={field_type!r}",
        )
    sql = _canonical_field_sql(table_name, raw_field)
    prefix = f"{field_name} {field_type}"
    suffix = sql[len(prefix) :]
    suffix = re.sub(r"\bDEFAULT\s+now\(\)", "DEFAULT CURRENT_TIMESTAMP", suffix, flags=re.I)
    suffix = re.sub(r"\bjsonb_typeof\s*\(", "json_type(", suffix, flags=re.I)
    suffix = _REFERENCE_RE.sub(lambda match: f'REFERENCES "{match.group(1)}"', suffix)
    return f'"{field_name}" {_SQLITE_TYPE_MAP[field_type]}{suffix}'


def _table_dependencies(authority: _SchemaAuthority) -> dict[str, set[str]]:
    dependencies: dict[str, set[str]] = {table_name: set() for table_name in authority.tables}
    for table_name, raw_table in authority.tables.items():
        raw_fields = raw_table["fields"]
        assert isinstance(raw_fields, list)
        for raw_field in raw_fields:
            field_sql = _canonical_field_sql(table_name, raw_field)
            for target in _REFERENCE_RE.findall(field_sql):
                if target not in authority.tables:
                    raise BootstrapError(
                        "REFERENCE_TARGET_MISSING",
                        f"table={table_name} target={target}",
                    )
                if target != table_name:
                    dependencies[table_name].add(target)
    return dependencies


def _postgres_table_order(authority: _SchemaAuthority) -> tuple[str, ...]:
    dependencies = _table_dependencies(authority)
    reverse: dict[str, set[str]] = {table_name: set() for table_name in authority.tables}
    for table_name, targets in dependencies.items():
        for target in targets:
            reverse[target].add(table_name)

    indegree = {table_name: len(targets) for table_name, targets in dependencies.items()}
    ready = [table_name for table_name, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        current = heapq.heappop(ready)
        order.append(current)
        for dependent in sorted(reverse[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, dependent)

    if len(order) != len(authority.tables):
        unresolved = sorted(table_name for table_name, degree in indegree.items() if degree > 0)
        raise BootstrapError("REFERENCE_CYCLE", f"tables={unresolved!r}")
    return tuple(order)


def _postgres_create_statements(authority: _SchemaAuthority) -> tuple[str, ...]:
    schemas = sorted({table_name.split(".", 1)[0] for table_name in authority.tables})
    statements = [f'CREATE SCHEMA IF NOT EXISTS "{schema}"' for schema in schemas]
    for table_name in _postgres_table_order(authority):
        raw_table = authority.tables[table_name]
        raw_fields = raw_table["fields"]
        assert isinstance(raw_fields, list)
        fields = [_canonical_field_sql(table_name, field) for field in raw_fields]
        schema_name, relation_name = table_name.split(".", 1)
        statements.append(
            f'CREATE TABLE "{schema_name}"."{relation_name}" (\n  '
            + ",\n  ".join(fields)
            + "\n)"
        )
    return tuple(statements)


def postgres_create_statements() -> tuple[str, ...]:
    """Project the frozen logical schema to deterministic PostgreSQL DDL statements."""

    return _postgres_create_statements(_load_authority())


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _postgres_manifest_qualified_name() -> str:
    return f'"{POSTGRES_MANIFEST_SCHEMA}"."{BOOTSTRAP_MANIFEST_TABLE}"'


def _postgres_manifest_create_statement() -> str:
    return f'''CREATE TABLE {_postgres_manifest_qualified_name()} (
  singleton integer PRIMARY KEY CHECK (singleton = 1),
  engine_profile text NOT NULL,
  schema_version text NOT NULL,
  core_baseline text NOT NULL,
  authority_artifact_id text NOT NULL,
  authority_sha256 text NOT NULL,
  baseline_lock_sha256 text NOT NULL,
  physical_schema_sha256 text NOT NULL,
  catalog_schema_sha256 text NOT NULL
)'''


def _postgres_catalog_lines_sql() -> str:
    """Return a stable PostgreSQL catalog projection for physical drift hashing."""

    return r'''SELECT line
FROM (
  SELECT 'SCHEMA|' || n.nspname AS line
  FROM pg_namespace n
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'

  UNION ALL

  SELECT 'REL|' || n.nspname || '|' || c.relname || '|' || c.relkind::text
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
    AND c.relkind IN ('r','p','v','m','S','i')

  UNION ALL

  SELECT 'COL|' || n.nspname || '|' || c.relname || '|' || a.attnum::text || '|'
         || a.attname || '|' || format_type(a.atttypid, a.atttypmod) || '|'
         || a.attnotnull::text || '|'
         || COALESCE(pg_get_expr(d.adbin, d.adrelid), '') || '|'
         || a.attidentity::text || '|' || a.attgenerated::text
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
    AND c.relkind IN ('r','p')
    AND a.attnum > 0 AND NOT a.attisdropped

  UNION ALL

  SELECT 'CON|' || n.nspname || '|' || c.relname || '|' || con.contype::text || '|'
         || pg_get_constraintdef(con.oid, true)
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'

  UNION ALL

  SELECT 'IDX|' || n.nspname || '|' || t.relname || '|'
         || regexp_replace(pg_get_indexdef(i.indexrelid), 'INDEX [^ ]+ ON ', 'INDEX ON ')
  FROM pg_index i
  JOIN pg_class t ON t.oid = i.indrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'

  UNION ALL

  SELECT 'TRG|' || n.nspname || '|' || c.relname || '|' || t.tgname || '|'
         || pg_get_triggerdef(t.oid, true)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE NOT t.tgisinternal
    AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'

  UNION ALL

  SELECT 'VIEW|' || n.nspname || '|' || c.relname || '|' || pg_get_viewdef(c.oid, true)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('v','m')
    AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'

  UNION ALL

  SELECT 'SEQ|' || n.nspname || '|' || c.relname || '|'
         || s.seqstart::text || '|' || s.seqincrement::text || '|'
         || s.seqmin::text || '|' || s.seqmax::text || '|' || s.seqcache::text || '|'
         || s.seqcycle::text
  FROM pg_sequence s
  JOIN pg_class c ON c.oid = s.seqrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
) AS catalog_lines
ORDER BY line'''


def _postgres_catalog_hash_query() -> str:
    lines = _postgres_catalog_lines_sql()
    return (
        "SELECT encode(sha256(convert_to(COALESCE(string_agg(line, E'\\n' ORDER BY line), ''), "
        "'UTF8')), 'hex') FROM (" + lines + ") AS snapshot"
    )


def _postgres_expected_user_schemas(authority: _SchemaAuthority) -> tuple[str, ...]:
    return tuple(sorted({table_name.split('.', 1)[0] for table_name in authority.tables}))


def _postgres_expected_tables(authority: _SchemaAuthority) -> tuple[str, ...]:
    return tuple(
        sorted((*authority.tables.keys(), f"{POSTGRES_MANIFEST_SCHEMA}.{BOOTSTRAP_MANIFEST_TABLE}"))
    )


def _postgres_target_empty_guard() -> str:
    return r'''DO $$
DECLARE
  objects text[];
BEGIN
  SELECT COALESCE(array_agg(n.nspname || '.' || c.relname ORDER BY n.nspname, c.relname), ARRAY[]::text[])
    INTO objects
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
    AND c.relkind IN ('r','p','v','m','S');
  IF objects <> ARRAY[]::text[] THEN
    RAISE EXCEPTION 'TPAA_TARGET_NOT_EMPTY objects=%', objects;
  END IF;
END $$'''


def _postgres_schema_inventory_guard(authority: _SchemaAuthority) -> str:
    expected_schemas = ', '.join(
        _sql_literal(value) for value in _postgres_expected_user_schemas(authority)
    )
    expected_tables = ', '.join(
        _sql_literal(value) for value in _postgres_expected_tables(authority)
    )
    return f'''DO $$
DECLARE
  actual_schemas text[];
  actual_tables text[];
BEGIN
  SELECT COALESCE(array_agg(nspname ORDER BY nspname), ARRAY[]::text[])
    INTO actual_schemas
  FROM pg_namespace
  WHERE nspname !~ '^pg_' AND nspname NOT IN ('information_schema', 'public');
  IF actual_schemas <> ARRAY[{expected_schemas}]::text[] THEN
    RAISE EXCEPTION 'TPAA_SCHEMA_INVENTORY_MISMATCH actual=%', actual_schemas;
  END IF;

  SELECT COALESCE(array_agg(n.nspname || '.' || c.relname ORDER BY n.nspname, c.relname), ARRAY[]::text[])
    INTO actual_tables
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
    AND c.relkind IN ('r','p');
  IF actual_tables <> ARRAY[{expected_tables}]::text[] THEN
    RAISE EXCEPTION 'TPAA_TABLE_INVENTORY_MISMATCH actual=%', actual_tables;
  END IF;
END $$'''


def postgres_bootstrap_script(*, fault_after_tables: int | None = None) -> str:
    """Build transactional PostgreSQL bootstrap SQL for an external psql client."""

    authority = _load_authority()
    create_statements = _postgres_create_statements(authority)
    projection_hash = _schema_fingerprint(create_statements)
    table_seen = 0
    statements: list[str] = [r"\set ON_ERROR_STOP on", "BEGIN", _postgres_target_empty_guard()]
    for statement in create_statements:
        statements.append(statement)
        if statement.startswith("CREATE TABLE"):
            table_seen += 1
            if fault_after_tables is not None and table_seen == fault_after_tables:
                statements.append("SELECT tpaa_intentional_bootstrap_fault()")
    statements.append(_postgres_manifest_create_statement())
    catalog_hash_query = _postgres_catalog_hash_query()
    statements.append(
        f'''INSERT INTO {_postgres_manifest_qualified_name()} (
  singleton, engine_profile, schema_version, core_baseline,
  authority_artifact_id, authority_sha256, baseline_lock_sha256,
  physical_schema_sha256, catalog_schema_sha256
)
SELECT 1, {_sql_literal(POSTGRES_ENGINE_PROFILE)}, {_sql_literal(authority.schema_version)},
       {_sql_literal(authority.core_baseline)}, {_sql_literal(CORE_MODEL_ARTIFACT_ID)},
       {_sql_literal(authority.authority_sha256)}, {_sql_literal(authority.baseline_lock_sha256)},
       {_sql_literal(projection_hash)}, ({catalog_hash_query})'''
    )
    statements.extend([_postgres_schema_inventory_guard(authority), "COMMIT"])
    meta_command, *sql_statements = statements
    return meta_command + "\n" + ";\n\n".join(sql_statements) + ";\n"


def postgres_verify_script() -> str:
    """Build read-only fail-closed PostgreSQL schema/provenance verification SQL."""

    authority = _load_authority()
    create_statements = _postgres_create_statements(authority)
    projection_hash = _schema_fingerprint(create_statements)
    catalog_hash_query = _postgres_catalog_hash_query()
    manifest = _postgres_manifest_qualified_name()
    return f'''\\set ON_ERROR_STOP on
BEGIN READ ONLY;

{_postgres_schema_inventory_guard(authority)};

DO $$
DECLARE
  manifest_count bigint;
  mismatch_count bigint;
BEGIN
  SELECT COUNT(*) INTO manifest_count FROM {manifest};
  IF manifest_count <> 1 THEN
    RAISE EXCEPTION 'TPAA_BOOTSTRAP_MANIFEST_CARDINALITY actual=%', manifest_count;
  END IF;

  SELECT COUNT(*) INTO mismatch_count
  FROM {manifest}
  WHERE singleton <> 1
     OR engine_profile <> {_sql_literal(POSTGRES_ENGINE_PROFILE)}
     OR schema_version <> {_sql_literal(authority.schema_version)}
     OR core_baseline <> {_sql_literal(authority.core_baseline)}
     OR authority_artifact_id <> {_sql_literal(CORE_MODEL_ARTIFACT_ID)}
     OR authority_sha256 <> {_sql_literal(authority.authority_sha256)}
     OR baseline_lock_sha256 <> {_sql_literal(authority.baseline_lock_sha256)}
     OR physical_schema_sha256 <> {_sql_literal(projection_hash)};
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'TPAA_BOOTSTRAP_MANIFEST_MISMATCH';
  END IF;
END $$;

DO $$
DECLARE
  expected_hash text;
  actual_hash text;
BEGIN
  SELECT catalog_schema_sha256 INTO expected_hash FROM {manifest} WHERE singleton = 1;
  actual_hash := ({catalog_hash_query});
  IF expected_hash IS NULL OR actual_hash <> expected_hash THEN
    RAISE EXCEPTION 'TPAA_PHYSICAL_SCHEMA_MISMATCH expected=% actual=%', expected_hash, actual_hash;
  END IF;
END $$;

SELECT engine_profile || '|' || schema_version || '|' || core_baseline || '|'
       || authority_artifact_id || '|' || authority_sha256 || '|'
       || baseline_lock_sha256 || '|' || physical_schema_sha256 || '|'
       || catalog_schema_sha256 || '|{len(authority.tables)}'
FROM {manifest}
WHERE singleton = 1;

ROLLBACK;
'''


def postgres_empty_check_script() -> str:
    """Return a psql script that emits the count of non-system user relations."""

    return r'''\set ON_ERROR_STOP on
SELECT COUNT(*)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
  AND c.relkind IN ('r','p','v','m','S');
'''


def _sqlite_create_statements(authority: _SchemaAuthority) -> tuple[str, ...]:
    statements: list[str] = []
    for table_name, raw_table in authority.tables.items():
        raw_fields = raw_table["fields"]
        assert isinstance(raw_fields, list)
        fields = [_sqlite_field_sql(table_name, field) for field in raw_fields]
        statements.append(f'CREATE TABLE "{table_name}" (\n  ' + ",\n  ".join(fields) + "\n)")
    return tuple(statements)


def _manifest_create_statement() -> str:
    return f'''CREATE TABLE "{BOOTSTRAP_MANIFEST_TABLE}" (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  engine_profile TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  core_baseline TEXT NOT NULL,
  authority_artifact_id TEXT NOT NULL,
  authority_sha256 TEXT NOT NULL,
  baseline_lock_sha256 TEXT NOT NULL,
  physical_schema_sha256 TEXT NOT NULL
)'''


def _user_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _unexpected_schema_objects(connection: sqlite3.Connection) -> tuple[tuple[str, str], ...]:
    rows = connection.execute(
        """SELECT type, name
           FROM sqlite_master
           WHERE name NOT LIKE 'sqlite_%'
             AND type IN ('view', 'trigger', 'index')
             AND sql IS NOT NULL
           ORDER BY type, name"""
    ).fetchall()
    return tuple((str(row[0]), str(row[1])) for row in rows)


def _configure_sqlite(
    connection: sqlite3.Connection, *, file_backed: bool, set_wal: bool
) -> str:
    connection.execute("PRAGMA foreign_keys = ON")
    row = connection.execute("PRAGMA foreign_keys").fetchone()
    if row is None or row[0] != 1:
        raise BootstrapError("SQLITE_FOREIGN_KEYS_DISABLED", "PRAGMA foreign_keys did not enable")
    journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    if file_backed and set_wal:
        journal_mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
        if journal_mode != "wal":
            raise BootstrapError(
                "SQLITE_WAL_UNAVAILABLE", f"expected=wal actual={journal_mode}"
            )
    return journal_mode


def _verify_connection(
    connection: sqlite3.Connection,
    *,
    authority: _SchemaAuthority,
    expected_journal_mode: str | None,
) -> BootstrapVerification:
    create_statements = _sqlite_create_statements(authority)
    expected_tables = {BOOTSTRAP_MANIFEST_TABLE, *authority.tables.keys()}
    actual_tables = set(_user_tables(connection))
    if actual_tables != expected_tables:
        missing = sorted(expected_tables - actual_tables)
        extra = sorted(actual_tables - expected_tables)
        raise BootstrapError(
            "TABLE_INVENTORY_MISMATCH", f"missing={missing} extra={extra}"
        )
    unexpected_objects = _unexpected_schema_objects(connection)
    if unexpected_objects:
        raise BootstrapError(
            "UNEXPECTED_SCHEMA_OBJECT",
            f"objects={list(unexpected_objects)!r}",
        )

    for table_name, expected_sql in zip(authority.tables, create_statements, strict=True):
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        if row is None or not isinstance(row[0], str):
            raise BootstrapError("TABLE_DDL_MISSING", f"table={table_name}")
        if _normalize_sql(row[0]) != _normalize_sql(expected_sql):
            raise BootstrapError("TABLE_DDL_MISMATCH", f"table={table_name}")

    expected_fingerprint = _schema_fingerprint(create_statements)
    row = connection.execute(
        f'''SELECT engine_profile, schema_version, core_baseline, authority_artifact_id,
                   authority_sha256, baseline_lock_sha256, physical_schema_sha256
            FROM "{BOOTSTRAP_MANIFEST_TABLE}" WHERE singleton = 1'''
    ).fetchone()
    if row is None:
        raise BootstrapError("BOOTSTRAP_MANIFEST_MISSING", "singleton row is absent")
    expected_manifest = (
        SQLITE_ENGINE_PROFILE,
        authority.schema_version,
        authority.core_baseline,
        CORE_MODEL_ARTIFACT_ID,
        authority.authority_sha256,
        authority.baseline_lock_sha256,
        expected_fingerprint,
    )
    if tuple(row) != expected_manifest:
        raise BootstrapError(
            "BOOTSTRAP_MANIFEST_MISMATCH",
            f"expected={expected_manifest!r} actual={tuple(row)!r}",
        )
    count = connection.execute(
        f'SELECT COUNT(*) FROM "{BOOTSTRAP_MANIFEST_TABLE}"'
    ).fetchone()
    if count is None or count[0] != 1:
        raise BootstrapError("BOOTSTRAP_MANIFEST_CARDINALITY", f"actual={count!r}")

    journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    if expected_journal_mode is not None and journal_mode != expected_journal_mode:
        raise BootstrapError(
            "SQLITE_JOURNAL_MODE_MISMATCH",
            f"expected={expected_journal_mode} actual={journal_mode}",
        )
    return BootstrapVerification(
        engine_profile=SQLITE_ENGINE_PROFILE,
        schema_version=authority.schema_version,
        core_baseline=authority.core_baseline,
        authority_artifact_id=CORE_MODEL_ARTIFACT_ID,
        authority_sha256=authority.authority_sha256,
        baseline_lock_sha256=authority.baseline_lock_sha256,
        physical_schema_sha256=expected_fingerprint,
        table_count=len(authority.tables),
        journal_mode=journal_mode,
    )


def _bootstrap_connection(
    connection: sqlite3.Connection,
    *,
    authority: _SchemaAuthority,
    file_backed: bool,
) -> BootstrapVerification:
    journal_mode = _configure_sqlite(connection, file_backed=file_backed, set_wal=True)
    existing = _user_tables(connection)
    existing_objects = _unexpected_schema_objects(connection)
    if existing or existing_objects:
        raise BootstrapError(
            "TARGET_NOT_EMPTY",
            f"existing_tables={list(existing)!r} existing_objects={list(existing_objects)!r}",
        )
    create_statements = _sqlite_create_statements(authority)
    fingerprint = _schema_fingerprint(create_statements)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(_manifest_create_statement())
        for statement in create_statements:
            connection.execute(statement)
        connection.execute(
            f'''INSERT INTO "{BOOTSTRAP_MANIFEST_TABLE}" (
                   singleton, engine_profile, schema_version, core_baseline,
                   authority_artifact_id, authority_sha256, baseline_lock_sha256,
                   physical_schema_sha256
               ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)''',
            (
                SQLITE_ENGINE_PROFILE,
                authority.schema_version,
                authority.core_baseline,
                CORE_MODEL_ARTIFACT_ID,
                authority.authority_sha256,
                authority.baseline_lock_sha256,
                fingerprint,
            ),
        )
        verification = _verify_connection(
            connection,
            authority=authority,
            expected_journal_mode=journal_mode,
        )
        connection.commit()
        return verification
    except Exception:
        connection.rollback()
        raise


def bootstrap_sqlite(path: str | Path) -> BootstrapVerification:
    """Bootstrap an empty SQLite database to the exact frozen schema authority."""

    authority = _load_authority()
    db_path = Path(path)
    file_backed = str(path) != ":memory:"
    if file_backed:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        return _bootstrap_connection(connection, authority=authority, file_backed=file_backed)
    except sqlite3.DatabaseError as exc:
        raise BootstrapError("SQLITE_DATABASE_ERROR", str(exc)) from exc
    finally:
        connection.close()


def verify_sqlite(path: str | Path) -> BootstrapVerification:
    """Verify schema/version/provenance for an existing SQLite bootstrap."""

    authority = _load_authority()
    if str(path) == ":memory:":
        raise BootstrapError("VERIFY_TARGET_INVALID", "verify requires a persistent SQLite database")
    db_path = Path(path)
    if not db_path.is_file():
        raise BootstrapError("TARGET_DB_MISSING", f"path={db_path}")
    connection = sqlite3.connect(str(db_path))
    try:
        _configure_sqlite(connection, file_backed=True, set_wal=False)
        expected_journal = "wal"
        return _verify_connection(
            connection,
            authority=authority,
            expected_journal_mode=expected_journal,
        )
    except sqlite3.DatabaseError as exc:
        raise BootstrapError("SQLITE_DATABASE_ERROR", str(exc)) from exc
    finally:
        connection.close()
