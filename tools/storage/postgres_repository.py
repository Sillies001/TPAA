#!/usr/bin/env python3
"""Run disposable M0-STO-003 PostgreSQL Repository/UoW acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_acceptance_database,
    bootstrap_postgres,
)
from tpaa_storage.postgres_repository import (  # noqa: E402
    PostgreSQLRepositoryError,
    postgres_repository_smoke,
)

DEFAULT_DATABASE = "tpaa_m0_sto_003_acceptance"


def run_acceptance(
    *,
    psql_client: PsqlClient,
    admin_database: str,
    database: str,
    conninfo_template: str,
) -> dict[str, object]:
    if not database.startswith("tpaa_m0_sto_003_"):
        raise ValueError("acceptance database name must start with 'tpaa_m0_sto_003_'")
    if "{database}" not in conninfo_template:
        raise ValueError("conninfo template must contain '{database}' placeholder")
    _recreate_acceptance_database(psql_client, admin_database, database)
    try:
        bootstrap = bootstrap_postgres(psql_client, database)
        repository = postgres_repository_smoke(conninfo_template.format(database=database))
        return {
            "bootstrap_verify": "PASS",
            "repository_conformance": "PASS",
            "transaction_smoke": "PASS",
            "bootstrap": {
                "engine_profile": bootstrap.engine_profile,
                "schema_version": bootstrap.schema_version,
                "table_count": bootstrap.table_count,
            },
            "repository": repository,
        }
    finally:
        if _database_exists(psql_client, admin_database, database):
            psql_client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = {_literal(database)} AND pid <> pg_backend_pid();\n"
                f"DROP DATABASE {_identifier(database)};\n",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--docker-container")
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--conninfo-template", required=True)
    args = parser.parse_args()
    client = PsqlClient(
        user=args.user,
        host=args.host,
        port=args.port,
        docker_container=args.docker_container,
        psql_executable=args.psql,
    )
    try:
        result = run_acceptance(
            psql_client=client,
            admin_database=args.admin_database,
            database=args.database,
            conninfo_template=args.conninfo_template,
        )
    except (PostgreSQLRepositoryError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
