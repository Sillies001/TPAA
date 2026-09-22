#!/usr/bin/env python3
"""Verify the frozen ADR-M0-004 Repository DB access technology decision."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "tools" / "storage" / "REPOSITORY_DB_ACCESS_POLICY.json"
ADR_PATH = REPO_ROOT / "docs" / "adr" / "ADR-M0-004-repository-db-access-implementation.md"
ARCHITECTURE_PATH = REPO_ROOT / "tools" / "architecture" / "ARCHITECTURE_POLICY.json"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _sqlite_transaction_spike() -> tuple[bool, str]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("BEGIN")
        connection.execute("INSERT INTO probe(value) VALUES (?)", ("rollback",))
        connection.rollback()
        if connection.execute("SELECT COUNT(*) FROM probe").fetchone() != (0,):
            return False, "rollback left a row"
        connection.execute("BEGIN")
        connection.execute("INSERT INTO probe(value) VALUES (?)", ("commit",))
        connection.commit()
        if connection.execute("SELECT value FROM probe").fetchall() != [("commit",)]:
            return False, "commit did not persist exactly one row"
        return True, "stdlib sqlite3 explicit rollback/commit semantics PASS"
    finally:
        connection.close()


def verify() -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    adr = ADR_PATH.read_text(encoding="utf-8")
    architecture = json.loads(ARCHITECTURE_PATH.read_text(encoding="utf-8"))
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")

    record(
        "policy_frozen",
        policy.get("schema") == "TPAA_REPOSITORY_DB_ACCESS_POLICY_V1"
        and policy.get("status") == "FROZEN"
        and policy.get("decision_id") == "ADR-M0-004",
        f"schema={policy.get('schema')} status={policy.get('status')} decision_id={policy.get('decision_id')}",
    )
    record("adr_closed", "**Status:** CLOSED" in adr, ADR_PATH.relative_to(REPO_ROOT).as_posix())

    sqlite = policy.get("sqlite", {})
    postgres = policy.get("postgresql", {})
    uow = policy.get("unit_of_work", {})
    ports = policy.get("repository_ports", {})
    migration = policy.get("migration", {})

    record(
        "sqlite_decision",
        isinstance(sqlite, dict)
        and sqlite.get("driver") == "python_stdlib.sqlite3"
        and sqlite.get("api_mode") == "synchronous_dbapi"
        and sqlite.get("journal_mode") == "WAL"
        and sqlite.get("writer_model") == "single_backend_writer",
        "stdlib sqlite3 / sync DB-API / WAL / single backend writer",
    )
    record(
        "postgres_decision",
        isinstance(postgres, dict)
        and postgres.get("driver") == "psycopg"
        and postgres.get("driver_generation") == 3
        and postgres.get("decision_reference_version") == "3.3.6"
        and postgres.get("api_mode") == "synchronous_dbapi",
        "Psycopg 3.3.6 decision reference / synchronous DB-API",
    )
    record(
        "port_isolation",
        isinstance(ports, dict)
        and ports.get("package") == "tpaa_storage.ports"
        and ports.get("driver_types_forbidden") is True
        and ports.get("dialect_branches_forbidden") is True,
        "tpaa_storage.ports is engine-neutral",
    )
    record(
        "uow_semantics",
        isinstance(uow, dict)
        and uow.get("required") is True
        and uow.get("repository_commit_forbidden") is True
        and uow.get("success_requires_explicit_commit") is True
        and uow.get("exception_rolls_back") is True
        and uow.get("uncommitted_exit_rolls_back") is True,
        "explicit commit; repository commit forbidden; fail-closed rollback",
    )
    record(
        "migration_boundary",
        isinstance(migration, dict)
        and migration.get("service_ci_mechanism") == "Alembic"
        and migration.get("authority_role") == "execution/history mechanism only"
        and migration.get("autogenerate_as_authority_forbidden") is True
        and migration.get("runtime_repository_auto_migrate_forbidden") is True,
        "Alembic is migration mechanism only; Canonical remains schema authority",
    )

    forbidden = architecture.get("forbidden_external_prefixes", {})
    storage_forbidden = set(forbidden.get("tpaa_storage", [])) if isinstance(forbidden, dict) else set()
    record(
        "runtime_abstraction_guard",
        storage_forbidden == {"sqlalchemy", "alembic", "asyncpg"},
        f"tpaa_storage forbidden external prefixes={sorted(storage_forbidden)}",
    )
    application_forbidden = set(forbidden.get("tpaa_application", [])) if isinstance(forbidden, dict) else set()
    gui_forbidden = set(forbidden.get("tpaa_gui", [])) if isinstance(forbidden, dict) else set()
    record(
        "upper_layer_driver_guard",
        {"sqlite3", "psycopg"}.issubset(application_forbidden)
        and {"sqlite3", "psycopg"}.issubset(gui_forbidden),
        "Application/GUI concrete DB-driver imports remain forbidden",
    )

    spike_ok, spike_detail = _sqlite_transaction_spike()
    record("sqlite_transaction_spike", spike_ok, spike_detail)

    record(
        "psycopg_dependency_activated",
        '"psycopg[binary]==3.3.6"' in pyproject
        and "sqlalchemy" not in pyproject.lower()
        and "alembic" not in pyproject.lower()
        and "asyncpg" not in pyproject.lower(),
        "M0-STO-003 activated exact Psycopg 3.3.6; rejected runtime abstractions remain absent",
    )

    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "evidence_schema": "TPAA_ADR_M0_004_EVIDENCE_V1",
        "status": status,
        "decision": "ADR-M0-004",
        "checks": checks,
        "execution_limitations": [
            "The Chat host remains network-isolated; dependency resolution/import evidence for Psycopg 3.3.6 was produced on the governed Windows CPython 3.13 environment.",
            "Real PostgreSQL Service Repository acceptance for M0-STO-003 was executed against the governed PostgreSQL 16 container and recorded in the implementation record.",
            "Cross-platform Windows/Linux CI is not claimed by this verifier.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    payload = verify()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.evidence:
        target = args.evidence if args.evidence.is_absolute() else REPO_ROOT / args.evidence
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
