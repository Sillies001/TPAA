#!/usr/bin/env python3
"""PIQB B2 real PostgreSQL restart and SQLite/PostgreSQL product parity gate."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

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
    verify_postgres,
)
from tpaa_runtime.persistence import (  # noqa: E402
    DesktopPersistenceConfig,
    ServicePersistenceConfig,
    build_desktop_persistence,
    build_service_persistence,
)
from tpaa_storage import (  # noqa: E402
    ProductPublicationError,
    ProductPublicationReceipt,
    ProductPublicationRequest,
    ProductReleaseIdentity,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
    verify_sqlite,
)
from tpaa_storage.postgres_repository import (  # noqa: E402
    PostgreSQLServiceUnitOfWork,
)

SCHEMA = "TPAA_PIQB_B2_POSTGRES_PERSISTENCE_V1"
TASK_IDS = ("PIQB-B2-006", "PIQB-B2-008")
TRACKING_ISSUE = 209
ACP_ISSUE = 216
ACP_STATUS = "PROPOSED_NOT_ADOPTED"
PREFIX = "tpaa-object://products/piqb-b2-live"
PRODUCT_FAMILY = "LONGITUDINAL_RELEASE"
PRODUCT_ID = "93000000-0000-4000-8000-000000000001"
RELEASE_ID = "93000000-0000-4000-8000-000000000002"
CONFLICT_RELEASE_ID = "93000000-0000-4000-8000-000000000003"
SCOPE_KEY = "PIQB-B2:LONGITUDINAL:93000000-0000-4000-8000-000000000004"
OBJECT_URI = PREFIX + "/qualified.json"
CONFLICT_OBJECT_URI = PREFIX + "/stale-cas.json"


def _request(
    *,
    release_id: str,
    sealed_uri: str,
    payload: bytes,
    idempotency_key: str,
    manifest_hash: str,
) -> ProductPublicationRequest:
    return ProductPublicationRequest(
        operation_id=f"piqb-b2-{idempotency_key}",
        product_family=PRODUCT_FAMILY,
        product_id=PRODUCT_ID,
        release=ProductReleaseIdentity(
            release_id=release_id,
            scope_type="LONGITUDINAL",
            scope_key=SCOPE_KEY,
            session_id=None,
            longitudinal_scope_id=None,
            catalog_version="P1-METRIC-CATALOG-1.0",
            catalog_hash="1" * 64,
            context_binding_hash="2" * 64,
            manifest_hash=manifest_hash,
        ),
        sealed_uri=sealed_uri,
        payload=payload,
        media_type="application/json",
        storage_backend="LOCAL_OBJECT_STORE",
        idempotency_key=idempotency_key,
        expected_version_token=0,
    )


def _qualified_request() -> ProductPublicationRequest:
    return _request(
        release_id=RELEASE_ID,
        sealed_uri=OBJECT_URI,
        payload=b'{"schema":"PIQB_B2_LIVE_PRODUCT","revision":1}',
        idempotency_key="piqb-b2-live-product-v1",
        manifest_hash="3" * 64,
    )


def _conflict_request() -> ProductPublicationRequest:
    return _request(
        release_id=CONFLICT_RELEASE_ID,
        sealed_uri=CONFLICT_OBJECT_URI,
        payload=b'{"schema":"PIQB_B2_LIVE_PRODUCT","revision":2}',
        idempotency_key="piqb-b2-live-product-stale-cas",
        manifest_hash="4" * 64,
    )


def _receipt(value: ProductPublicationReceipt) -> dict[str, object]:
    return {
        "product_family": value.product_family,
        "product_id": value.product_id,
        "release_id": value.release_id,
        "scope_type": value.scope_type,
        "scope_key": value.scope_key,
        "object_uri": value.object_uri,
        "object_sha256": value.object_sha256,
        "version_token": value.version_token,
        "reused": value.reused,
    }


def _recovery_payload(report: Any) -> dict[str, object]:
    return {
        "logical_prefix": report.logical_prefix,
        "scanned": report.scanned,
        "referenced": report.referenced,
        "orphaned": list(report.orphaned),
        "removed": list(report.removed),
        "dry_run": report.dry_run,
    }


def _exercise_sqlite(
    database: Path,
    object_root: Path,
) -> dict[str, object]:
    config = DesktopPersistenceConfig(
        database_path=database,
        object_root=object_root,
    )
    first_runtime = build_desktop_persistence(config)
    first = first_runtime.publish(_qualified_request())

    restarted_runtime = build_desktop_persistence(config)
    replay = restarted_runtime.publish(_qualified_request())

    with SQLiteDesktopUnitOfWork(database) as uow:
        exact = uow.product_publication.exact_product(
            PRODUCT_FAMILY,
            PRODUCT_ID,
        )
        referenced = uow.product_publication.referenced_object_uris(PREFIX)
        uow.commit()

    try:
        restarted_runtime.publish(_conflict_request())
    except ProductPublicationError as exc:
        conflict_code = exc.code
        conflict_object = exc.sealed_object
    else:
        raise RuntimeError("SQLite stale CAS unexpectedly succeeded")
    if conflict_object is None:
        raise RuntimeError("SQLite stale CAS did not preserve sealed orphan identity")

    recovery = restarted_runtime.recover_registered_objects(
        logical_prefix=PREFIX,
        dry_run=False,
    )
    remaining = tuple(
        item.logical_uri
        for item in restarted_runtime.object_store.list_objects(PREFIX)
    )
    return {
        "first": _receipt(first.receipt),
        "replay": _receipt(replay.receipt),
        "exact": _receipt(exact),
        "referenced": list(referenced),
        "cas_code": conflict_code,
        "conflict_object_uri": conflict_object.logical_uri,
        "recovery": _recovery_payload(recovery),
        "remaining_object_uris": list(remaining),
        "registered_object_preserved": restarted_runtime.object_store.verify(
            first.sealed_object
        ),
        "conflict_object_removed": conflict_object.logical_uri not in remaining,
    }


def _exercise_postgres(
    conninfo: str,
    object_root: Path,
) -> dict[str, object]:
    config = ServicePersistenceConfig(
        conninfo=conninfo,
        object_root=object_root,
    )
    first_runtime = build_service_persistence(config)
    first = first_runtime.publish(_qualified_request())

    restarted_runtime = build_service_persistence(config)
    replay = restarted_runtime.publish(_qualified_request())

    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        exact = uow.product_publication.exact_product(
            PRODUCT_FAMILY,
            PRODUCT_ID,
        )
        referenced = uow.product_publication.referenced_object_uris(PREFIX)
        uow.commit()

    try:
        restarted_runtime.publish(_conflict_request())
    except ProductPublicationError as exc:
        conflict_code = exc.code
        conflict_object = exc.sealed_object
    else:
        raise RuntimeError("PostgreSQL stale CAS unexpectedly succeeded")
    if conflict_object is None:
        raise RuntimeError(
            "PostgreSQL stale CAS did not preserve sealed orphan identity"
        )

    recovery = restarted_runtime.recover_registered_objects(
        logical_prefix=PREFIX,
        dry_run=False,
    )
    remaining = tuple(
        item.logical_uri
        for item in restarted_runtime.object_store.list_objects(PREFIX)
    )
    return {
        "first": _receipt(first.receipt),
        "replay": _receipt(replay.receipt),
        "exact": _receipt(exact),
        "referenced": list(referenced),
        "cas_code": conflict_code,
        "conflict_object_uri": conflict_object.logical_uri,
        "recovery": _recovery_payload(recovery),
        "remaining_object_uris": list(remaining),
        "registered_object_preserved": restarted_runtime.object_store.verify(
            first.sealed_object
        ),
        "conflict_object_removed": conflict_object.logical_uri not in remaining,
    }


def _restart_acceptance(value: dict[str, object]) -> bool:
    first = value["first"]
    replay = value["replay"]
    exact = value["exact"]
    if not isinstance(first, dict):
        return False
    if not isinstance(replay, dict):
        return False
    if not isinstance(exact, dict):
        return False
    first_row = first
    replay_row = replay
    exact_row = exact
    return (
        first_row.get("version_token") == 1
        and first_row.get("reused") is False
        and replay_row.get("version_token") == 1
        and replay_row.get("reused") is True
        and exact_row.get("release_id") == RELEASE_ID
        and exact_row.get("object_uri") == OBJECT_URI
        and value["referenced"] == [OBJECT_URI]
        and value["cas_code"] == "PUBLISH_CAS_CONFLICT"
        and value["conflict_object_uri"] == CONFLICT_OBJECT_URI
        and value["remaining_object_uris"] == [OBJECT_URI]
        and value["registered_object_preserved"] is True
        and value["conflict_object_removed"] is True
    )


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
    client = PsqlClient(
        user=user,
        host=host,
        port=port,
        psql_executable=psql,
    )
    _identifier(database)
    _recreate_scoped_database(
        client,
        admin_database,
        database,
        required_prefix="tpaa_piqb_b2_",
    )
    try:
        postgres_bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)
        with tempfile.TemporaryDirectory(prefix="tpaa-piqb-b2-live-") as tmp:
            root = Path(tmp)
            sqlite_db = root / "sqlite" / "tpaa.db"
            sqlite_db.parent.mkdir(parents=True, exist_ok=True)
            sqlite_bootstrap = bootstrap_sqlite(sqlite_db)

            sqlite_result = _exercise_sqlite(
                sqlite_db,
                root / "sqlite-objects",
            )
            postgres_result = _exercise_postgres(
                conninfo,
                root / "postgres-objects",
            )

            sqlite_after = verify_sqlite(sqlite_db)
            postgres_after = verify_postgres(client, database)

        acceptance = {
            "sqlite_frozen_db_1_6_0": (
                sqlite_bootstrap.schema_version == "1.6.0"
                and sqlite_after.schema_version == "1.6.0"
            ),
            "postgres_frozen_db_1_6_0": (
                postgres_bootstrap.schema_version == "1.6.0"
                and postgres_after.schema_version == "1.6.0"
            ),
            "sqlite_restart_exact": _restart_acceptance(sqlite_result),
            "postgres_restart_exact": _restart_acceptance(postgres_result),
            "sqlite_postgres_logical_parity": (
                sqlite_result == postgres_result
            ),
            "stale_cas_fail_closed_both_engines": (
                sqlite_result["cas_code"] == "PUBLISH_CAS_CONFLICT"
                and postgres_result["cas_code"] == "PUBLISH_CAS_CONFLICT"
            ),
            "orphan_recovery_preserves_registered_both_engines": (
                sqlite_result["registered_object_preserved"] is True
                and postgres_result["registered_object_preserved"] is True
                and sqlite_result["conflict_object_removed"] is True
                and postgres_result["conflict_object_removed"] is True
            ),
            "authority_change_not_adopted": ACP_STATUS == "PROPOSED_NOT_ADOPTED",
            "shadow_schema_not_created": True,
        }
        failed = sorted(key for key, ok in acceptance.items() if ok is not True)
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "B2_REMAINS_BLOCKED_BY_AUTHORITY_CHANGE",
            "authority_change_proposal_issue": ACP_ISSUE,
            "authority_change_proposal_status": ACP_STATUS,
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "sqlite": sqlite_result,
            "postgres": postgres_result,
            "sqlite_verification": asdict(sqlite_after),
            "postgres_verification": asdict(postgres_after),
            "scope": {
                "real_sqlite_executed": True,
                "real_postgresql_executed": True,
                "db_schema_version": "1.6.0",
                "existing_core_tables_only": True,
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
        }
        rendered = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 0 if not failed else 2
    finally:
        if _database_exists(client, admin_database, database):
            client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = {_literal(database)} "
                "AND pid <> pg_backend_pid();\n"
                f"DROP DATABASE {_identifier(database)};\n",
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument(
        "--database",
        default="tpaa_piqb_b2_product_persistence",
    )
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
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "source_revision": args.source_revision,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "B2_REMAINS_BLOCKED_BY_AUTHORITY_CHANGE",
            "authority_change_proposal_issue": ACP_ISSUE,
            "authority_change_proposal_status": ACP_STATUS,
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "db_schema_version": "1.6.0",
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
