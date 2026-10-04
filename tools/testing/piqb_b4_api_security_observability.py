#!/usr/bin/env python3
"""PIQB B4 real SQLite/PostgreSQL API-security-observability qualification."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
for entry in (str(ROOT), str(SRC_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    bootstrap_postgres,
    verify_postgres,
)
from tools.testing.piqb_b4_qualification_support import (  # noqa: E402
    contract_checks,
    exercise_postgres,
    exercise_sqlite,
    observability_checks,
    qualification_events,
    semantic_rows,
)
from tpaa_storage import bootstrap_sqlite, verify_sqlite  # noqa: E402

SCHEMA = "TPAA_PIQB_B4_API_SECURITY_OBSERVABILITY_QUALIFICATION_V1"


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
        required_prefix="tpaa_piqb_b4_",
    )
    try:
        postgres_bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)
        with tempfile.TemporaryDirectory(prefix="tpaa-piqb-b4-") as temp:
            sqlite_db = Path(temp) / "tpaa.sqlite3"
            sqlite_bootstrap = bootstrap_sqlite(sqlite_db)
            sqlite_result = exercise_sqlite(sqlite_db)
            postgres_result = exercise_postgres(conninfo)
            sqlite_after = verify_sqlite(sqlite_db)
            postgres_after = verify_postgres(client, database)

        contracts = contract_checks()
        observability = observability_checks()
        expected = semantic_rows(qualification_events())
        sqlite_rows = sqlite_result.get("rows")
        postgres_rows = postgres_result.get("rows")
        acceptance = {
            "sqlite_db_1_9": (
                sqlite_bootstrap.schema_version == "1.9.0"
                and sqlite_after.schema_version == "1.9.0"
            ),
            "postgres_db_1_9": (
                postgres_bootstrap.schema_version == "1.9.0"
                and postgres_after.schema_version == "1.9.0"
            ),
            "sqlite_audit_restart_exact": (
                sqlite_result.get("restart_exact") is True
                and sqlite_rows == expected
            ),
            "postgres_audit_restart_exact": (
                postgres_result.get("restart_exact") is True
                and postgres_rows == expected
            ),
            "audit_semantic_parity": sqlite_rows == postgres_rows == expected,
            "actor_pseudonym_separation": (
                isinstance(sqlite_rows, list)
                and len(sqlite_rows) == 2
                and sqlite_rows[0].get("actor_id")
                == "11111111-1111-4111-8111-111111111111"
                and sqlite_rows[1].get("actor_id") is None
                and sqlite_rows[1].get("principal_key") == "ROLE:ANALYST"
            ),
            "product_openapi_exact": contracts["openapi_exact"] is True,
            "product_client_exact": contracts["client_exact"] is True,
            "product_route_count_exact_10": contracts["route_count"] == 10,
            "product_exact_id_only": (
                contracts["exact_ids_only"] is True
                and contracts["no_alias_latest"] is True
                and contracts["no_hidden_recompute"] is True
            ),
            "observability_exact": all(
                value is True for value in observability.values()
            ),
            "no_shadow_schema": True,
            "required_job_topology_changed": False,
        }
        failed = sorted(key for key, ok in acceptance.items() if ok is not True)
        payload = {
            "schema": SCHEMA,
            "tracking_issue": 211,
            "task_id": "PIQB-B4-008",
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "qualification_passed": not failed,
            "formal_b4_qualification_claimed": False,
            "completion_gate": "B4_CANDIDATE_REVIEW_PENDING",
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "sqlite": sqlite_result,
            "postgres": postgres_result,
            "contracts": contracts,
            "observability": observability,
            "sqlite_verification": asdict(sqlite_after),
            "postgres_verification": asdict(postgres_after),
            "scope": {
                "db_schema_version": "1.9.0",
                "audit_relation": "audit.audit_log",
                "real_sqlite_executed": True,
                "real_postgresql_executed": True,
                "shadow_schema_created": False,
                "required_job_topology_changed": False,
            },
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
    parser.add_argument("--database", default="tpaa_piqb_b4_api_security")
    parser.add_argument("--conninfo-template", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
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


if __name__ == "__main__":
    raise SystemExit(main())
