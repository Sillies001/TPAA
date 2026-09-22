from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_APP = ROOT / "src" / "tpaa_api" / "app.py"
PYPROJECT = ROOT / "pyproject.toml"
API_SMOKE = ROOT / "tools" / "api" / "smoke.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_api_transport_depends_on_application_not_core_storage_or_gui() -> None:
    imports = _imports(API_APP)
    assert "tpaa_application" in imports
    assert not any(name.startswith("tpaa_canonical") for name in imports)
    assert not any(name.startswith("tpaa_storage") for name in imports)
    assert not any(name.startswith("tpaa_gui") for name in imports)
    assert not any(name.startswith("psycopg") for name in imports)
    assert not any(name.startswith("sqlite3") for name in imports)


def test_api_controller_does_not_own_ready_comparison_rules() -> None:
    source = API_APP.read_text(encoding="utf-8")
    assert "evaluate_runtime_baseline_handshake" not in source
    assert "RuntimeBaselineMismatch" not in source
    assert "DB_SCHEMA_VERSION_MISMATCH" not in source
    assert "CORE_BASELINE_MISMATCH" not in source


def test_fastapi_dependency_is_exactly_activated_in_project_and_lock() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")

    assert '"fastapi[standard-no-fastapi-cloud-cli]==0.141.1"' in pyproject
    assert '[[tool.uv.index]]' not in pyproject
    assert 'pypi.tuna.tsinghua.edu.cn' not in pyproject
    assert 'name = "fastapi"' in lock
    assert 'version = "0.141.1"' in lock
    assert 'source = { registry = "https://pypi.org/simple" }' in lock
    assert 'pypi.tuna.tsinghua.edu.cn' not in lock


def test_api_smoke_is_directly_executable_from_clean_checkout() -> None:
    result = subprocess.run(
        [sys.executable, str(API_SMOKE)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout
