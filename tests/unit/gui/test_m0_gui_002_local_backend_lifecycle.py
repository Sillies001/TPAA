from __future__ import annotations

import subprocess

import pytest

from tpaa_gui.desktop import run_desktop
from tpaa_gui.local_backend import LocalBackendController, LocalBackendError, LocalBackendState


def test_real_child_enters_ready_then_gracefully_exits() -> None:
    controller = LocalBackendController(startup_timeout_seconds=5)
    ready = controller.start()
    try:
        assert ready.state is LocalBackendState.READY
        assert ready.ready is True
        assert ready.port is not None and ready.port > 0
        assert ready.pid is not None
    finally:
        exited = controller.shutdown()
    assert exited.state is LocalBackendState.EXITED
    assert exited.ready is False
    assert exited.port is None


def test_handshake_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = LocalBackendController()
    responses = iter(
        [
            (503, {"status": "NOT_READY", "ready": False, "mismatches": ["DB_SCHEMA_VERSION_MISMATCH"]}),
        ]
    )
    monkeypatch.setattr(controller, "_get_json", lambda _path: next(responses))
    with pytest.raises(LocalBackendError, match="READINESS_NOT_READY"):
        controller._perform_http_handshake()


def test_backend_crash_immediately_revokes_ready() -> None:
    controller = LocalBackendController(startup_timeout_seconds=5)
    controller.start()
    process = controller._process
    assert process is not None
    process.kill()
    process.wait(timeout=2)
    status = controller.status
    assert status.state is LocalBackendState.NOT_READY
    assert status.ready is False
    assert status.failure_code == "BACKEND_EXITED"
    controller.shutdown()


def test_token_is_fresh_and_never_part_of_child_command(monkeypatch: pytest.MonkeyPatch) -> None:
    generated: list[int] = []

    def token_urlsafe(nbytes: int) -> str:
        generated.append(nbytes)
        return "unit-test-secret"

    monkeypatch.setattr("tpaa_gui.local_backend.secrets.token_urlsafe", token_urlsafe)
    controller = LocalBackendController(child_command=("python", "fake-child.py"))
    assert "unit-test-secret" not in " ".join(controller._child_command)
    assert generated == []


def test_run_desktop_owns_backend_for_entire_qt_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class FakeBackend:
        def start(self) -> None:
            events.append("start")

        def shutdown(self) -> None:
            events.append("shutdown")

    def fake_run_gui(*args: object, **kwargs: object) -> int:
        events.append("gui")
        return 7

    monkeypatch.setattr("tpaa_gui.desktop.run_gui", fake_run_gui)
    result = run_desktop(backend=FakeBackend())  # type: ignore[arg-type]
    assert result == 7
    assert events == ["start", "gui", "shutdown"]


def test_run_desktop_shutdowns_backend_even_if_gui_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class FakeBackend:
        def start(self) -> None:
            events.append("start")

        def shutdown(self) -> None:
            events.append("shutdown")

    def explode(*args: object, **kwargs: object) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr("tpaa_gui.desktop.run_gui", explode)
    with pytest.raises(RuntimeError, match="boom"):
        run_desktop(backend=FakeBackend())  # type: ignore[arg-type]
    assert events == ["start", "shutdown"]
