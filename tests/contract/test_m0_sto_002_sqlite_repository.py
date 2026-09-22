from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTS_PATH = REPO_ROOT / "src" / "tpaa_storage" / "ports.py"
ADAPTER_PATH = REPO_ROOT / "src" / "tpaa_storage" / "sqlite_repository.py"
PLAN_PATH = REPO_ROOT / "docs" / "implementation" / "M0-STO-002_SQLITE_DESKTOP_REPOSITORY_SKELETON.md"
POLICY_PATH = REPO_ROOT / "tools" / "storage" / "REPOSITORY_DB_ACCESS_POLICY.json"


def test_ports_do_not_import_concrete_database_drivers() -> None:
    tree = ast.parse(PORTS_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert imported.isdisjoint({"sqlite3", "psycopg", "sqlalchemy", "asyncpg", "alembic"})


def test_sqlite_adapter_matches_closed_adr_policy() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    sqlite = policy["sqlite"]
    uow = policy["unit_of_work"]
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert sqlite["driver"] == "python_stdlib.sqlite3"
    assert sqlite["journal_mode"] == "WAL"
    assert sqlite["writer_model"] == "single_backend_writer"
    assert uow["success_requires_explicit_commit"] is True
    assert uow["uncommitted_exit_rolls_back"] is True
    assert "import sqlite3" in source
    assert "BEGIN IMMEDIATE" in source
    assert "PRAGMA journal_mode" in source
    assert "bootstrap_sqlite" not in source


def test_task_plan_keeps_application_postgres_and_handshake_out_of_scope() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")
    assert "**Status:** COMPLETE" in plan
    assert "PostgreSQL/Psycopg adapter (M0-STO-003)" in plan
    assert "Application/FastAPI/PySide6 and M0-CORE-006" in plan


def test_developer_cli_runs_disposable_sqlite_repository_acceptance() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/dev/tpaa_dev.py", "db-sqlite-repository-acceptance"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["wal"] == "PASS"
    assert payload["single_writer"] == "PASS"
    assert payload["read_transaction"] == "PASS"
    assert payload["write_commit"] == "PASS"
    assert payload["uncommitted_exit_rollback"] == "PASS"
    assert payload["exception_rollback"] == "PASS"
