#!/usr/bin/env python3
"""ACP-216 live PostgreSQL DB 1.6.0 -> 1.7.0 migration qualification."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.storage.acp216_migration import (  # noqa: E402
    historical_postgres_bootstrap_script,
    historical_postgres_verify_script,
    postgres_downgrade_script,
    postgres_upgrade_script,
)
from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    verify_postgres,
)

SCHEMA = "TPAA_ACP216_POSTGRES_MIGRATION_V1"
PROBE_ID = "94000000-0000-4000-8000-000000000001"
PROBE_VALUE = f"{PROBE_ID}|AIRCRAFT|ACP216-HISTORY-PROBE|BLUE"


def _probe(client: PsqlClient, database: str) -> str:
    return client.run(
        database,
        '''SELECT entity_id::text || '|' || entity_type || '|' ||
                  alias || '|' || actual_side_affiliation
           FROM "master"."entity"
           WHERE entity_id='94000000-0000-4000-8000-000000000001'::uuid''',
    ).strip()


def run(
    *,
    user: str,
    host: str | None,
    port: int | None,
    psql: str,
    admin_database: str,
    database: str,
    source_revision: str,
    evidence: Path,
) -> int:
    client = PsqlClient(user=user, host=host, port=port, psql_executable=psql)
    _identifier(database)
    _recreate_scoped_database(
        client,
        admin_database,
        database,
        required_prefix="tpaa_acp216_",
    )
    try:
        client.run(database, historical_postgres_bootstrap_script())
        client.run(database, historical_postgres_verify_script())
        client.run(
            database,
            '''INSERT INTO "master"."entity" (
                   entity_id, session_id, entity_type, parent_entity_id,
                   alias, actual_side_affiliation, created_at
               ) VALUES (
                   '94000000-0000-4000-8000-000000000001'::uuid,
                   NULL, 'AIRCRAFT', NULL,
                   'ACP216-HISTORY-PROBE', 'BLUE',
                   '2026-10-03T00:00:00Z'::timestamptz
               )''',
        )
        before = _probe(client, database)

        client.run(database, postgres_upgrade_script())
        upgraded = verify_postgres(client, database)
        after_upgrade = _probe(client, database)

        client.run(
            database,
            '''INSERT INTO "registry"."mutation_idempotency" (
                   operation_code, request_id, request_hash,
                   result_object_type, result_object_id
               ) VALUES (
                   'ACP216_TEST', 'request-1',
                   'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                   'TEST', 'result-1'
               )''',
        )
        downgrade_error = client.run(
            database,
            postgres_downgrade_script(),
            expect_failure=True,
        )
        after_failed = verify_postgres(client, database)

        client.run(
            database,
            'DELETE FROM "registry"."mutation_idempotency"',
        )
        client.run(database, postgres_downgrade_script())
        client.run(database, historical_postgres_verify_script())
        after_downgrade = _probe(client, database)

        client.run(database, postgres_upgrade_script())
        reupgraded = verify_postgres(client, database)
        after_reupgrade = _probe(client, database)

        acceptance = {
            "historical_1_6_bootstrap_verified": before == PROBE_VALUE,
            "upgrade_to_1_7_verified": upgraded.schema_version == "1.7.0",
            "historical_row_exact_after_upgrade": after_upgrade == PROBE_VALUE,
            "nonempty_downgrade_fail_closed": (
                "ACP216_DOWNGRADE_NONEMPTY" in downgrade_error
            ),
            "failed_downgrade_preserves_1_7": after_failed.schema_version == "1.7.0",
            "empty_downgrade_to_1_6_verified": after_downgrade == PROBE_VALUE,
            "forward_reupgrade_to_1_7": reupgraded.schema_version == "1.7.0",
            "historical_row_exact_after_reupgrade": after_reupgrade == PROBE_VALUE,
        }
        failed = sorted(key for key, ok in acceptance.items() if ok is not True)
        payload = {
            "schema": SCHEMA,
            "proposal_id": "ACP-216",
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "source_db_schema_version": "1.6.0",
            "target_db_schema_version": "1.7.0",
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "target_verification": asdict(reupgraded),
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
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
    parser.add_argument("--database", default="tpaa_acp216_migration")
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
            source_revision=args.source_revision,
            evidence=args.evidence,
        )
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "proposal_id": "ACP-216",
            "source_revision": args.source_revision,
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
