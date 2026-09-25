"""PySide6 Desktop shell and read-only runtime diagnostics view.

M0-GUI-001 owns the process/window shell. M0-GUI-003 adds only rendering of
sanitized diagnostics snapshots. READY semantics and backend lifecycle remain
owned by lower authoritative layers and M0-GUI-002 respectively.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from .diagnostics import DiagnosticsSnapshot, diagnostics_lines
from .m1_workspace import M1DesktopTransport, create_m1_workspace


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


def _create_window(
    qt_core: Any,
    qt_widgets: Any,
    config: GuiShellConfig,
    diagnostics_provider: Callable[[], DiagnosticsSnapshot] | None = None,
    m1_transport: M1DesktopTransport | None = None,
) -> Any:
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

    if diagnostics_provider is not None:
        diagnostics_title = qt_widgets.QLabel("Runtime diagnostics", central)
        diagnostics_title.setObjectName("tpaaDiagnosticsTitle")
        layout.addWidget(diagnostics_title)
        diagnostic_labels: dict[str, Any] = {}
        for object_name, _label, text in diagnostics_lines(diagnostics_provider()):
            widget = qt_widgets.QLabel(text, central)
            widget.setObjectName(object_name)
            layout.addWidget(widget)
            diagnostic_labels[object_name] = widget

        def refresh_diagnostics() -> None:
            for object_name, _label, text in diagnostics_lines(diagnostics_provider()):
                diagnostic_labels[object_name].setText(text)

        refresh_timer = qt_core.QTimer(window)
        refresh_timer.timeout.connect(refresh_diagnostics)
        refresh_timer.start(500)
        window._tpaa_diagnostics_timer = refresh_timer
        window._tpaa_diagnostics_labels = diagnostic_labels

    if m1_transport is not None and diagnostics_provider is not None:
        workspace = create_m1_workspace(
            qt_core,
            qt_widgets,
            central,
            transport=m1_transport,
            diagnostics_provider=diagnostics_provider,
        )
        layout.addWidget(workspace)
        window._tpaa_m1_workspace = workspace

    layout.addStretch(1)
    window.setCentralWidget(central)
    return window


def run_gui(
    argv: Sequence[str] | None = None,
    *,
    config: GuiShellConfig | None = None,
    auto_close_ms: int | None = None,
    show: bool = True,
    diagnostics_provider: Callable[[], DiagnosticsSnapshot] | None = None,
    m1_transport: M1DesktopTransport | None = None,
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

    window = _create_window(
        qt_core,
        qt_widgets,
        shell_config,
        diagnostics_provider,
        m1_transport,
    )
    if show:
        window.show()

    if auto_close_ms is not None:
        qt_core.QTimer.singleShot(auto_close_ms, window.close)
        qt_core.QTimer.singleShot(auto_close_ms, app.quit)

    return int(app.exec())
