"""Run the W1 PostgreSQL migration graph against an isolated test database."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import psycopg

from tpaa_storage.bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    CORE_MODEL_ARTIFACT_ID,
    POSTGRES_ENGINE_PROFILE,
    _postgres_catalog_hash_query,
    _postgres_create_statements,
    _postgres_manifest_create_statement,
    _schema_fingerprint,
)
from tpaa_storage.migration_service import (
    PostgreSQLMigrationService,
    _load_migration_authority,
)


def _bootstrap_1_6(conninfo: str, authority_root: Path, migration_root: Path) -> None:
    authority = _load_migration_authority(
        "1.6.0",
        current_authority_root=authority_root,
        migration_authority_root=migration_root,
    )
    connection = psycopg.connect(conninfo, autocommit=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COUNT(*) FROM pg_class c
                   JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
                     AND c.relkind IN ('r','p','v','m','S')"""
            )
            row = cursor.fetchone()
            if row is None or int(row[0]) != 0:
                raise RuntimeError("qualification database is not empty")
            for statement in _postgres_create_statements(authority):
                cursor.execute(statement)
            cursor.execute(_postgres_manifest_create_statement())
            cursor.execute(_postgres_catalog_hash_query())
            catalog = cursor.fetchone()
            if catalog is None:
                raise RuntimeError("catalog hash unavailable")
            cursor.execute(
                f'''INSERT INTO "public"."{BOOTSTRAP_MANIFEST_TABLE}" (
                       singleton, engine_profile, schema_version, core_baseline,
                       authority_artifact_id, authority_sha256,
                       baseline_lock_sha256, physical_schema_sha256,
                       catalog_schema_sha256
                   ) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (
                    POSTGRES_ENGINE_PROFILE,
                    authority.schema_version,
                    authority.core_baseline,
                    CORE_MODEL_ARTIFACT_ID,
                    authority.authority_sha256,
                    authority.baseline_lock_sha256,
                    _schema_fingerprint(_postgres_create_statements(authority)),
                    str(catalog[0]),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def qualify(
    *,
    conninfo: str,
    authority_root: Path,
    migration_root: Path,
    state_root: Path,
    backup_root: Path,
    docker_container: str,
    database_user: str,
    database_name: str,
) -> dict[str, Any]:
    _bootstrap_1_6(conninfo, authority_root, migration_root)
    backup_root.mkdir(parents=True, exist_ok=True)

    def backup(_evidence: object, operation_id: str) -> tuple[Path, str]:
        target = backup_root / f"{operation_id}.dump"
        result = subprocess.run(
            (
                "docker",
                "exec",
                docker_container,
                "pg_dump",
                "--format=custom",
                "--username",
                database_user,
                "--dbname",
                database_name,
            ),
            check=True,
            capture_output=True,
        )
        target.write_bytes(result.stdout)
        return target, hashlib.sha256(result.stdout).hexdigest()

    service = PostgreSQLMigrationService(
        conninfo,
        state_root=state_root,
        current_authority_root=authority_root,
        migration_authority_root=migration_root,
        backup_provider=backup,
    )
    planned = service.plan().payload()
    planned_hops = planned["hops"]
    if not isinstance(planned_hops, list):
        raise RuntimeError("migration plan has invalid hop payload")

    class FailOnce(PostgreSQLMigrationService):
        failed = False

        def _apply_hop(self, connection: Any, hop: Any) -> None:
            if not self.failed:
                self.failed = True
                raise RuntimeError("intentional W1 recovery qualification fault")
            super()._apply_hop(connection, hop)

    failing = FailOnce(
        conninfo,
        state_root=state_root,
        current_authority_root=authority_root,
        migration_authority_root=migration_root,
        backup_provider=backup,
    )
    failure_observed = False
    try:
        failing.apply()
    except RuntimeError:
        failure_observed = True
    if not failure_observed or service.status().journal_state != "FAILED":
        raise RuntimeError("failure journal was not preserved")

    resumed = service.resume()
    if service.verify().schema_version != "1.9.0":
        raise RuntimeError("resume did not reach DB 1.9.0")
    rolled_back = service.rollback("1.8.0")
    if service.verify().schema_version != "1.8.0":
        raise RuntimeError("rollback did not reach DB 1.8.0")
    reapplied = service.apply()
    status = service.status().payload()
    if status["status"] != "READY":
        raise RuntimeError("final migration state is not READY")
    return {
        "schema": "TPAA_W1_POSTGRES_MIGRATION_QUALIFICATION_V1",
        "status": "PASS",
        "planned_hops": [
            item["proposal"] for item in planned_hops if isinstance(item, dict)
        ],
        "failure_recovery": resumed["status"],
        "rollback_target": rolled_back["target_version"],
        "final_target": reapplied["target_version"],
        "final_status": status,
        "backup_count": len(tuple(backup_root.glob("*.dump"))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conninfo", required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--migration-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--docker-container", required=True)
    parser.add_argument("--database-user", default="tpaa")
    parser.add_argument("--database-name", default="tpaa")
    args = parser.parse_args()
    print(
        json.dumps(
            qualify(
                conninfo=args.conninfo,
                authority_root=args.authority_root.resolve(),
                migration_root=args.migration_root.resolve(),
                state_root=args.state_root.resolve(),
                backup_root=args.backup_root.resolve(),
                docker_container=args.docker_container,
                database_user=args.database_user,
                database_name=args.database_name,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
