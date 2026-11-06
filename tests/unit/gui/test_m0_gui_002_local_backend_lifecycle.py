from __future__ import annotations

import os
import subprocess

import pytest

from tpaa_gui.desktop import run_desktop
from tpaa_gui.local_backend import (
    LocalBackendController,
    LocalBackendError,
    LocalBackendState,
    _prepare_child_spawn,
)


def test_real_child_enters_ready_then_gracefully_exits(tmp_path) -> None:
    controller = LocalBackendController(
        startup_timeout_seconds=10,
        data_root=(tmp_path / "desktop-data").resolve(),
    )
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
            (
                200,
                {
                    "expected": {
                        "product_build_version": "0.0.0",
                        "core_baseline": "CB-1.4.0",
                        "p1_metric_catalog_version": "P1-METRIC-CATALOG-1.0",
                        "db_schema_version": "1.6.0",
                    },
                    "observed": {
                        "product_build_version": "0.0.0",
                        "core_baseline": "CB-1.4.0",
                        "p1_metric_catalog_version": "P1-METRIC-CATALOG-1.0",
                        "db_schema_version": "1.5.0",
                    },
                },
            ),
        ]
    )
    monkeypatch.setattr(controller, "_get_json", lambda _path: next(responses))
    with pytest.raises(LocalBackendError, match="READINESS_NOT_READY"):
        controller._perform_http_handshake()


def test_backend_crash_immediately_revokes_ready(tmp_path) -> None:
    controller = LocalBackendController(
        startup_timeout_seconds=10,
        data_root=(tmp_path / "desktop-data").resolve(),
    )
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


def test_windows_venv_spawn_bypasses_redirector_but_preserves_venv_identity() -> None:
    command, child_env = _prepare_child_spawn(
        (r"C:\repo\.venv\Scripts\python.exe", "child.py"),
        os_name="nt",
        executable=r"C:\repo\.venv\Scripts\python.exe",
        base_executable=r"C:\Python313\python.exe",
        environ={"KEEP": "1"},
    )

    assert command == [r"C:\Python313\python.exe", "child.py"]
    assert child_env == {
        "KEEP": "1",
        "__PYVENV_LAUNCHER__": r"C:\repo\.venv\Scripts\python.exe",
    }


def test_non_windows_spawn_keeps_interpreter_and_does_not_copy_environment() -> None:
    command, child_env = _prepare_child_spawn(
        ("/repo/.venv/bin/python", "child.py"),
        os_name="posix",
        executable="/repo/.venv/bin/python",
        base_executable="/usr/bin/python3.13",
        environ={"KEEP": "1"},
    )

    assert command == ["/repo/.venv/bin/python", "child.py"]
    assert child_env is None


def test_child_stderr_is_suppressed_by_default_and_can_be_inherited() -> None:
    production = LocalBackendController(child_command=("python", "fake-child.py"))
    diagnostic = LocalBackendController(
        child_command=("python", "fake-child.py"),
        child_stderr=None,
    )
    assert production._child_stderr is subprocess.DEVNULL
    assert diagnostic._child_stderr is None


def test_child_spawn_exports_source_import_root_when_no_venv_redirector_is_needed(
    tmp_path,
) -> None:
    import_root = tmp_path / "src"
    import_root.mkdir()
    existing_root = tmp_path / "additional-python-path"
    existing_root.mkdir()
    command, child_env = _prepare_child_spawn(
        ("C:/Python313/python.exe", "-m", "tpaa_api.local_backend_child"),
        os_name="nt",
        executable="C:/Python313/python.exe",
        base_executable="C:/Python313/python.exe",
        environ={"KEEP": "1", "PYTHONPATH": str(existing_root)},
        import_root=import_root,
    )

    assert command == ["C:/Python313/python.exe", "-m", "tpaa_api.local_backend_child"]
    assert child_env is not None
    assert child_env["KEEP"] == "1"
    assert child_env["PYTHONPATH"].split(os.pathsep) == [
        str(import_root),
        str(existing_root),
    ]


def test_child_spawn_preserves_source_import_root_with_windows_venv_redirector(
    tmp_path,
) -> None:
    import_root = tmp_path / "src"
    import_root.mkdir()
    command, child_env = _prepare_child_spawn(
        (r"C:\repo\.venv\Scripts\python.exe", "-m", "tpaa_api.local_backend_child"),
        os_name="nt",
        executable=r"C:\repo\.venv\Scripts\python.exe",
        base_executable=r"C:\Python313\python.exe",
        environ={"KEEP": "1"},
        import_root=import_root,
    )

    assert command == [
        r"C:\Python313\python.exe",
        "-m",
        "tpaa_api.local_backend_child",
    ]
    assert child_env is not None
    assert child_env["KEEP"] == "1"
    assert child_env["__PYVENV_LAUNCHER__"] == r"C:\repo\.venv\Scripts\python.exe"
    assert child_env["PYTHONPATH"].split(os.pathsep) == [str(import_root)]