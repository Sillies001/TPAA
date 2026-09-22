from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "src" / "tpaa_gui" / "shell.py"
PYPROJECT = ROOT / "pyproject.toml"
STATUS = ROOT / "docs" / "developer" / "M0_STATUS.md"
PLAN = ROOT / "docs" / "implementation" / "M0-GUI-001_PYSIDE6_APPLICATION_SHELL.md"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_gui_shell_is_transport_only_and_does_not_own_backend_lifecycle() -> None:
    source = SHELL.read_text(encoding="utf-8")
    imports = _imports(SHELL)
    forbidden = {
        "tpaa_api",
        "tpaa_storage",
        "tpaa_canonical",
        "subprocess",
        "socket",
        "secrets",
        "httpx",
        "fastapi",
    }
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
    for token in ("Bearer", "LISTENING", "SHUTDOWN", "127.0.0.1"):
        assert token not in source


def test_pyside6_is_loaded_only_at_concrete_gui_edge() -> None:
    source = SHELL.read_text(encoding="utf-8")
    assert 'import_module("PySide6.QtCore")' in source
    assert 'import_module("PySide6.QtWidgets")' in source


def test_dependency_activation_and_dual_platform_acceptance_are_complete() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    assert '"pyside6==6.11.2"' in pyproject.lower()
    assert "[[tool.uv.index]]" not in pyproject
    assert "PySide6==6.11.2" in plan
    assert "Windows" in plan and "PASS" in plan
    assert "Linux" in plan and "PASS" in plan
    assert "COMPLETE" in plan
    assert "uv sync --locked" in plan
    assert "46-package" in plan


def test_status_keeps_gui_002_backend_lifecycle_separate() -> None:
    status = STATUS.read_text(encoding="utf-8")
    assert "M0-GUI-001" in status
    assert "M0-GUI-002" in status


def test_unified_developer_cli_exposes_gui_shell_and_smoke() -> None:
    dev = (ROOT / "tools" / "dev" / "tpaa_dev.py").read_text(encoding="utf-8")
    assert 'CommandSpec("run-gui", "M0-GUI-001", "IMPLEMENTED"' in dev
    assert 'CommandSpec("gui-smoke", "M0-GUI-001", "IMPLEMENTED"' in dev
    assert 'if command == "run-gui":' in dev
    assert 'if command == "gui-smoke":' in dev
