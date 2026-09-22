from __future__ import annotations

from dataclasses import dataclass

import pytest

from tpaa_gui import GuiShellConfig
from tpaa_gui import shell


class _SignalTimer:
    calls: list[tuple[int, object]] = []

    @classmethod
    def singleShot(cls, delay: int, callback: object) -> None:
        cls.calls.append((delay, callback))
        callback()  # deterministic fake event delivery


class _Application:
    _instance = None

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.name = ""
        self.quit_called = False
        type(self)._instance = self

    @classmethod
    def instance(cls):
        return cls._instance

    def setApplicationName(self, name: str) -> None:
        self.name = name

    def quit(self) -> None:
        self.quit_called = True

    def exec(self) -> int:
        return 0


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


class _Layout:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.widgets: list[object] = []

    def addWidget(self, widget: object) -> None:
        self.widgets.append(widget)

    def addStretch(self, stretch: int) -> None:
        self.stretch = stretch


class _MainWindow(_Widget):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.size = (0, 0)
        self.central = None
        self.shown = False
        self.closed = False

    def setWindowTitle(self, title: str) -> None:
        self.title = title

    def resize(self, width: int, height: int) -> None:
        self.size = (width, height)

    def setCentralWidget(self, widget: object) -> None:
        self.central = widget

    def show(self) -> None:
        self.shown = True

    def close(self) -> None:
        self.closed = True


@dataclass
class _QtCore:
    QTimer = _SignalTimer


@dataclass
class _QtWidgets:
    QApplication = _Application
    QMainWindow = _MainWindow
    QWidget = _Widget
    QVBoxLayout = _Layout
    QLabel = _Label


def _reset() -> None:
    _Application._instance = None
    _SignalTimer.calls = []


def test_shell_starts_window_and_exits_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset()
    monkeypatch.setattr(shell, "_load_qt", lambda: (_QtCore, _QtWidgets))

    result = shell.run_gui(
        ["tpaa"],
        config=GuiShellConfig(application_name="TPAA Test", window_title="TPAA Test Window"),
        auto_close_ms=0,
    )

    assert result == 0
    assert _Application._instance is not None
    assert _Application._instance.name == "TPAA Test"
    assert _Application._instance.quit_called is True
    assert len(_SignalTimer.calls) == 2


def test_shell_can_run_hidden_for_platform_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset()
    monkeypatch.setattr(shell, "_load_qt", lambda: (_QtCore, _QtWidgets))
    assert shell.run_gui(["tpaa"], auto_close_ms=0, show=False) == 0


def test_shell_rejects_negative_auto_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shell, "_load_qt", lambda: (_QtCore, _QtWidgets))
    with pytest.raises(ValueError, match="non-negative"):
        shell.run_gui(["tpaa"], auto_close_ms=-1)


def test_missing_pyside6_fails_with_deterministic_code(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = shell.import_module

    def fail(name: str):
        if name.startswith("PySide6"):
            exc = ModuleNotFoundError("No module named 'PySide6'")
            exc.name = "PySide6"
            raise exc
        return real_import(name)

    monkeypatch.setattr(shell, "import_module", fail)
    with pytest.raises(shell.GuiShellError, match=shell.PYSIDE6_DEPENDENCY_MISSING):
        shell._load_qt()
