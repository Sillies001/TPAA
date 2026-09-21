#!/usr/bin/env python3
"""Repository-controlled PostgreSQL bootstrap/readiness acceptance harness.

This M0-STO-001 tool deliberately uses an external ``psql`` client instead of
selecting a Python PostgreSQL driver. Repository DB-access technology remains
owned by open ADR-M0-004.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_storage.bootstrap import (  # noqa: E402
    BootstrapError,
    BootstrapVerification,
    postgres_bootstrap_script,
    postgres_empty_check_script,
    postgres_verify_script,
)

EXIT_OK = 0
EXIT_FAILURE = 1
DEFAULT_ACCEPTANCE_DATABASE = "tpaa_m0_sto_001_acceptance"


class PsqlExecutionError(RuntimeError):
    def __init__(self, *, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        detail = (stderr or stdout).strip()
        super().__init__(f"PSQL_EXECUTION_FAIL returncode={returncode} detail={detail}")


class SqlClient(Protocol):
    def run(self, database: str, sql: str, *, expect_failure: bool = False) -> str: ...


class PsqlClient:
    def __init__(
        self,
        *,
        user: str,
        host: str | None = None,
        port: int | None = None,
        docker_container: str | None = None,
        psql_executable: str = "psql",
    ) -> None:
        self.user = user
        self.host = host
        self.port = port
        self.docker_container = docker_container
        self.psql_executable = psql_executable

    def _command(self, database: str) -> list[str]:
        common = ["-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-U", self.user, "-d", database]
        if self.docker_container:
            docker = shutil.which("docker") or "docker"
            return [docker, "exec", "-i", self.docker_container, self.psql_executable, *common]
        command = [self.psql_executable, *common]
        if self.host:
            command.extend(["-h", self.host])
        if self.port is not None:
            command.extend(["-p", str(self.port)])
        return command

    def run(self, database: str, sql: str, *, expect_failure: bool = False) -> str:
        try:
            completed = subprocess.run(
                self._command(database),
                input=sql,
                text=True,
                capture_output=True,
                check=False,
                cwd=REPO_ROOT,
                env=os.environ.copy(),
            )
        except OSError as exc:
            raise PsqlExecutionError(returncode=127, stdout="", stderr=str(exc)) from exc
        if expect_failure:
            if completed.returncode == 0:
                raise RuntimeError("EXPECTED_PSQL_FAILURE_BUT_SUCCEEDED")
            return (completed.stderr or completed.stdout).strip()
        if completed.returncode != 0:
            raise PsqlExecutionError(
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return completed.stdout.strip()


def _single_value(output: str) -> str:
    values = [line.strip() for line in output.splitlines() if line.strip()]
    if len(values) != 1:
        raise RuntimeError(f"PSQL_OUTPUT_UNEXPECTED values={values!r}")
    return values[0]


def _empty_relation_count(client: PsqlClient, database: str) -> int:
    return int(_single_value(client.run(database, postgres_empty_check_script())))


def bootstrap_postgres(client: SqlClient, database: str) -> BootstrapVerification:
    client.run(database, postgres_bootstrap_script())
    return verify_postgres(client, database)


def verify_postgres(client: SqlClient, database: str) -> BootstrapVerification:
    output = _single_value(client.run(database, postgres_verify_script()))
    parts = output.split("|")
    if len(parts) != 9:
        raise RuntimeError(f"POSTGRES_VERIFY_OUTPUT_INVALID value={output!r}")
    engine, schema, baseline, artifact, authority_hash, lock_hash, physical_hash, catalog_hash, count = parts
    return BootstrapVerification(
        engine_profile=engine,
        schema_version=schema,
        core_baseline=baseline,
        authority_artifact_id=artifact,
        authority_sha256=authority_hash,
        baseline_lock_sha256=lock_hash,
        physical_schema_sha256=physical_hash,
        table_count=int(count),
        journal_mode="n/a",
        catalog_schema_sha256=catalog_hash,
    )


def fault_inject_postgres(client: SqlClient, database: str, *, after_tables: int = 4) -> None:
    before = _empty_relation_count(client, database)
    if before != 0:
        raise BootstrapError("TARGET_NOT_EMPTY", f"user_relation_count={before}")
    error = client.run(
        database,
        postgres_bootstrap_script(fault_after_tables=after_tables),
        expect_failure=True,
    )
    if "tpaa_intentional_bootstrap_fault" not in error:
        raise RuntimeError(f"FAULT_INJECTION_WRONG_FAILURE detail={error}")
    after = _empty_relation_count(client, database)
    if after != 0:
        raise RuntimeError(f"FAULT_INJECTION_PARTIAL_BOOTSTRAP user_relation_count={after}")


def _database_exists(client: SqlClient, admin_database: str, database: str) -> bool:
    sql = "SELECT COUNT(*) FROM pg_database WHERE datname = " + _literal(database) + ";\n"
    return _single_value(client.run(admin_database, sql)) == "1"


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _identifier(value: str) -> str:
    if not value or any(not (ch.isalnum() or ch == "_") for ch in value):
        raise ValueError(f"unsafe PostgreSQL identifier: {value!r}")
    return '"' + value + '"'


def _recreate_acceptance_database(client: SqlClient, admin_database: str, database: str) -> None:
    if not database.startswith("tpaa_m0_sto_001_"):
        raise ValueError("acceptance database name must start with 'tpaa_m0_sto_001_'")
    name = _identifier(database)
    if _database_exists(client, admin_database, database):
        client.run(
            admin_database,
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = {_literal(database)} AND pid <> pg_backend_pid();\n"
            f"DROP DATABASE {name};\n",
        )
    client.run(admin_database, f"CREATE DATABASE {name};\n")


def run_acceptance(
    client: SqlClient,
    *,
    admin_database: str,
    database: str = DEFAULT_ACCEPTANCE_DATABASE,
) -> dict[str, object]:
    results: dict[str, object] = {}
    _recreate_acceptance_database(client, admin_database, database)
    try:
        fault_inject_postgres(client, database)
        results["mid_bootstrap_rollback"] = "PASS"

        verified = bootstrap_postgres(client, database)
        results["clean_bootstrap_verify"] = "PASS"
        results["verification"] = asdict(verified)

        client.run(database, 'DROP TABLE "debrief"."annotation" CASCADE;\n')
        try:
            verify_postgres(client, database)
        except (PsqlExecutionError, RuntimeError):
            results["missing_table_fail_closed"] = "PASS"
        else:
            raise RuntimeError("MISSING_TABLE_NOT_DETECTED")

        _recreate_acceptance_database(client, admin_database, database)
        bootstrap_postgres(client, database)
        client.run(
            database,
            'UPDATE "public"."_tpaa_bootstrap_manifest" SET schema_version = \'9.9.9\';\n',
        )
        try:
            verify_postgres(client, database)
        except (PsqlExecutionError, RuntimeError):
            results["manifest_tamper_fail_closed"] = "PASS"
        else:
            raise RuntimeError("MANIFEST_TAMPER_NOT_DETECTED")

        _recreate_acceptance_database(client, admin_database, database)
        bootstrap_postgres(client, database)
        client.run(database, 'ALTER TABLE "debrief"."annotation" ADD COLUMN rogue text;\n')
        try:
            verify_postgres(client, database)
        except (PsqlExecutionError, RuntimeError):
            results["ddl_tamper_fail_closed"] = "PASS"
        else:
            raise RuntimeError("DDL_TAMPER_NOT_DETECTED")

        _recreate_acceptance_database(client, admin_database, database)
        bootstrap_postgres(client, database)
        client.run(
            database,
            'CREATE INDEX rogue_idx ON "debrief"."annotation" (annotation_id);\n',
        )
        try:
            verify_postgres(client, database)
        except (PsqlExecutionError, RuntimeError):
            results["unexpected_index_fail_closed"] = "PASS"
        else:
            raise RuntimeError("UNEXPECTED_INDEX_NOT_DETECTED")
    finally:
        if _database_exists(client, admin_database, database):
            client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = {_literal(database)} AND pid <> pg_backend_pid();\n"
                f"DROP DATABASE {_identifier(database)};\n",
            )
    return results


def _client_from_args(args: argparse.Namespace) -> PsqlClient:
    return PsqlClient(
        user=args.user,
        host=args.host,
        port=args.port,
        docker_container=args.docker_container,
        psql_executable=args.psql,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--docker-container")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("bootstrap", "verify", "fault-inject"):
        command = sub.add_parser(name)
        command.add_argument("database")
    acceptance = sub.add_parser("acceptance")
    acceptance.add_argument("--admin-database", default="postgres")
    acceptance.add_argument("--database", default=DEFAULT_ACCEPTANCE_DATABASE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = _client_from_args(args)
    try:
        if args.command == "bootstrap":
            result = bootstrap_postgres(client, args.database)
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
        elif args.command == "verify":
            result = verify_postgres(client, args.database)
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
        elif args.command == "fault-inject":
            fault_inject_postgres(client, args.database)
            print("POSTGRES_FAULT_INJECTION_PASS rollback_left_zero_user_relations")
        elif args.command == "acceptance":
            print(
                json.dumps(
                    run_acceptance(
                        client,
                        admin_database=args.admin_database,
                        database=args.database,
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            raise AssertionError(args.command)
    except (BootstrapError, PsqlExecutionError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
