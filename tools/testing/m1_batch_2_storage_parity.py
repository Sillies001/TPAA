"""Real SQLite/PostgreSQL logical Release parity for M1-STO-001/003."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
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
from tpaa_storage.bootstrap import bootstrap_sqlite  # noqa: E402
from tpaa_storage.postgres_repository import PostgreSQLServiceUnitOfWork  # noqa: E402
from tpaa_storage.sqlite_repository import SQLiteDesktopUnitOfWork  # noqa: E402

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"
DEFAULT_DATABASE = "tpaa_m1_batch_2_parity"
SCHEMA = "TPAA_M1_BATCH_2_STORAGE_PARITY_V1"


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


def _has_exact_list_size(payload: dict[str, object], key: str, size: int) -> bool:
    value = payload.get(key)
    return isinstance(value, list) and len(value) == size


def _publish_sqlite(products: Any) -> tuple[dict[str, object], dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="tpaa-m1-batch2-sqlite-") as tmp:
        database = Path(tmp) / "tpaa.sqlite3"
        bootstrap_sqlite(database)
        connection = sqlite3.connect(database)
        try:
            seed_sqlite_core_prerequisites(connection, products)
        finally:
            connection.close()

        bundle = to_core_publication_bundle(products.release)
        with SQLiteDesktopUnitOfWork(database, write=True) as uow:
            receipt = uow.publication.publish(
                bundle,
                idempotency_key="m1-batch-2-storage-parity",
                expected_version_token=0,
            )
            membership = uow.publication.logical_membership(products.release.release_id)
            uow.commit()

        with SQLiteDesktopUnitOfWork(database, write=True) as uow:
            retry = uow.publication.publish(
                bundle,
                idempotency_key="m1-batch-2-storage-parity",
                expected_version_token=0,
            )
            retry_membership = uow.publication.logical_membership(products.release.release_id)
            uow.commit()

    receipt_payload = {
        "release_id": receipt.release_id,
        "session_id": receipt.session_id,
        "request_hash": receipt.request_hash,
        "manifest_hash": receipt.manifest_hash,
        "version_token": receipt.version_token,
        "reused": receipt.reused,
        "retry_reused": retry.reused,
        "retry_version_token": retry.version_token,
        "retry_membership_equal": retry_membership == membership,
    }
    return membership, receipt_payload


def _publish_postgres(
    *,
    conninfo: str,
    products: Any,
) -> tuple[dict[str, object], dict[str, object]]:
    import psycopg

    with psycopg.connect(conninfo, autocommit=False) as connection:
        seed_postgres_core_prerequisites(connection, products)

    bundle = to_core_publication_bundle(products.release)
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        receipt = uow.publication.publish(
            bundle,
            idempotency_key="m1-batch-2-storage-parity",
            expected_version_token=0,
        )
        membership = uow.publication.logical_membership(products.release.release_id)
        uow.commit()

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        retry = uow.publication.publish(
            bundle,
            idempotency_key="m1-batch-2-storage-parity",
            expected_version_token=0,
        )
        retry_membership = uow.publication.logical_membership(products.release.release_id)
        uow.commit()

    receipt_payload = {
        "release_id": receipt.release_id,
        "session_id": receipt.session_id,
        "request_hash": receipt.request_hash,
        "manifest_hash": receipt.manifest_hash,
        "version_token": receipt.version_token,
        "reused": receipt.reused,
        "retry_reused": retry.reused,
        "retry_version_token": retry.version_token,
        "retry_membership_equal": retry_membership == membership,
    }
    return membership, receipt_payload


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
    if not database.startswith("tpaa_m1_batch_2_"):
        raise ValueError("database must start with 'tpaa_m1_batch_2_'")
    if "{database}" not in conninfo_template:
        raise ValueError("conninfo template must contain '{database}'")
    if len(source_revision) != 40:
        raise ValueError("source_revision must be an exact 40-character Git SHA")

    products = build_batch_2_fixture_products(
        fixture_root=FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
        fixture_id="BF_M1_NOMINAL_V1",
        request_label="storage-parity",
    )
    sqlite_membership, sqlite_receipt = _publish_sqlite(products)

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
        required_prefix="tpaa_m1_batch_2_",
    )
    try:
        bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)
        postgres_membership, postgres_receipt = _publish_postgres(
            conninfo=conninfo,
            products=products,
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
    sqlite_hash = _hash(sqlite_membership)
    postgres_hash = _hash(postgres_membership)

    acceptance = {
        "core_schema_is_frozen_1_6_0": (
            bootstrap.schema_version == "1.6.0"
            and bootstrap.core_baseline == "CB-1.4.0"
            and bootstrap.table_count == 77
        ),
        "sqlite_publish_pass": (
            sqlite_receipt["reused"] is False
            and sqlite_receipt["version_token"] == 1
            and sqlite_receipt["retry_reused"] is True
            and sqlite_receipt["retry_version_token"] == 1
            and sqlite_receipt["retry_membership_equal"] is True
        ),
        "postgres_publish_pass": (
            postgres_receipt["reused"] is False
            and postgres_receipt["version_token"] == 1
            and postgres_receipt["retry_reused"] is True
            and postgres_receipt["retry_version_token"] == 1
            and postgres_receipt["retry_membership_equal"] is True
        ),
        "receipt_identity_equal": all(receipt_identity_equal.values()),
        "logical_release_membership_equal": membership_equal,
        "logical_membership_hash_equal": sqlite_hash == postgres_hash,
        "five_metric_instances_equal": (
            _has_exact_list_size(sqlite_membership, "metric_instances", 5)
            and _has_exact_list_size(postgres_membership, "metric_instances", 5)
        ),
        "five_evidence_sets_equal": (
            _has_exact_list_size(sqlite_membership, "evidence_sets", 5)
            and _has_exact_list_size(postgres_membership, "evidence_sets", 5)
        ),
        "five_observations_equal": (
            _has_exact_list_size(sqlite_membership, "observations", 5)
            and _has_exact_list_size(postgres_membership, "observations", 5)
        ),
    }
    failed_acceptance = sorted(
        name for name, passed in acceptance.items() if not passed
    )
    status = "PASS" if not failed_acceptance else "FAIL"
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "tracking_issue": 87,
        "task_ids": ["M1-STO-001", "M1-STO-003"],
        "source_revision": source_revision,
        "status": status,
        "fixture_id": products.release.fixture_id,
        "release_id": products.release.release_id,
        "manifest_hash": products.release.manifest_hash,
        "sqlite_membership_hash": sqlite_hash,
        "postgres_membership_hash": postgres_hash,
        "receipt_identity_equal": receipt_identity_equal,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
        "logical_membership": sqlite_membership if membership_equal else {
            "sqlite": sqlite_membership,
            "postgres": postgres_membership,
        },
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


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
    except Exception as exc:  # noqa: BLE001 - evidence runner must fail closed
        print(f"M1_BATCH_2_STORAGE_PARITY_FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
