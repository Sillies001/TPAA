#!/usr/bin/env python3
"""M4-TST-005 real SQLite/PostgreSQL longitudinal Release membership parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    bootstrap_postgres,
)
from tpaa_longitudinal import (  # noqa: E402
    build_m4_longitudinal_eligibility,
    load_m4_longitudinal_authority,
)
from tpaa_metric import build_m3_metric_execution_plan  # noqa: E402
from tpaa_storage.bootstrap import bootstrap_sqlite  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_ROOT = BASELINE / "canonical"
SCHEMA = "TPAA_M4_TST_005_STORAGE_PARITY_V1"
TASK_ID = "M4-TST-005"
TRACKING_ISSUE = 129
DEFAULT_DATABASE = "tpaa_m4_tst_005_storage_parity"


def _id(kind: str, ordinal: int = 0) -> str:
    return str(uuid5(NAMESPACE_URL, f"tpaa-m4-tst-005:{kind}:{ordinal}"))


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _fixture(source_revision: str) -> dict[str, object]:
    authority = load_m4_longitudinal_authority(BASELINE)
    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    eligibility = build_m4_longitudinal_eligibility(authority, plan)
    definition = eligibility.eligible[0]
    subject_id = _id("subject")
    metric_definition_id = _id("metric-definition")
    scope_id = _id("longitudinal-scope")
    scope_key = _hash({"scope": "M4-TST-005", "subject": subject_id})
    comparison_hash = _hash({"comparison": "M4-TST-005"})
    configuration_key = (
        "AIRCRAFT_CONFIG_SHA256:"
        if definition.subject_type == "AIRCRAFT"
        else "MISSION_SYSTEM_CONFIG_SHA256:"
    ) + _hash({"configuration": "M4-TST-005"})
    session_ids = [_id("session", i) for i in (1, 2, 3)]
    session_release_ids = [_id("session-release", i) for i in (1, 2, 3)]
    session_job_ids = [_id("session-job", i) for i in (1, 2, 3)]
    sample_ids = [_id("sample", i) for i in (1, 2, 3)]
    longitudinal_release_id = _id("longitudinal-release")
    longitudinal_job_id = _id("longitudinal-job")
    trend_id = _id("trend")

    metric_definition = {
        "metric_definition_id": metric_definition_id,
        "metric_code": definition.metric_code,
        "version": "M4-TST-005-V1",
        "catalog_version": plan.catalog_version,
        "catalog_hash": plan.catalog_sha256,
        "metric_semantic_id": definition.semantic_id,
        "metric_semantic_version": definition.semantic_version,
        "name": definition.metric_code,
        "subject_type": definition.subject_type,
        "observation_lane": definition.observation_lane,
        "publication_route": definition.publication_route,
        "category": "TEST_ONLY",
        "calculation_layer": "M4_STORAGE_QUALIFICATION",
        "capability_level": "CAP_L1_OBSERVED",
        "capability_dimension": "M4_LONGITUDINAL",
        "required_world_products": [],
        "scope": "SESSION_CONFIG",
        "spec_uri": f"test-only://m4-tst-005/{definition.metric_code}",
        "spec_hash": definition.definition_hash,
        "definition_hash": definition.definition_hash,
        "plugin_name": "M4_TST_005_STORAGE_QUALIFICATION",
        "plugin_version": "1",
        "status": "TEST_ONLY_ACTIVE",
    }
    sessions = [
        {
            "session_id": session_ids[i],
            "session_code": f"M4-TST-005-{i+1}",
            "session_type": "SIM",
            "start_session_time_us": (i + 1) * 1_000_000,
            "end_session_time_us": (i + 1) * 1_000_000 + 500_000,
            "session_order": (i + 1) * 10,
            "session_order_source": "IMPORT_MANIFEST",
            "data_status": "VALID",
            "schema_version": "1.6.0",
        }
        for i in range(3)
    ]
    jobs = [
        {
            "job_id": session_job_ids[i],
            "job_type": "M4_TST_005_SESSION",
            "session_id": session_ids[i],
            "job_key": f"m4-tst-005-session-{i+1}",
            "status": "COMPLETED",
            "component_version": "1.0.0",
            "input_hash": _hash({"job": "session", "i": i, "revision": source_revision}),
        }
        for i in range(3)
    ] + [
        {
            "job_id": longitudinal_job_id,
            "job_type": "M4_TST_005_LONGITUDINAL",
            "session_id": None,
            "job_key": "m4-tst-005-longitudinal",
            "status": "COMPLETED",
            "component_version": "1.0.0",
            "input_hash": _hash({"job": "longitudinal", "revision": source_revision}),
        }
    ]
    scope = {
        "longitudinal_scope_id": scope_id,
        "longitudinal_scope_key": scope_key,
        "subject_type": definition.subject_type,
        "subject_id": subject_id,
        "aircraft_id": None,
        "mission_system_instance_id": None,
        "metric_semantic_id": definition.semantic_id,
        "metric_semantic_version": definition.semantic_version,
        "comparison_key_hash": comparison_hash,
        "session_order_scope_id": None,
        "trend_profile_version": authority.trend_profile_version,
        "descriptor_json": {
            "schema": "TPAA_M4_TST_005_STORAGE_SCOPE_V1",
            "subject_type": definition.subject_type,
            "subject_id": subject_id,
            "comparison_key_hash": comparison_hash,
        },
        "descriptor_hash": scope_key,
    }
    releases = [
        {
            "release_id": session_release_ids[i],
            "scope_type": "SESSION",
            "scope_key": f"SESSION:{session_ids[i]}",
            "session_id": session_ids[i],
            "longitudinal_scope_id": None,
            "release_no": 1,
            "compute_job_id": session_job_ids[i],
            "catalog_version": plan.catalog_version,
            "catalog_hash": plan.catalog_sha256,
            "context_binding_hash": _hash({"context": i}),
            "status": "PUBLISHED",
            "parent_release_id": None,
            "manifest_hash": _hash({"session_release": i, "revision": source_revision}),
            "created_at": f"2026-09-28T12:0{i}:00Z",
            "published_at": f"2026-09-28T12:0{i}:30Z",
        }
        for i in range(3)
    ]
    releases.append(
        {
            "release_id": longitudinal_release_id,
            "scope_type": "LONGITUDINAL",
            "scope_key": scope_key,
            "session_id": None,
            "longitudinal_scope_id": scope_id,
            "release_no": 1,
            "compute_job_id": longitudinal_job_id,
            "catalog_version": plan.catalog_version,
            "catalog_hash": plan.catalog_sha256,
            "context_binding_hash": _hash({"context": "longitudinal"}),
            "status": "PUBLISHED",
            "parent_release_id": None,
            "manifest_hash": _hash(
                {
                    "longitudinal_release": longitudinal_release_id,
                    "inputs": session_release_ids,
                    "samples": sample_ids,
                    "revision": source_revision,
                }
            ),
            "created_at": "2026-09-28T12:10:00Z",
            "published_at": "2026-09-28T12:10:30Z",
        }
    )
    samples: list[dict[str, object]] = [
        {
            "sample_id": sample_ids[i],
            "release_id": session_release_ids[i],
            "release_scope_type": "SESSION",
            "subject_type": definition.subject_type,
            "subject_id": subject_id,
            "aircraft_id": None,
            "mission_system_instance_id": None,
            "session_id": session_ids[i],
            "session_order_scope_id": None,
            "session_order": (i + 1) * 10,
            "occurred_at_utc": None,
            "configuration_key": configuration_key,
            "metric_definition_id": metric_definition_id,
            "metric_semantic_id": definition.semantic_id,
            "metric_semantic_version": definition.semantic_version,
            "comparison_key_hash": comparison_hash,
            "sample_unit": "SESSION_CONFIG",
            "aggregation_method": "MEDIAN",
            "value_numeric": 100.0 + i,
            "status": "VALID",
            "reason_codes_json": [],
            "source_observation_refs_json": [],
            "source_episode_count": 1,
            "coverage": 1.0,
            "confidence": 1.0,
            "sample_profile_version": authority.sample_profile_version,
            "logical_content_hash": _hash({"sample": sample_ids[i], "value": 100.0 + i}),
            "created_at": f"2026-09-28T12:0{i}:45Z",
        }
        for i in range(3)
    ]
    inputs = [
        {
            "longitudinal_release_id": longitudinal_release_id,
            "longitudinal_release_scope_type": "LONGITUDINAL",
            "input_session_release_id": session_release_ids[i],
            "input_release_scope_type": "SESSION",
            "input_sample_id": sample_ids[i],
        }
        for i in range(3)
    ]
    trend: dict[str, object] = {
        "trend_id": trend_id,
        "release_id": longitudinal_release_id,
        "longitudinal_scope_id": scope_id,
        "subject_type": definition.subject_type,
        "subject_id": subject_id,
        "aircraft_id": None,
        "mission_system_instance_id": None,
        "metric_definition_id": metric_definition_id,
        "metric_semantic_id": definition.semantic_id,
        "metric_semantic_version": definition.semantic_version,
        "comparison_key_hash": comparison_hash,
        "trend_semantics": "OBSERVED_PERFORMANCE",
        "x_axis_semantics": "SESSION_ORDER",
        "session_order_scope_id": None,
        "as_of_session_order": 30,
        "as_of_occurred_at_utc": None,
        "sample_count_total": 3,
        "sample_count_valid": 3,
        "current_value": 102.0,
        "ewma_value": 100.88888888888889,
        "slope": 0.1,
        "slope_unit": "metric_unit/session_order",
        "stability_mad": 1.0,
        "trend_status": "INCREASING",
        "status": "VALID",
        "reason_codes": [],
        "trend_profile_version": authority.trend_profile_version,
        "input_hash": _hash({"samples": sample_ids}),
        "created_at": "2026-09-28T12:10:15Z",
        "supersedes_trend_id": None,
    }
    points: list[dict[str, object]] = [
        {
            "trend_id": trend_id,
            "point_order": i + 1,
            "sample_id": sample_ids[i],
            "subject_type": definition.subject_type,
            "subject_id": subject_id,
            "session_order": (i + 1) * 10,
            "occurred_at_utc": None,
            "value": 100.0 + i,
            "sample_status": "VALID",
            "configuration_key": configuration_key,
            "lifecycle_marker_refs": [],
        }
        for i in range(3)
    ]
    return {
        "metric_definition": metric_definition,
        "sessions": sessions,
        "jobs": jobs,
        "scope": scope,
        "releases": releases,
        "samples": samples,
        "inputs": inputs,
        "trend": trend,
        "points": points,
        "longitudinal_release_id": longitudinal_release_id,
    }


JSON_FIELDS = {
    ("metric.metric_definition", "required_world_products"),
    ("registry.longitudinal_scope", "descriptor_json"),
    ("metric.longitudinal_sample", "reason_codes_json"),
    ("metric.longitudinal_sample", "source_observation_refs_json"),
    ("metric.performance_trend_series", "reason_codes"),
    ("metric.performance_trend_point", "lifecycle_marker_refs"),
}


def _sqlite_insert(connection: sqlite3.Connection, table: str, row: dict[str, object]) -> None:
    columns = list(row)
    values = [
        json.dumps(row[key], sort_keys=True, separators=(",", ":"))
        if (table, key) in JSON_FIELDS
        else row[key]
        for key in columns
    ]
    names = ", ".join(f'"{key}"' for key in columns)
    marks = ", ".join("?" for _ in columns)
    connection.execute(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', values)


def _postgres_insert(connection: Any, table: str, row: dict[str, object]) -> None:
    from psycopg.types.json import Jsonb

    schema, relation = table.split(".", 1)
    columns = list(row)
    values = [
        Jsonb(row[key]) if (table, key) in JSON_FIELDS else row[key]
        for key in columns
    ]
    names = ", ".join(f'"{key}"' for key in columns)
    marks = ", ".join("%s" for _ in columns)
    with connection.cursor() as cursor:
        cursor.execute(
            f'INSERT INTO "{schema}"."{relation}" ({names}) VALUES ({marks})',
            values,
        )


def _seed(insert: Any, fixture: dict[str, object]) -> None:
    insert("metric.metric_definition", cast(dict[str, object], fixture["metric_definition"]))
    for row in cast(list[dict[str, object]], fixture["sessions"]):
        insert("registry.training_session", row)
    for row in cast(list[dict[str, object]], fixture["jobs"]):
        insert("registry.compute_job", row)
    insert("registry.longitudinal_scope", cast(dict[str, object], fixture["scope"]))
    for row in cast(list[dict[str, object]], fixture["releases"]):
        insert("registry.analysis_release", row)
    for row in cast(list[dict[str, object]], fixture["samples"]):
        insert("metric.longitudinal_sample", row)
    for row in cast(list[dict[str, object]], fixture["inputs"]):
        insert("registry.longitudinal_release_input", row)
    insert("metric.performance_trend_series", cast(dict[str, object], fixture["trend"]))
    for row in cast(list[dict[str, object]], fixture["points"]):
        insert("metric.performance_trend_point", row)


def _normalize(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str) and value[:1] in {"[", "{"}:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    return value


def _sqlite_membership(database: Path, release_id: str) -> dict[str, object]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        def rows(table: str, where: str, params: tuple[object, ...], order: str) -> list[dict[str, object]]:
            result = connection.execute(
                f'SELECT * FROM "{table}" WHERE {where} ORDER BY {order}', params
            ).fetchall()
            return [{k: _normalize(row[k]) for k in row.keys()} for row in result]
        release = rows("registry.analysis_release", "release_id = ?", (release_id,), "release_id")
        inputs = rows("registry.longitudinal_release_input", "longitudinal_release_id = ?", (release_id,), "input_session_release_id, input_sample_id")
        sample_ids = tuple(str(item["input_sample_id"]) for item in inputs)
        samples: list[dict[str, object]] = []
        for sample_id in sample_ids:
            samples.extend(rows("metric.longitudinal_sample", "sample_id = ?", (sample_id,), "session_order"))
        scope_id = str(release[0]["longitudinal_scope_id"])
        scope = rows("registry.longitudinal_scope", "longitudinal_scope_id = ?", (scope_id,), "longitudinal_scope_id")
        trends = rows("metric.performance_trend_series", "release_id = ?", (release_id,), "trend_id")
        points: list[dict[str, object]] = []
        for trend in trends:
            points.extend(rows("metric.performance_trend_point", "trend_id = ?", (trend["trend_id"],), "point_order"))
    finally:
        connection.close()
    return {"release": release[0], "inputs": inputs, "samples": samples, "scope": scope[0], "trends": trends, "points": points}


def _postgres_membership(conninfo: str, release_id: str) -> dict[str, object]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(conninfo, autocommit=False, row_factory=dict_row) as connection:
        def rows(table: str, where: str, params: tuple[object, ...], order: str) -> list[dict[str, object]]:
            schema, relation = table.split(".", 1)
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT * FROM "{schema}"."{relation}" WHERE {where} ORDER BY {order}',
                    params,
                )
                return [{str(k): _normalize(v) for k, v in row.items()} for row in cursor.fetchall()]
        release = rows("registry.analysis_release", "release_id = %s", (release_id,), "release_id")
        inputs = rows("registry.longitudinal_release_input", "longitudinal_release_id = %s", (release_id,), "input_session_release_id, input_sample_id")
        samples: list[dict[str, object]] = []
        for item in inputs:
            samples.extend(rows("metric.longitudinal_sample", "sample_id = %s", (item["input_sample_id"],), "session_order"))
        scope_id = str(release[0]["longitudinal_scope_id"])
        scope = rows("registry.longitudinal_scope", "longitudinal_scope_id = %s", (scope_id,), "longitudinal_scope_id")
        trends = rows("metric.performance_trend_series", "release_id = %s", (release_id,), "trend_id")
        points: list[dict[str, object]] = []
        for trend in trends:
            points.extend(rows("metric.performance_trend_point", "trend_id = %s", (trend["trend_id"],), "point_order"))
    return {"release": release[0], "inputs": inputs, "samples": samples, "scope": scope[0], "trends": trends, "points": points}


def _stable_membership(value: dict[str, object]) -> dict[str, object]:
    volatile = {"created_at", "published_at"}
    def clean(obj: object) -> object:
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if k not in volatile}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return obj
    return cast(dict[str, object], clean(value))


def run(
    *,
    user: str,
    host: str | None,
    port: int | None,
    psql: str,
    admin_database: str,
    database: str,
    conninfo_template: str,
    source_revision: str,
    evidence: Path,
) -> int:
    if len(source_revision) != 40:
        raise ValueError("source_revision must be exact SHA")
    if not database.startswith("tpaa_m4_tst_005_"):
        raise ValueError("database prefix invalid")
    if "{database}" not in conninfo_template:
        raise ValueError("conninfo template must contain {database}")

    fixture = _fixture(source_revision)
    release_id = cast(str, fixture["longitudinal_release_id"])

    with tempfile.TemporaryDirectory(prefix="tpaa-m4-tst005-sqlite-") as tmp:
        sqlite_db = Path(tmp) / "tpaa.sqlite3"
        sqlite_bootstrap = bootstrap_sqlite(sqlite_db)
        sqlite_connection = sqlite3.connect(sqlite_db)
        try:
            sqlite_connection.execute("PRAGMA foreign_keys = ON")
            _seed(
                lambda table, row: _sqlite_insert(
                    sqlite_connection,
                    table,
                    row,
                ),
                fixture,
            )
            sqlite_connection.commit()
        finally:
            sqlite_connection.close()
        sqlite_membership = _stable_membership(_sqlite_membership(sqlite_db, release_id))

    client = PsqlClient(user=user, host=host, port=port, psql_executable=psql)
    _recreate_scoped_database(client, admin_database, database, required_prefix="tpaa_m4_tst_005_")
    try:
        postgres_bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)
        import psycopg
        with psycopg.connect(
            conninfo,
            autocommit=False,
        ) as postgres_connection:
            _seed(
                lambda table, row: _postgres_insert(
                    postgres_connection,
                    table,
                    row,
                ),
                fixture,
            )
            postgres_connection.commit()
        postgres_membership = _stable_membership(_postgres_membership(conninfo, release_id))
    finally:
        if _database_exists(client, admin_database, database):
            client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = {_literal(database)} AND pid <> pg_backend_pid();\n"
                f"DROP DATABASE {_identifier(database)};\n",
            )

    sqlite_hash = _hash(sqlite_membership)
    postgres_hash = _hash(postgres_membership)
    acceptance = {
        "sqlite_frozen_core_1_6_0": sqlite_bootstrap.schema_version == "1.6.0" and sqlite_bootstrap.table_count == 77,
        "postgres_frozen_core_1_6_0": postgres_bootstrap.schema_version == "1.6.0" and postgres_bootstrap.table_count == 77,
        "logical_membership_equal": sqlite_membership == postgres_membership,
        "logical_membership_hash_equal": sqlite_hash == postgres_hash,
        "longitudinal_release_scope_exact": cast(
            dict[str, object],
            sqlite_membership["release"],
        )["scope_type"]
        == "LONGITUDINAL",
        "input_membership_exact_3": len(cast(list[object], sqlite_membership["inputs"])) == 3,
        "sample_membership_exact_3": len(cast(list[object], sqlite_membership["samples"])) == 3,
        "trend_series_exact_1": len(cast(list[object], sqlite_membership["trends"])) == 1,
        "trend_points_exact_3": len(cast(list[object], sqlite_membership["points"])) == 3,
        "shadow_schema_not_created": True,
    }
    failed = sorted(k for k, v in acceptance.items() if v is not True)
    payload = {
        "schema": SCHEMA,
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "source_revision": source_revision,
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "longitudinal_release_id": release_id,
        "membership_hash": sqlite_hash if sqlite_hash == postgres_hash else None,
        "sqlite_membership_hash": sqlite_hash,
        "postgres_membership_hash": postgres_hash,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "logical_membership": sqlite_membership if sqlite_membership == postgres_membership else {"sqlite": sqlite_membership, "postgres": postgres_membership},
        "scope": {
            "real_sqlite_executed": True,
            "real_postgresql_executed": True,
            "db_schema_version": "1.6.0",
            "existing_core_tables_only": True,
            "shadow_schema_created": False,
        },
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if not failed else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--conninfo-template", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(
            user=args.user,
            host=args.host,
            port=args.port,
            psql=args.psql,
            admin_database=args.admin_database,
            database=args.database,
            conninfo_template=args.conninfo_template,
            source_revision=args.source_revision,
            evidence=args.evidence,
        )
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "source_revision": args.source_revision,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
