from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tools" / "gui" / "automation_smoke.py"
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
STATUS = ROOT / "docs" / "developer" / "M0_STATUS.md"
PLAN = ROOT / "docs" / "implementation" / "M0-GUI-004_UI_AUTOMATION_SMOKE_HARNESS.md"
PYPROJECT = ROOT / "pyproject.toml"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_harness_automates_real_composed_desktop_without_reimplementing_ready() -> None:
    source = HARNESS.read_text(encoding="utf-8")
    imports = _imports(HARNESS)
    assert "tpaa_gui" in imports
    assert "PySide6" in source
    assert "run_desktop" in source
    assert "tpaaMainWindow" in source
    assert "tpaaDiagnosticsReadiness" in source
    assert '"Readiness: READY"' in source
    assert "evaluate_runtime_baseline_handshake" not in source
    assert "CORE_BASELINE_MISMATCH" not in source


def test_harness_covers_sdib_launch_ready_close_and_backend_cleanup() -> None:
    source = HARNESS.read_text(encoding="utf-8")
    for check in ("launch", "backend_ready", "close", "backend_cleanup"):
        assert f'"{check}"' in source
    assert "diagnostics_visible" in source
    assert "LocalBackendState.EXITED" in source


def test_harness_uses_frozen_diagnostics_object_names() -> None:
    source = HARNESS.read_text(encoding="utf-8")
    for name in (
        "tpaaDiagnosticsReadiness",
        "tpaaDiagnosticsMismatches",
        "tpaaDiagnosticsBuild",
        "tpaaDiagnosticsCore",
        "tpaaDiagnosticsCatalog",
        "tpaaDiagnosticsSchema",
    ):
        assert name in source


def test_developer_dispatcher_exposes_m0_gui_004_smoke() -> None:
    source = DEV.read_text(encoding="utf-8")
    assert 'CommandSpec("ui-automation-smoke", "M0-GUI-004", "IMPLEMENTED"' in source
    assert 'if command == "ui-automation-smoke":' in source
    assert "automation_smoke.py" in source


def test_m0_gui_004_does_not_add_dependency_or_claim_cross_platform_ci() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    assert '"pyside6==6.11.2"' in pyproject.lower()
    assert "pytest-qt" not in pyproject.lower()
    assert "pyautogui" not in pyproject.lower()
    assert "Cross-platform CI" in plan
    assert "M0-GUI-004" in STATUS.read_text(encoding="utf-8")


def test_m0_gui_004_completion_status_and_windows_acceptance_are_recorded() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")
    assert "Status: **COMPLETE**" in plan
    assert "M0-GUI-004 — COMPLETE" in status
    for check in ("launch", "backend_ready", "diagnostics_visible", "close", "backend_cleanup"):
        assert check in plan
        assert check in status
    assert "uv sync --locked" in plan
    assert "uv lock --check" in plan
    assert "cross-platform CI is not claimed" in plan
