"""PySide6 application shell for M0-GUI-001.

This module deliberately owns only the Desktop process/UI shell.  Local backend
process ownership, token transfer, readiness handshake and crash recovery belong
to M0-GUI-002 and are intentionally absent here.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Sequence


class GuiShellError(RuntimeError):
    """Deterministic GUI shell failure."""


PYSIDE6_DEPENDENCY_MISSING = "PYSIDE6_DEPENDENCY_MISSING"


@dataclass(frozen=True)
class GuiShellConfig:
    """Transport-only configuration for the M0 Desktop shell."""

    application_name: str = "TPAA"
    window_title: str = "TPAA"
    width: int = 960
    height: int = 640


def _load_qt() -> tuple[Any, Any]:
    """Load Qt only at the concrete GUI adapter edge."""

    try:
        qt_core = import_module("PySide6.QtCore")
        qt_widgets = import_module("PySide6.QtWidgets")
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6" or (exc.name or "").startswith("PySide6."):
            raise GuiShellError(PYSIDE6_DEPENDENCY_MISSING) from exc
        raise
    return qt_core, qt_widgets


def _create_window(qt_widgets: Any, config: GuiShellConfig) -> Any:
    window = qt_widgets.QMainWindow()
    window.setObjectName("tpaaMainWindow")
    window.setWindowTitle(config.window_title)
    window.resize(config.width, config.height)

    central = qt_widgets.QWidget(window)
    central.setObjectName("tpaaShellCentralWidget")
    layout = qt_widgets.QVBoxLayout(central)

    title = qt_widgets.QLabel(config.application_name, central)
    title.setObjectName("tpaaShellTitle")
    status = qt_widgets.QLabel("Application shell initialized", central)
    status.setObjectName("tpaaShellStatus")

    layout.addWidget(title)
    layout.addWidget(status)
    layout.addStretch(1)
    window.setCentralWidget(central)
    return window


def run_gui(
    argv: Sequence[str] | None = None,
    *,
    config: GuiShellConfig | None = None,
    auto_close_ms: int | None = None,
    show: bool = True,
) -> int:
    """Start the PySide6 event loop and return its process exit code.

    ``auto_close_ms`` exists only to support deterministic startup/exit smoke
    testing.  Backend startup/readiness is intentionally not part of this task.
    """

    if auto_close_ms is not None and auto_close_ms < 0:
        raise ValueError("auto_close_ms must be non-negative")

    qt_core, qt_widgets = _load_qt()
    shell_config = config or GuiShellConfig()
    qt_argv = list(sys.argv if argv is None else argv)

    existing = qt_widgets.QApplication.instance()
    app = existing if existing is not None else qt_widgets.QApplication(qt_argv)
    app.setApplicationName(shell_config.application_name)

    window = _create_window(qt_widgets, shell_config)
    if show:
        window.show()

    if auto_close_ms is not None:
        qt_core.QTimer.singleShot(auto_close_ms, window.close)
        qt_core.QTimer.singleShot(auto_close_ms, app.quit)

    return int(app.exec())
