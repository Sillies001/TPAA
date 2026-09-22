from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from tpaa_gui.local_backend import LocalBackendState

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "tools" / "gui" / "automation_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tpaa_m0_gui_004_automation_smoke", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self) -> None:
        assert self.callback is not None
        self.callback()


class _Timer:
    last = None

    def __init__(self) -> None:
        type(self).last = self
        self.timeout = _Signal()
        self.interval = None
        self.running = False

    def setInterval(self, value: int) -> None:
        self.interval = value

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    @staticmethod
    def singleShot(_delay: int, callback) -> None:
        callback()


class _Label:
    def __init__(self, text: str, visible: bool = True) -> None:
        self._text = text
        self._visible = visible

    def text(self) -> str:
        return self._text

    def isVisible(self) -> bool:
        return self._visible


class _Window:
    def __init__(self, *, missing: str | None = None) -> None:
        self._visible = True
        self.closed = False
        names = {
            "tpaaDiagnosticsReadiness": _Label("Readiness: READY"),
            "tpaaDiagnosticsMismatches": _Label("Mismatches: NONE"),
            "tpaaDiagnosticsBuild": _Label("Build: expected=0.0.0 observed=0.0.0"),
            "tpaaDiagnosticsCore": _Label("Core baseline: expected=CB-1.4.0 observed=CB-1.4.0"),
            "tpaaDiagnosticsCatalog": _Label("P1 Catalog: expected=P1 observed=P1"),
            "tpaaDiagnosticsSchema": _Label("DB schema: expected=1.6.0 observed=1.6.0"),
        }
        if missing:
            names.pop(missing)
        self.labels = names

    def objectName(self) -> str:
        return "tpaaMainWindow"

    def findChild(self, _kind, name: str):
        return self.labels.get(name)

    def isVisible(self) -> bool:
        return self._visible

    def close(self) -> bool:
        self.closed = True
        self._visible = False
        return True


class _Application:
    _instance = None
    windows: list[_Window] = []

    def __init__(self, _argv) -> None:
        type(self)._instance = self
        self.quit_called = False

    @classmethod
    def instance(cls):
        return cls._instance

    @classmethod
    def topLevelWidgets(cls):
        return list(cls.windows)

    def setQuitOnLastWindowClosed(self, _value: bool) -> None:
        pass

    def quit(self) -> None:
        self.quit_called = True


class _FakeController:
    def __init__(self, *args, **kwargs) -> None:
        self._status = types.SimpleNamespace(state=LocalBackendState.EXITED, ready=False, port=None)

    @property
    def status(self):
        return self._status


def _install_fake_pyside(monkeypatch: pytest.MonkeyPatch, window: _Window) -> None:
    _Application._instance = None
    _Application.windows = [window]
    _Timer.last = None
    qt_core = types.SimpleNamespace(QTimer=_Timer)
    qt_widgets = types.SimpleNamespace(QApplication=_Application, QLabel=_Label)
    package = types.ModuleType("PySide6")
    package.QtCore = qt_core
    package.QtWidgets = qt_widgets
    monkeypatch.setitem(sys.modules, "PySide6", package)


def test_automation_smoke_proves_launch_ready_visible_close_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    window = _Window()
    _install_fake_pyside(monkeypatch, window)
    monkeypatch.setattr(module, "LocalBackendController", _FakeController)

    def fake_run_desktop(*_args, **_kwargs) -> int:
        assert _Timer.last is not None
        _Timer.last.timeout.emit()
        return 0

    monkeypatch.setattr(module, "run_desktop", fake_run_desktop)
    result = module.run_smoke(headless=True, timeout_seconds=5)

    assert result["status"] == "PASS"
    assert result["m0_gui_004"] == {
        "launch": "PASS",
        "backend_ready": "PASS",
        "diagnostics_visible": "PASS",
        "close": "PASS",
        "backend_cleanup": "PASS",
    }
    assert window.closed is True


def test_automation_smoke_fails_closed_when_stable_diagnostics_object_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    _install_fake_pyside(monkeypatch, _Window(missing="tpaaDiagnosticsSchema"))
    monkeypatch.setattr(module, "LocalBackendController", _FakeController)

    def fake_run_desktop(*_args, **_kwargs) -> int:
        assert _Timer.last is not None
        _Timer.last.timeout.emit()
        return 0

    monkeypatch.setattr(module, "run_desktop", fake_run_desktop)
    result = module.run_smoke(headless=True, timeout_seconds=5)
    assert result["status"] == "FAIL"
    assert result["failure"] == "DIAGNOSTICS_OBJECT_MISSING"


def test_automation_smoke_rejects_non_positive_timeout() -> None:
    module = _load_module()
    with pytest.raises(ValueError, match="positive"):
        module.run_smoke(timeout_seconds=0)


def test_automation_smoke_reports_missing_pyside6_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    monkeypatch.delitem(sys.modules, "PySide6", raising=False)
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PySide6":
            exc = ModuleNotFoundError("No module named 'PySide6'")
            exc.name = "PySide6"
            raise exc
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = module.run_smoke(headless=True, timeout_seconds=5)
    assert result["status"] == "FAIL"
    assert result["failure"] == "PYSIDE6_DEPENDENCY_MISSING"
