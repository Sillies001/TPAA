#!/usr/bin/env python3
"""M3-TST-005 real SQLite/PostgreSQL exact-116 Release membership parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    bootstrap_postgres,
)
from tools.testing.m1_batch_2_support import (  # noqa: E402
    build_batch_2_fixture_products,
    seed_postgres_core_prerequisites,
    seed_sqlite_core_prerequisites,
)
from tpaa_application.m1_publication import to_core_publication_bundle  # noqa: E402
from tpaa_metric import (  # noqa: E402
    M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    CatalogMetricEngine,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m3_metric_execution_plan,
)
from tpaa_observation import (  # noqa: E402
    build_m3_publication_routing_plan,
    build_m3_release_snapshot,
)
from tpaa_storage.bootstrap import bootstrap_sqlite  # noqa: E402
from tpaa_storage.postgres_repository import PostgreSQLServiceUnitOfWork  # noqa: E402
from tpaa_storage.publication_bundle import CorePublicationBundle  # noqa: E402
from tpaa_storage.sqlite_repository import SQLiteDesktopUnitOfWork  # noqa: E402

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"
DEFAULT_DATABASE = "tpaa_m3_tst_005_storage_parity"
SCHEMA = "TPAA_M3_TST_005_STORAGE_PARITY_EVIDENCE_V1"
IDEMPOTENCY_KEY = "m3-tst-005-storage-parity"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _id(kind: str, metric_code: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"tpaa-m3-tst-005:{kind}:{metric_code}"))


def _build_release(products: Any, source_revision: str) -> tuple[Any, Any]:
    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    routing = build_m3_publication_routing_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "definition_hash": request.definition.definition_hash,
            "input_token": request.input_payload["input_token"],
            "upstream_result_hashes": list(request.upstream_result_hashes),
        }

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-tst-005-storage:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": f"M3-TST-005-STORAGE::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    batch = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    ).execute(
        inputs,
        validate_runtime_contract=False,
    )

    request_hash = _hash(
        {
            "command": "M3_TST_005_STORAGE_PARITY",
            "session_id": products.release.session_id,
            "source_revision": source_revision,
            "metric_codes": list(plan.metric_codes),
        }
    )
    identity = products.release.observations[0].identity
    context_snapshot: dict[str, object] = {
        "context_id": products.release.context_id,
        "context_version": products.release.context_version,
        "source_revision": source_revision,
    }
    world_snapshot: dict[str, object] = {
        "world_product_id": products.world.world_product_id,
        "world_logical_hash": products.world.logical_content_hash,
        "source_revision": source_revision,
    }
    identity_snapshot: dict[str, object] = {
        "aircraft_id": identity.aircraft_id,
        "aircraft_instance_id": identity.aircraft_instance_id,
        "subject_entity_id": identity.subject_entity_id,
        "aircraft_model_id": identity.aircraft_model_id,
    }
    provenance_snapshot: dict[str, object] = {
        "source_revision": source_revision,
        "catalog_hash": plan.catalog_sha256,
        "metric_execution_plan_hash": plan.logical_hash,
        "publication_routing_plan_hash": routing.logical_hash,
        "execution_batch_hash": batch.logical_hash,
    }
    evidence_by_metric = {
        definition.metric_code: {
            "evidence_contract": "M3_TST_005_STORAGE_MEMBERSHIP_V1",
            "metric_code": definition.metric_code,
            "execution_record_hash": next(
                record.logical_hash
                for record in batch.records
                if record.metric_code == definition.metric_code
            ),
        }
        for definition in plan.definitions
    }
    release = build_m3_release_snapshot(
        session_id=products.release.session_id,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        evidence_by_metric=evidence_by_metric,
        context_snapshot=context_snapshot,
        world_snapshot=world_snapshot,
        identity_snapshot=identity_snapshot,
        provenance_snapshot=provenance_snapshot,
    )
    return plan, release


def _to_storage_bundle(products: Any, plan: Any, release: Any) -> CorePublicationBundle:
    base = to_core_publication_bundle(products.release)
    base_definition = base.definitions[0]
    base_evidence = base.evidence_sets[0]
    base_metric = base.metric_instances[0]
    base_observation = base.observations[0]

    definitions: list[Any] = []
    evidence_sets: list[Any] = []
    metric_instances: list[Any] = []
    first_observation: Any | None = None

    release_definitions = {item.metric_code: item for item in release.definitions}
    release_records = {item.metric_code: item for item in release.execution_records}
    release_evidence = {item.metric_code: item for item in release.evidence_bindings}

    for metric_code in plan.metric_codes:
        definition = release_definitions[metric_code]
        record = release_records[metric_code]
        evidence = release_evidence[metric_code]
        definition_id = _id("definition", metric_code)
        evidence_id = _id("evidence", metric_code)
        metric_instance_id = _id("metric-instance", metric_code)
        storage_value: dict[str, object] = {
            "qualification_contract": "M3_TST_005_STORAGE_MEMBERSHIP_V1",
            "metric_code": metric_code,
            "definition_hash": definition.definition_hash,
            "execution_record_hash": record.record_logical_hash,
            "evidence_hash": evidence.evidence_hash,
        }

        definitions.append(
            replace(
                base_definition,
                metric_definition_id=definition_id,
                metric_code=metric_code,
                catalog_version=release.catalog_version,
                catalog_hash=release.catalog_hash,
                metric_semantic_id=definition.semantic_id,
                metric_semantic_version=definition.semantic_version,
                subject_type=definition.subject_type,
                observation_lane=definition.observation_lane,
                publication_route=definition.publication_route,
                definition_hash=definition.definition_hash,
            )
        )
        evidence_sets.append(
            replace(
                base_evidence,
                evidence_set_id=evidence_id,
                series_locator={
                    "qualification_contract": "M3_TST_005_STORAGE_MEMBERSHIP_V1",
                    "metric_code": metric_code,
                    "evidence_hash": evidence.evidence_hash,
                },
                algorithm_versions={
                    "metric_code": metric_code,
                    "execution_record_hash": record.record_logical_hash,
                },
            )
        )
        metric_instances.append(
            replace(
                base_metric,
                metric_instance_id=metric_instance_id,
                metric_definition_id=definition_id,
                metric_code=metric_code,
                value_numeric=None,
                value_structured=storage_value,
                evidence_set_id=evidence_id,
                context_id=base.context_id,
                world_product_versions={
                    "world_product_id": products.world.world_product_id,
                    "world_logical_hash": products.world.logical_content_hash,
                    "m3_release_manifest_hash": release.manifest_hash,
                },
                input_hash=record.input_payload_hash,
            )
        )
        if first_observation is None:
            first_observation = replace(
                base_observation,
                observation_id=_id("qualification-observation", metric_code),
                observed_metric_instance_id=metric_instance_id,
                observed_value_numeric=None,
                observed_value_structured=storage_value,
                evidence_set_id=evidence_id,
                comparison_key_hash=_hash(
                    {
                        "qualification_contract": "M3_TST_005_STORAGE_MEMBERSHIP_V1",
                        "metric_code": metric_code,
                        "release_id": release.release_id,
                    }
                ),
            )

    if first_observation is None:
        raise ValueError("M3 storage bundle cannot be empty")

    return replace(
        base,
        release_id=release.release_id,
        release_no=release.release_no,
        parent_release_id=release.parent_release_id,
        request_hash=release.request_hash,
        context_binding_hash=release.bindings.context_hash,
        catalog_version=release.catalog_version,
        catalog_hash=release.catalog_hash,
        manifest_hash=release.manifest_hash,
        definitions=tuple(definitions),
        evidence_sets=tuple(evidence_sets),
        metric_instances=tuple(metric_instances),
        observations=(first_observation,),
    )


def _seed_sqlite_definitions(
    connection: sqlite3.Connection,
    *,
    bundle: CorePublicationBundle,
    world_product_id: str,
    capability_dimension: str,
) -> None:
    connection.execute('DELETE FROM "metric.metric_definition"')
    for definition in bundle.definitions:
        connection.execute(
            """INSERT INTO "metric.metric_definition" (
                   metric_definition_id, metric_code, version, catalog_version,
                   catalog_hash, metric_semantic_id, metric_semantic_version,
                   name, subject_type, observation_lane, publication_route,
                   category, calculation_layer, capability_level,
                   capability_dimension, required_world_products, scope,
                   spec_uri, spec_hash, definition_hash, plugin_name,
                   plugin_version, status
               ) VALUES (
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
               )""",
            (
                definition.metric_definition_id,
                definition.metric_code,
                "M3-TST-005-V1",
                definition.catalog_version,
                definition.catalog_hash,
                definition.metric_semantic_id,
                definition.metric_semantic_version,
                definition.metric_code,
                definition.subject_type,
                definition.observation_lane,
                definition.publication_route,
                "TEST_ONLY",
                "TEST_ONLY_M3_STORAGE_QUALIFICATION",
                "CAP_L1_OBSERVED",
                capability_dimension,
                _canonical_json([world_product_id]),
                "EPISODE",
                f"test-only://m3-tst-005/{definition.metric_code}",
                definition.definition_hash,
                definition.definition_hash,
                "M3_TST_005_STORAGE_QUALIFICATION",
                "1",
                "TEST_ONLY_ACTIVE",
            ),
        )
    connection.commit()


def _seed_postgres_definitions(
    connection: Any,
    *,
    bundle: CorePublicationBundle,
    world_product_id: str,
    capability_dimension: str,
) -> None:
    from psycopg.types.json import Jsonb

    with connection.cursor() as cursor:
        cursor.execute('DELETE FROM "metric"."metric_definition"')
        for definition in bundle.definitions:
            cursor.execute(
                """INSERT INTO "metric"."metric_definition" (
                       metric_definition_id, metric_code, version, catalog_version,
                       catalog_hash, metric_semantic_id, metric_semantic_version,
                       name, subject_type, observation_lane, publication_route,
                       category, calculation_layer, capability_level,
                       capability_dimension, required_world_products, scope,
                       spec_uri, spec_hash, definition_hash, plugin_name,
                       plugin_version, status
                   ) VALUES (
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                   )""",
                (
                    definition.metric_definition_id,
                    definition.metric_code,
                    "M3-TST-005-V1",
                    definition.catalog_version,
                    definition.catalog_hash,
                    definition.metric_semantic_id,
                    definition.metric_semantic_version,
                    definition.metric_code,
                    definition.subject_type,
                    definition.observation_lane,
                    definition.publication_route,
                    "TEST_ONLY",
                    "TEST_ONLY_M3_STORAGE_QUALIFICATION",
                    "CAP_L1_OBSERVED",
                    capability_dimension,
                    Jsonb([world_product_id]),
                    "EPISODE",
                    f"test-only://m3-tst-005/{definition.metric_code}",
                    definition.definition_hash,
                    definition.definition_hash,
                    "M3_TST_005_STORAGE_QUALIFICATION",
                    "1",
                    "TEST_ONLY_ACTIVE",
                ),
            )
    connection.commit()


def _sqlite_codes(database: Path, release_id: str) -> tuple[str, ...]:
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            """SELECT d.metric_code
               FROM "metric.metric_instance" AS i
               JOIN "metric.metric_definition" AS d
                 ON d.metric_definition_id = i.metric_definition_id
               WHERE i.release_id = ?
               ORDER BY d.metric_code""",
            (release_id,),
        ).fetchall()
    finally:
        connection.close()
    return tuple(str(row[0]) for row in rows)


def _postgres_codes(conninfo: str, release_id: str) -> tuple[str, ...]:
    import psycopg

    with psycopg.connect(conninfo, autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT d.metric_code
                   FROM "metric"."metric_instance" AS i
                   JOIN "metric"."metric_definition" AS d
                     ON d.metric_definition_id = i.metric_definition_id
                   WHERE i.release_id = %s
                   ORDER BY d.metric_code""",
                (release_id,),
            )
            return tuple(str(row[0]) for row in cursor.fetchall())


def _receipt_payload(receipt: Any, retry: Any, retry_equal: bool) -> dict[str, object]:
    return {
        "release_id": receipt.release_id,
        "session_id": receipt.session_id,
        "request_hash": receipt.request_hash,
        "manifest_hash": receipt.manifest_hash,
        "version_token": receipt.version_token,
        "reused": receipt.reused,
        "retry_reused": retry.reused,
        "retry_version_token": retry.version_token,
        "retry_membership_equal": retry_equal,
    }


def _publish_sqlite(
    products: Any,
    bundle: CorePublicationBundle,
) -> tuple[dict[str, object], dict[str, object], tuple[str, ...]]:
    with tempfile.TemporaryDirectory(prefix="tpaa-m3-tst005-sqlite-") as tmp:
        database = Path(tmp) / "tpaa.sqlite3"
        bootstrap_sqlite(database)
        connection = sqlite3.connect(database)
        try:
            seed_sqlite_core_prerequisites(connection, products)
            _seed_sqlite_definitions(
                connection,
                bundle=bundle,
                world_product_id=products.world.world_product_id,
                capability_dimension=products.release.observations[0].identity.capability_dimension,
            )
        finally:
            connection.close()

        with SQLiteDesktopUnitOfWork(database, write=True) as uow:
            receipt = uow.publication.publish(
                bundle,
                idempotency_key=IDEMPOTENCY_KEY,
                expected_version_token=0,
            )
            membership = uow.publication.logical_membership(bundle.release_id)
            uow.commit()

        with SQLiteDesktopUnitOfWork(database, write=True) as uow:
            retry = uow.publication.publish(
                bundle,
                idempotency_key=IDEMPOTENCY_KEY,
                expected_version_token=0,
            )
            retry_membership = uow.publication.logical_membership(bundle.release_id)
            uow.commit()

        codes = _sqlite_codes(database, bundle.release_id)
    return membership, _receipt_payload(
        receipt,
        retry,
        retry_membership == membership,
    ), codes


def _publish_postgres(
    *,
    conninfo: str,
    products: Any,
    bundle: CorePublicationBundle,
) -> tuple[dict[str, object], dict[str, object], tuple[str, ...]]:
    import psycopg

    with psycopg.connect(conninfo, autocommit=False) as connection:
        seed_postgres_core_prerequisites(connection, products)
        _seed_postgres_definitions(
            connection,
            bundle=bundle,
            world_product_id=products.world.world_product_id,
            capability_dimension=products.release.observations[0].identity.capability_dimension,
        )

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        receipt = uow.publication.publish(
            bundle,
            idempotency_key=IDEMPOTENCY_KEY,
            expected_version_token=0,
        )
        membership = uow.publication.logical_membership(bundle.release_id)
        uow.commit()

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        retry = uow.publication.publish(
            bundle,
            idempotency_key=IDEMPOTENCY_KEY,
            expected_version_token=0,
        )
        retry_membership = uow.publication.logical_membership(bundle.release_id)
        uow.commit()

    codes = _postgres_codes(conninfo, bundle.release_id)
    return membership, _receipt_payload(
        receipt,
        retry,
        retry_membership == membership,
    ), codes


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return {str(key): item for key, item in value.items()}


def _rows(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return [
        _mapping(item, field=f"{key}[{index}]")
        for index, item in enumerate(value)
    ]


def _exact_list_size(payload: dict[str, object], key: str, size: int) -> bool:
    value = payload.get(key)
    return isinstance(value, list) and len(value) == size


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
    if not database.startswith("tpaa_m3_tst_005_"):
        raise ValueError("database must start with 'tpaa_m3_tst_005_'")
    if "{database}" not in conninfo_template:
        raise ValueError("conninfo template must contain '{database}'")
    if len(source_revision) != 40:
        raise ValueError("source_revision must be an exact 40-character Git SHA")

    products = build_batch_2_fixture_products(
        fixture_root=FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
        fixture_id="BF_M1_NOMINAL_V1",
        request_label="m3-tst-005-storage-prerequisites",
    )
    plan, release = _build_release(products, source_revision)
    bundle = _to_storage_bundle(products, plan, release)
    expected_codes = tuple(sorted(plan.metric_codes))

    sqlite_membership, sqlite_receipt, sqlite_codes = _publish_sqlite(
        products,
        bundle,
    )

    client = PsqlClient(
        user=user,
        host=host,
        port=port,
        psql_executable=psql,
    )
    _recreate_scoped_database(
        client,
        admin_database,
        database,
        required_prefix="tpaa_m3_tst_005_",
    )
    try:
        bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)
        postgres_membership, postgres_receipt, postgres_codes = _publish_postgres(
            conninfo=conninfo,
            products=products,
            bundle=bundle,
        )
    finally:
        if _database_exists(client, admin_database, database):
            client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = {_literal(database)} AND pid <> pg_backend_pid();\n"
                f"DROP DATABASE {_identifier(database)};\n",
            )

    membership_equal = sqlite_membership == postgres_membership
    sqlite_hash = _hash(sqlite_membership)
    postgres_hash = _hash(postgres_membership)
    receipt_identity_equal = {
        key: sqlite_receipt[key] == postgres_receipt[key]
        for key in (
            "release_id",
            "session_id",
            "request_hash",
            "manifest_hash",
            "version_token",
            "reused",
            "retry_reused",
            "retry_version_token",
            "retry_membership_equal",
        )
    }
    expected_definition_ids = {
        _id("definition", metric_code)
        for metric_code in plan.metric_codes
    }
    sqlite_definition_ids = {
        str(item.get("metric_definition_id"))
        for item in _rows(sqlite_membership, "metric_instances")
    }
    postgres_definition_ids = {
        str(item.get("metric_definition_id"))
        for item in _rows(postgres_membership, "metric_instances")
    }
    sqlite_release = _mapping(
        sqlite_membership.get("release"),
        field="sqlite.release",
    )
    postgres_release = _mapping(
        postgres_membership.get("release"),
        field="postgres.release",
    )

    acceptance = {
        "current_core_schema_is_1_9_0": (
            bootstrap.schema_version == "1.9.0"
            and bootstrap.core_baseline == "CB-1.4.0"
            and bootstrap.table_count == 95
        ),
        "m3_release_snapshot_exact_116": (
            len(release.definitions) == 116
            and len(release.execution_records) == 116
            and len(release.evidence_bindings) == 116
            and len(set(release.metric_codes)) == 116
        ),
        "sqlite_publish_idempotent": (
            sqlite_receipt["reused"] is False
            and sqlite_receipt["version_token"] == 1
            and sqlite_receipt["retry_reused"] is True
            and sqlite_receipt["retry_version_token"] == 1
            and sqlite_receipt["retry_membership_equal"] is True
        ),
        "postgres_publish_idempotent": (
            postgres_receipt["reused"] is False
            and postgres_receipt["version_token"] == 1
            and postgres_receipt["retry_reused"] is True
            and postgres_receipt["retry_version_token"] == 1
            and postgres_receipt["retry_membership_equal"] is True
        ),
        "receipt_identity_equal": all(receipt_identity_equal.values()),
        "logical_release_membership_equal": membership_equal,
        "logical_membership_hash_equal": sqlite_hash == postgres_hash,
        "sqlite_exact_116_metric_instances": _exact_list_size(
            sqlite_membership,
            "metric_instances",
            116,
        ),
        "postgres_exact_116_metric_instances": _exact_list_size(
            postgres_membership,
            "metric_instances",
            116,
        ),
        "sqlite_exact_116_evidence_sets": _exact_list_size(
            sqlite_membership,
            "evidence_sets",
            116,
        ),
        "postgres_exact_116_evidence_sets": _exact_list_size(
            postgres_membership,
            "evidence_sets",
            116,
        ),
        "sqlite_postgres_exact_metric_codes": (
            sqlite_codes == postgres_codes == expected_codes
        ),
        "sqlite_postgres_exact_definition_ids": (
            sqlite_definition_ids
            == postgres_definition_ids
            == expected_definition_ids
        ),
        "qualification_does_not_fabricate_116_observations": (
            _exact_list_size(sqlite_membership, "observations", 1)
            and _exact_list_size(postgres_membership, "observations", 1)
        ),
        "stored_release_identity_matches_m3_snapshot": (
            sqlite_release.get("release_id") == release.release_id
            and postgres_release.get("release_id") == release.release_id
            and sqlite_release.get("manifest_hash") == release.manifest_hash
            and postgres_release.get("manifest_hash") == release.manifest_hash
        ),
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "task_id": "M3-TST-005",
        "tracking_issue": 117,
        "source_revision": source_revision,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "release_id": release.release_id,
        "manifest_hash": release.manifest_hash,
        "metric_codes": list(plan.metric_codes),
        "sqlite_membership_hash": sqlite_hash,
        "postgres_membership_hash": postgres_hash,
        "receipt_identity_equal": receipt_identity_equal,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "logical_membership": (
            sqlite_membership
            if membership_equal
            else {
                "sqlite": sqlite_membership,
                "postgres": postgres_membership,
            }
        ),
        "scope": {
            "real_sqlite_executed": True,
            "real_postgresql_executed": True,
            "current_db_schema_1_9_0_only": True,
            "existing_core_publication_ledger_only": True,
            "shadow_schema_created": False,
            "business_metric_recomputation_executed": False,
            "qualification_only_storage_sentinel_observation_count": 1,
        },
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failed else 2


def main(argv: list[str] | None = None) -> int:
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
    args = parser.parse_args(argv)
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
            "task_id": "M3-TST-005",
            "tracking_issue": 117,
            "source_revision": args.source_revision,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
