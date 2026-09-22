from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTS = REPO_ROOT / "src" / "tpaa_storage" / "ports.py"
ADAPTER = REPO_ROOT / "src" / "tpaa_storage" / "postgres_repository.py"
PLAN = REPO_ROOT / "docs" / "implementation" / "M0-STO-003_POSTGRESQL_SERVICE_REPOSITORY_SKELETON.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"


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


def test_plan_keeps_task_in_progress_until_dependency_and_real_server_gate() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    assert "**Status:** IN PROGRESS" in plan
    assert "psycopg[binary]==3.3.6" in plan
    assert "Application/FastAPI/PySide6" in plan


def test_dependency_is_not_claimed_active_before_uv_lock_can_be_regenerated() -> None:
    project = PYPROJECT.read_text(encoding="utf-8")
    assert "psycopg" not in project.lower()
