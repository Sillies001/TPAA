#!/usr/bin/env python3
"""Real M0-GUI-004 UI automation smoke for the composed Desktop runtime.

The harness intentionally uses the governed PySide6 runtime and stable GUI object
names.  It automates the actual composed Desktop process path in one process:
local-backend startup/READY, diagnostics discovery, window close, and backend
cleanup.  It does not reimplement READY semantics.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_gui import LocalBackendController, LocalBackendState, run_desktop

_REQUIRED_DIAGNOSTICS = (
    "tpaaDiagnosticsReadiness",
    "tpaaDiagnosticsMismatches",
    "tpaaDiagnosticsBuild",
    "tpaaDiagnosticsCore",
    "tpaaDiagnosticsCatalog",
    "tpaaDiagnosticsSchema",
)


def _find_main_window(qt_widgets: Any) -> Any | None:
    for widget in qt_widgets.QApplication.topLevelWidgets():
        if widget.objectName() == "tpaaMainWindow":
            return widget
    return None


def run_smoke(*, headless: bool = True, timeout_seconds: float = 30.0) -> dict[str, object]:
    """Automate launch -> READY diagnostics -> close -> backend cleanup."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6 import QtCore, QtWidgets
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6" or (exc.name or "").startswith("PySide6."):
            return {
                "m0_gui_004": {
                    "launch": "FAIL",
                    "backend_ready": "FAIL",
                    "diagnostics_visible": "FAIL",
                    "close": "FAIL",
                    "backend_cleanup": "FAIL",
                },
                "headless": headless,
                "failure": "PYSIDE6_DEPENDENCY_MISSING",
                "status": "FAIL",
            }
        raise

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["tpaa-ui-automation-smoke"])
    app.setQuitOnLastWindowClosed(True)

    controller = LocalBackendController(product_build_version="0.0.0", startup_timeout_seconds=10)
    checks: dict[str, str] = {
        "launch": "FAIL",
        "backend_ready": "FAIL",
        "diagnostics_visible": "FAIL",
        "close": "FAIL",
        "backend_cleanup": "FAIL",
    }
    failure: list[str] = []
    deadline = time.monotonic() + timeout_seconds
    close_requested = False

    poll_timer = QtCore.QTimer()
    poll_timer.setInterval(25)

    def fail(code: str) -> None:
        if not failure:
            failure.append(code)
        poll_timer.stop()
        app.quit()

    def poll() -> None:
        nonlocal close_requested
        if time.monotonic() >= deadline:
            fail("UI_AUTOMATION_TIMEOUT")
            return

        window = _find_main_window(QtWidgets)
        if window is None:
            return
        checks["launch"] = "PASS"

        readiness = window.findChild(QtWidgets.QLabel, "tpaaDiagnosticsReadiness")
        if readiness is None or readiness.text() != "Readiness: READY":
            return
        checks["backend_ready"] = "PASS"

        labels = [window.findChild(QtWidgets.QLabel, name) for name in _REQUIRED_DIAGNOSTICS]
        if any(label is None for label in labels):
            fail("DIAGNOSTICS_OBJECT_MISSING")
            return
        if not window.isVisible() or any(not label.isVisible() for label in labels if label is not None):
            return
        checks["diagnostics_visible"] = "PASS"

        close_requested = bool(window.close())
        checks["close"] = "PASS" if close_requested else "FAIL"
        poll_timer.stop()
        QtCore.QTimer.singleShot(0, app.quit)

    poll_timer.timeout.connect(poll)
    poll_timer.start()

    try:
        exit_code = run_desktop(
            ["tpaa-ui-automation-smoke"],
            show=True,
            backend=controller,
        )
    except Exception as exc:
        failure.append(type(exc).__name__)
        exit_code = 2

    exited = controller.status
    if exited.state is LocalBackendState.EXITED and not exited.ready and exited.port is None:
        checks["backend_cleanup"] = "PASS"

    if exit_code != 0:
        failure.append(f"GUI_EXIT_{exit_code}")
    if not close_requested and checks["close"] != "PASS":
        failure.append("WINDOW_CLOSE_NOT_ACCEPTED")

    passed = not failure and all(value == "PASS" for value in checks.values())
    result: dict[str, object] = {
        "m0_gui_004": checks,
        "headless": headless,
        "status": "PASS" if passed else "FAIL",
    }
    if failure:
        result["failure"] = failure[0]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="Use the native Qt platform instead of offscreen mode")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    result = run_smoke(headless=not args.show, timeout_seconds=args.timeout)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
