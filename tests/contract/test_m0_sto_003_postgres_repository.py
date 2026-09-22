from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTS = REPO_ROOT / "src" / "tpaa_storage" / "ports.py"
ADAPTER = REPO_ROOT / "src" / "tpaa_storage" / "postgres_repository.py"
PLAN = REPO_ROOT / "docs" / "implementation" / "M0-STO-003_POSTGRESQL_SERVICE_REPOSITORY_SKELETON.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
HARNESS = REPO_ROOT / "tools" / "storage" / "postgres_repository.py"


def test_shared_ports_remain_driver_neutral() -> None:
    tree = ast.parse(PORTS.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    assert imports.isdisjoint({"sqlite3", "psycopg", "sqlalchemy", "asyncpg", "alembic"})


def test_postgres_adapter_is_explicit_sync_driver_edge_without_runtime_migration() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    assert 'import_module("psycopg")' in source
    assert "autocommit=False" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert "%s" in source
    assert "sqlalchemy" not in source.lower()
    assert "asyncpg" not in source.lower()
    assert "alembic" not in source.lower()
    assert "postgres_bootstrap_script" not in source


def test_plan_records_complete_dependency_and_real_server_gate() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    assert "**Status:** COMPLETE" in plan
    assert "psycopg[binary]==3.3.6" in plan
    assert "Application/FastAPI/PySide6" in plan


def test_dependency_is_exactly_activated_in_governed_project() -> None:
    project = PYPROJECT.read_text(encoding="utf-8")
    assert '"psycopg[binary]==3.3.6"' in project
    assert "sqlalchemy" not in project.lower()
    assert "asyncpg" not in project.lower()
    assert "alembic" not in project.lower()


def test_repository_acceptance_uses_m0_sto_003_scoped_database_guard() -> None:
    source = HARNESS.read_text(encoding="utf-8")
    assert "_recreate_scoped_database" in source
    assert 'required_prefix="tpaa_m0_sto_003_"' in source
    assert "_recreate_acceptance_database" not in source
