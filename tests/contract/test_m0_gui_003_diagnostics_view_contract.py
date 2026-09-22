from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTICS = ROOT / "src" / "tpaa_gui" / "diagnostics.py"
SHELL = ROOT / "src" / "tpaa_gui" / "shell.py"
DESKTOP = ROOT / "src" / "tpaa_gui" / "desktop.py"
STATUS = ROOT / "docs" / "developer" / "M0_STATUS.md"
PLAN = ROOT / "docs" / "implementation" / "M0-GUI-003_BASELINE_DIAGNOSTICS_VIEW.md"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_diagnostics_projection_is_gui_owned_and_transport_neutral() -> None:
    imports = _imports(DIAGNOSTICS)
    forbidden = {"tpaa_api", "tpaa_application", "tpaa_canonical", "tpaa_storage", "fastapi", "psycopg", "sqlite3"}
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
    assert "bearer_token" not in DIAGNOSTICS.read_text(encoding="utf-8")


def test_view_exposes_required_sd_ib_dimensions_with_stable_object_names() -> None:
    source = SHELL.read_text(encoding="utf-8")
    for object_name in (
        "tpaaDiagnosticsReadiness",
        "tpaaDiagnosticsMismatches",
        "tpaaDiagnosticsBuild",
        "tpaaDiagnosticsCore",
        "tpaaDiagnosticsCatalog",
        "tpaaDiagnosticsSchema",
    ):
        assert object_name in source or object_name in DIAGNOSTICS.read_text(encoding="utf-8")
    assert "QTimer" in source


def test_gui_does_not_recompute_core_ready_semantics() -> None:
    diagnostics_source = DIAGNOSTICS.read_text(encoding="utf-8")
    shell_source = SHELL.read_text(encoding="utf-8")
    desktop_source = DESKTOP.read_text(encoding="utf-8")
    combined = diagnostics_source + shell_source + desktop_source
    assert "evaluate_runtime_baseline_handshake" not in combined
    assert "CORE_BASELINE_MISMATCH" not in combined
    assert "DB_SCHEMA_VERSION_MISMATCH" not in combined


def test_not_ready_backend_can_still_open_diagnostics_shell_without_claiming_ready() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    assert "except LocalBackendError" in source
    assert "diagnostics_provider=lambda: controller.diagnostics" in source
    assert "controller.shutdown()" in source


def test_status_and_plan_mark_m0_gui_003_complete_but_leave_ui_automation_open() -> None:
    status = STATUS.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    assert "## M0-GUI-003 — COMPLETE" in status
    assert "Status: **COMPLETE**" in plan
    assert "M0-GUI-004" in plan
    assert "M0-GUI-004" in status
