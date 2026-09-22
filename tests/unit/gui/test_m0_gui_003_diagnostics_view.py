from __future__ import annotations

from dataclasses import dataclass

import pytest

from tpaa_gui import shell
from tpaa_gui.desktop import run_desktop
from tpaa_gui.diagnostics import (
    DiagnosticsIdentity,
    DiagnosticsSnapshot,
    diagnostics_lines,
    snapshot_from_http,
)
from tpaa_gui.local_backend import LocalBackendController, LocalBackendError


def _identity(version: str = "1.6.0") -> dict[str, str]:
    return {
        "product_build_version": "0.0.0",
        "core_baseline": "CB-1.4.0",
        "p1_metric_catalog_version": "P1-METRIC-CATALOG-1.0",
        "db_schema_version": version,
    }


def _snapshot(*, readiness: str = "READY", failure_code: str | None = None) -> DiagnosticsSnapshot:
    identity = DiagnosticsIdentity(
        product_build_version="0.0.0",
        core_baseline="CB-1.4.0",
        p1_metric_catalog_version="P1-METRIC-CATALOG-1.0",
        db_schema_version="1.6.0",
    )
    return DiagnosticsSnapshot(
        readiness=readiness,
        backend_state="READY" if readiness == "READY" else "EXITED",
        mismatches=() if readiness == "READY" else ("DB_SCHEMA_VERSION_MISMATCH",),
        failure_code=failure_code,
        expected=identity,
        observed=identity,
    )


def test_snapshot_projects_only_required_runtime_diagnostics() -> None:
    snapshot = snapshot_from_http(
        {"status": "NOT_READY", "ready": False, "mismatches": ["DB_SCHEMA_VERSION_MISMATCH"]},
        {"expected": _identity(), "observed": _identity("1.5.0")},
        backend_state="HTTP_HANDSHAKE",
    )

    assert snapshot.readiness == "NOT_READY"
    assert snapshot.mismatches == ("DB_SCHEMA_VERSION_MISMATCH",)
    assert snapshot.expected is not None and snapshot.expected.core_baseline == "CB-1.4.0"
    assert snapshot.observed is not None and snapshot.observed.db_schema_version == "1.5.0"
    assert "token" not in repr(snapshot).lower()


def test_lines_cover_readiness_build_core_catalog_schema_and_mismatch() -> None:
    lines = {object_name: text for object_name, _label, text in diagnostics_lines(_snapshot())}
    assert lines["tpaaDiagnosticsReadiness"] == "Readiness: READY"
    assert "Build: expected=0.0.0 observed=0.0.0" == lines["tpaaDiagnosticsBuild"]
    assert "Core baseline: expected=CB-1.4.0 observed=CB-1.4.0" == lines["tpaaDiagnosticsCore"]
    assert "P1 Catalog:" in lines["tpaaDiagnosticsCatalog"]
    assert "DB schema: expected=1.6.0 observed=1.6.0" == lines["tpaaDiagnosticsSchema"]
    assert lines["tpaaDiagnosticsMismatches"] == "Mismatches: NONE"


def test_real_backend_exposes_sanitized_ready_diagnostics() -> None:
    controller = LocalBackendController(startup_timeout_seconds=5)
    controller.start()
    try:
        snapshot = controller.diagnostics
        assert snapshot.readiness == "READY"
        assert snapshot.backend_state == "READY"
        assert snapshot.failure_code is None
        assert snapshot.expected is not None
        assert snapshot.expected.core_baseline == "CB-1.4.0"
        assert snapshot.expected.db_schema_version == "1.6.0"
        assert snapshot.expected.product_build_version == "0.0.0"
    finally:
        controller.shutdown()


def test_backend_crash_changes_effective_diagnostics_to_not_ready() -> None:
    controller = LocalBackendController(startup_timeout_seconds=5)
    controller.start()
    process = controller._process
    assert process is not None
    process.kill()
    process.wait(timeout=2)
    snapshot = controller.diagnostics
    assert snapshot.readiness == "NOT_READY"
    assert snapshot.backend_state == "NOT_READY"
    assert snapshot.failure_code == "BACKEND_EXITED"
    controller.shutdown()


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self) -> None:
        assert self.callback is not None
        self.callback()


class _Timer:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.timeout = _Signal()
        self.interval = None

    def start(self, interval: int) -> None:
        self.interval = interval


class _Widget:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.object_name = ""

    def setObjectName(self, value: str) -> None:
        self.object_name = value


class _Label(_Widget):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.text = text

    def setText(self, text: str) -> None:
        self.text = text


class _Layout:
    def __init__(self, parent=None) -> None:
        self.widgets: list[object] = []

    def addWidget(self, widget: object) -> None:
        self.widgets.append(widget)

    def addStretch(self, stretch: int) -> None:
        self.stretch = stretch


class _MainWindow(_Widget):
    def __init__(self) -> None:
        super().__init__()
        self.labels = {}

    def setWindowTitle(self, title: str) -> None:
        self.title = title

    def resize(self, width: int, height: int) -> None:
        self.size = (width, height)

    def setCentralWidget(self, widget: object) -> None:
        self.central = widget


@dataclass
class _QtCore:
    QTimer = _Timer


@dataclass
class _QtWidgets:
    QMainWindow = _MainWindow
    QWidget = _Widget
    QVBoxLayout = _Layout
    QLabel = _Label


def test_qt_view_renders_stable_diagnostics_labels_and_refreshes() -> None:
    current = [_snapshot()]
    window = shell._create_window(
        _QtCore,
        _QtWidgets,
        shell.GuiShellConfig(),
        diagnostics_provider=lambda: current[0],
    )
    labels = window._tpaa_diagnostics_labels
    assert labels["tpaaDiagnosticsReadiness"].text == "Readiness: READY"
    assert labels["tpaaDiagnosticsCore"].object_name == "tpaaDiagnosticsCore"
    assert window._tpaa_diagnostics_timer.interval == 500

    current[0] = _snapshot(readiness="NOT_READY", failure_code="BACKEND_EXITED")
    window._tpaa_diagnostics_timer.timeout.emit()
    assert labels["tpaaDiagnosticsReadiness"].text == "Readiness: NOT_READY"
    assert labels["tpaaDiagnosticsFailure"].text == "Lifecycle failure: BACKEND_EXITED"


def test_desktop_keeps_not_ready_shell_open_for_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _snapshot(readiness="NOT_READY", failure_code="READINESS_NOT_READY")
    events: list[str] = []

    class FakeBackend:
        @property
        def diagnostics(self) -> DiagnosticsSnapshot:
            return snapshot

        def start(self) -> None:
            events.append("start")
            raise LocalBackendError("READINESS_NOT_READY")

        def shutdown(self) -> None:
            events.append("shutdown")

    def fake_run_gui(*args: object, **kwargs: object) -> int:
        events.append("gui")
        provider = kwargs["diagnostics_provider"]
        assert provider().readiness == "NOT_READY"
        assert provider().failure_code == "READINESS_NOT_READY"
        return 0

    monkeypatch.setattr("tpaa_gui.desktop.run_gui", fake_run_gui)
    assert run_desktop(backend=FakeBackend()) == 0  # type: ignore[arg-type]
    assert events == ["start", "gui", "shutdown"]
