"""GUI-owned local backend lifecycle controller for M0-GUI-002."""

from __future__ import annotations

import json
import ntpath
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import IO, Any

from .diagnostics import EMPTY_DIAGNOSTICS, DiagnosticsSnapshot, snapshot_from_http

CONTROL_PROTOCOL = "TPAA_LOCAL_BACKEND_CONTROL_V1"
STARTUP_TIMEOUT_SECONDS = 10.0
GRACEFUL_SHUTDOWN_SECONDS = 5.0
TERMINATE_WAIT_SECONDS = 2.0
_LOCAL_HTTP_ALLOWED_PATHS = frozenset(
    {
        "/health",
        "/readiness",
        "/version",
        "/runtime/features",
        "/runtime/external-capabilities",
        "/runtime/operations",
        "/runtime/qualification",
        "/runtime/observability",
        "/jobs",
    }
)
_LOCAL_HTTP_ALLOWED_PREFIXES = (
    "/jobs/",
    "/m1/",
    "/m3/",
    "/m4/",
    "/m6/",
    "/m7/",
    "/m8/",
    "/m9/",
    "/api/v1/",
    "/security/",
)


def _prepare_child_spawn(
    command: Sequence[str],
    *,
    os_name: str | None = None,
    executable: str | None = None,
    base_executable: str | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str] | None]:
    """Return a spawn command that bypasses the Windows venv redirector.

    CPython's Windows venv ``python.exe`` is a redirector process. Spawning it
    directly would make ``Popen.pid`` refer to the redirector while the backend
    reports the PID of the real interpreter. CPython's own Windows
    multiprocessing launcher avoids that by spawning ``sys._base_executable``
    directly and setting ``__PYVENV_LAUNCHER__`` to the venv interpreter path.
    This keeps the virtual-environment semantics while preserving one real
    owned process/PID for lifecycle enforcement.
    """

    resolved_os_name = os.name if os_name is None else os_name
    resolved_executable = sys.executable if executable is None else executable
    resolved_base = (
        getattr(sys, "_base_executable", resolved_executable)
        if base_executable is None
        else base_executable
    )
    argv = list(command)

    if resolved_os_name != "nt" or not argv or not resolved_base:
        return argv, None

    def same_windows_path(left: str, right: str) -> bool:
        return ntpath.normcase(ntpath.abspath(left)) == ntpath.normcase(
            ntpath.abspath(right)
        )

    if not same_windows_path(argv[0], resolved_executable) or same_windows_path(
        resolved_executable, resolved_base
    ):
        return argv, None

    argv[0] = resolved_base
    child_env = dict(os.environ if environ is None else environ)
    child_env["__PYVENV_LAUNCHER__"] = resolved_executable
    return argv, child_env


class LocalBackendState(StrEnum):
    STOPPED = "STOPPED"
    SPAWNED = "SPAWNED"
    CONFIG_SENT = "CONFIG_SENT"
    LISTENING = "LISTENING"
    HTTP_HANDSHAKE = "HTTP_HANDSHAKE"
    READY = "READY"
    NOT_READY = "NOT_READY"
    SHUTDOWN_SENT = "SHUTDOWN_SENT"
    EXITED = "EXITED"


class LocalBackendError(RuntimeError):
    """Deterministic local-backend lifecycle failure."""


@dataclass(frozen=True)
class LocalBackendStatus:
    state: LocalBackendState
    ready: bool
    port: int | None
    pid: int | None
    failure_code: str | None = None


class LocalBackendController:
    """Own exactly one local FastAPI child process for the GUI process."""

    def __init__(
        self,
        *,
        product_build_version: str = "0.0.0",
        data_root: Path | None = None,
        child_command: Sequence[str] | None = None,
        startup_timeout_seconds: float = STARTUP_TIMEOUT_SECONDS,
        graceful_shutdown_seconds: float = GRACEFUL_SHUTDOWN_SECONDS,
        terminate_wait_seconds: float = TERMINATE_WAIT_SECONDS,
    ) -> None:
        if not product_build_version:
            raise ValueError("product_build_version must be non-empty")
        self._product_build_version = product_build_version
        if data_root is not None and not data_root.is_absolute():
            raise ValueError("data_root must be an absolute path")
        self._data_root = (
            None if data_root is None else data_root.resolve(strict=False)
        )
        self._child_command = tuple(
            child_command
            or (sys.executable, "-m", "tpaa_api.local_backend_child")
        )
        self._startup_timeout = startup_timeout_seconds
        self._graceful_shutdown = graceful_shutdown_seconds
        self._terminate_wait = terminate_wait_seconds
        self._process: subprocess.Popen[str] | None = None
        self._token: str | None = None
        self._port: int | None = None
        self._state = LocalBackendState.STOPPED
        self._failure_code: str | None = None
        self._baseline_diagnostics: DiagnosticsSnapshot = EMPTY_DIAGNOSTICS
        self._stdout_drain_thread: threading.Thread | None = None

    @property
    def diagnostics(self) -> DiagnosticsSnapshot:
        status = self.status
        return self._baseline_diagnostics.with_lifecycle(
            backend_state=status.state.value,
            backend_ready=status.ready,
            failure_code=status.failure_code,
        )

    @property
    def status(self) -> LocalBackendStatus:
        process = self._process
        if process is not None and process.poll() is not None and self._state not in {
            LocalBackendState.EXITED,
            LocalBackendState.STOPPED,
        }:
            self._state = LocalBackendState.NOT_READY
            self._failure_code = "BACKEND_EXITED"
        return LocalBackendStatus(
            state=self._state,
            ready=self._state is LocalBackendState.READY,
            port=self._port,
            pid=None if process is None else process.pid,
            failure_code=self._failure_code,
        )

    def start(self) -> LocalBackendStatus:
        if self._process is not None and self._process.poll() is None:
            raise LocalBackendError("BACKEND_ALREADY_RUNNING")
        self._failure_code = None
        self._port = None
        self._baseline_diagnostics = EMPTY_DIAGNOSTICS
        self._token = secrets.token_urlsafe(32)
        spawn_command, spawn_env = _prepare_child_spawn(self._child_command)
        self._process = subprocess.Popen(
            spawn_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=spawn_env,
        )
        self._state = LocalBackendState.SPAWNED
        try:
            start_record: dict[str, object] = {
                "protocol": CONTROL_PROTOCOL,
                "type": "START",
                "bearer_token": self._token,
                "product_build_version": self._product_build_version,
            }
            if self._data_root is not None:
                start_record["desktop_data_root"] = str(self._data_root)
            self._send_control(start_record)
            self._state = LocalBackendState.CONFIG_SENT
            record = self._read_control(self._startup_timeout)
            self._accept_listening(record)
            self._start_stdout_drain()
            self._state = LocalBackendState.LISTENING
            self._state = LocalBackendState.HTTP_HANDSHAKE
            self._perform_http_handshake()
            self._state = LocalBackendState.READY
            return self.status
        except Exception as exc:
            self._state = LocalBackendState.NOT_READY
            self._failure_code = str(exc) if isinstance(exc, LocalBackendError) else type(exc).__name__
            self.shutdown()
            raise

    def shutdown(self) -> LocalBackendStatus:
        process = self._process
        if process is None:
            self._state = LocalBackendState.EXITED
            self._clear_secret()
            return self.status
        if process.poll() is None:
            try:
                self._send_control({"protocol": CONTROL_PROTOCOL, "type": "SHUTDOWN"})
                self._state = LocalBackendState.SHUTDOWN_SENT
                process.wait(timeout=self._graceful_shutdown)
            except (
                BrokenPipeError,
                OSError,
                LocalBackendError,
                subprocess.TimeoutExpired,
            ):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=self._terminate_wait)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        self._state = LocalBackendState.EXITED
        self._port = None
        self._clear_secret()
        return self.status

    def _clear_secret(self) -> None:
        self._token = None

    def _send_control(self, payload: dict[str, object]) -> None:
        process = self._process
        if process is None or process.stdin is None or process.poll() is not None:
            raise LocalBackendError("CONTROL_CHANNEL_CLOSED")
        process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _read_control(self, timeout: float) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdout is None:
            raise LocalBackendError("CONTROL_CHANNEL_CLOSED")
        result: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

        def reader(stream: IO[str]) -> None:
            try:
                result.put(stream.readline())
            except BaseException as exc:  # pragma: no cover - defensive thread boundary
                result.put(exc)

        threading.Thread(target=reader, args=(process.stdout,), daemon=True).start()
        try:
            item = result.get(timeout=timeout)
        except queue.Empty as exc:
            raise LocalBackendError("STARTUP_TIMEOUT") from exc
        if isinstance(item, BaseException):
            raise LocalBackendError("CONTROL_READ_FAILED") from item
        if not item:
            raise LocalBackendError("CONTROL_CHANNEL_CLOSED")
        try:
            record = json.loads(item)
        except json.JSONDecodeError as exc:
            raise LocalBackendError("MALFORMED_CONTROL_RECORD") from exc
        if not isinstance(record, dict):
            raise LocalBackendError("MALFORMED_CONTROL_RECORD")
        return record

    def _start_stdout_drain(self) -> None:
        """Drain post-handshake child output so spawned workers cannot block.

        The control protocol emits exactly one child-to-parent LISTENING record.
        After it is consumed, any inherited stdout from libraries or spawned
        workers is non-protocol diagnostic noise and must not fill the pipe.
        """

        process = self._process
        if process is None or process.stdout is None:
            raise LocalBackendError("CONTROL_CHANNEL_CLOSED")

        def drain(stream: IO[str]) -> None:
            try:
                for _line in stream:
                    pass
            except (OSError, ValueError):
                pass

        thread = threading.Thread(
            target=drain,
            args=(process.stdout,),
            daemon=True,
            name="tpaa-local-backend-stdout-drain",
        )
        thread.start()
        self._stdout_drain_thread = thread

    def _accept_listening(self, record: dict[str, Any]) -> None:
        if record.get("protocol") != CONTROL_PROTOCOL or record.get("type") != "LISTENING":
            raise LocalBackendError("INVALID_LISTENING_RECORD")
        if "bearer_token" in record or "token" in record:
            raise LocalBackendError("SECRET_IN_CONTROL_RESPONSE")
        port = record.get("port")
        pid = record.get("pid")
        if not isinstance(port, int) or not (1 <= port <= 65535) or not isinstance(pid, int):
            raise LocalBackendError("INVALID_LISTENING_RECORD")
        if self._process is None or pid != self._process.pid:
            raise LocalBackendError("LISTENING_PID_MISMATCH")
        self._port = port

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        request_timeout_seconds: float | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Issue one authenticated product request while keeping the bearer private."""

        status = self.status
        if not status.ready or status.state is not LocalBackendState.READY:
            raise LocalBackendError("BACKEND_NOT_READY")
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST"}:
            raise LocalBackendError("LOCAL_HTTP_METHOD_FORBIDDEN")
        allowed_path = (
            path in _LOCAL_HTTP_ALLOWED_PATHS
            or any(path.startswith(prefix) for prefix in _LOCAL_HTTP_ALLOWED_PREFIXES)
        )
        if not allowed_path:
            raise LocalBackendError("LOCAL_HTTP_PATH_FORBIDDEN")
        supplied_headers = dict(headers or {})
        if any(
            key.lower() in {"authorization", "origin"}
            for key in supplied_headers
        ):
            raise LocalBackendError("LOCAL_HTTP_HEADER_FORBIDDEN")
        if self._port is None or self._token is None:
            raise LocalBackendError("HANDSHAKE_NOT_CONFIGURED")

        request_headers = {
            "Authorization": f"Bearer {self._token}",
            **supplied_headers,
        }
        data: bytes | None = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self._port}{path}",
            headers=request_headers,
            data=data,
            method=normalized_method,
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=(
                    self._startup_timeout
                    if request_timeout_seconds is None
                    else request_timeout_seconds
                ),
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise LocalBackendError("INVALID_HTTP_PAYLOAD")
                return response.status, payload
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                payload = {}
            return exc.code, payload if isinstance(payload, dict) else {}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise LocalBackendError("LOCAL_HTTP_REQUEST_FAILED") from exc

    def m1_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Compatibility adapter for the existing M1 workspace."""

        if method.upper() not in {"GET", "POST"}:
            raise LocalBackendError("M1_HTTP_METHOD_FORBIDDEN")
        if not path.startswith("/m1/"):
            raise LocalBackendError("M1_HTTP_PATH_FORBIDDEN")
        return self.request_json(
            method,
            path,
            body=body,
            headers=headers,
        )

    def source_request_bytes(
        self,
        path: str,
        *,
        data: bytes,
        content_type: str,
    ) -> tuple[int, dict[str, Any]]:
        """POST user-selected source bytes without exposing bearer state."""

        if not path.startswith("/api/v1/sources/"):
            raise LocalBackendError("SOURCE_HTTP_PATH_FORBIDDEN")
        if not data:
            raise LocalBackendError("SOURCE_HTTP_BODY_EMPTY")
        status = self.status
        if not status.ready or self._port is None or self._token is None:
            raise LocalBackendError("BACKEND_NOT_READY")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self._port}{path}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": content_type,
            },
            data=data,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._startup_timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise LocalBackendError("INVALID_HTTP_PAYLOAD")
                return response.status, payload
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                payload = {}
            return exc.code, payload if isinstance(payload, dict) else {}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise LocalBackendError("LOCAL_HTTP_REQUEST_FAILED") from exc

    def job_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Scoped formal job lifecycle adapter for P01."""

        if method.upper() not in {"GET", "POST"}:
            raise LocalBackendError("JOB_HTTP_METHOD_FORBIDDEN")
        if path != "/jobs" and not path.startswith("/jobs/"):
            raise LocalBackendError("JOB_HTTP_PATH_FORBIDDEN")
        return self.request_json(
            method,
            path,
            body=body,
            headers=headers,
            request_timeout_seconds=300.0 if method.upper() == "POST" else None,
        )

    def security_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, dict[str, Any]]:
        """Read the protected Desktop permission/approval surface."""

        if method.upper() != "GET":
            raise LocalBackendError("SECURITY_HTTP_METHOD_FORBIDDEN")
        if path != "/security/approvals":
            raise LocalBackendError("SECURITY_HTTP_PATH_FORBIDDEN")
        return self.request_json("GET", path)

    def _surface_request_json(
        self,
        surface: str,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST"}:
            raise LocalBackendError(f"{surface.upper()}_HTTP_METHOD_FORBIDDEN")
        if not path.startswith(f"/{surface}/"):
            raise LocalBackendError(f"{surface.upper()}_HTTP_PATH_FORBIDDEN")
        return self.request_json(
            normalized_method,
            path,
            body=None if body is None else dict(body),
            headers=None if headers is None else dict(headers),
        )

    def product_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Scoped transport for immutable Product API v1/discovery reads."""

        if method.upper() != "GET":
            raise LocalBackendError("PRODUCT_HTTP_METHOD_FORBIDDEN")
        if not path.startswith("/api/v1/"):
            raise LocalBackendError("PRODUCT_HTTP_PATH_FORBIDDEN")
        return self.request_json(
            method,
            path,
            body=body,
            headers=headers,
        )

    def m3_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Scoped transport for the existing M3 workspace."""

        return self._surface_request_json(
            "m3",
            method,
            path,
            body=body,
            headers=headers,
        )

    def m4_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Scoped transport for the existing M4 longitudinal/debrief workspace."""

        return self._surface_request_json("m4", method, path, body=body)

    def m6_request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
    ) -> tuple[int, Mapping[str, object]]:
        """Scoped transport for the admitted P2 workspace."""

        return self._surface_request_json("m6", method, path, body=body)

    def m7_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]:
        """Scoped transport for the admitted P3 workspace."""

        return self._surface_request_json("m7", method, path)

    def m8_request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
    ) -> tuple[int, Mapping[str, object]]:
        """Scoped transport for the admitted P4/P5 workspace."""

        return self._surface_request_json("m8", method, path, body=body)

    def m9_request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
    ) -> tuple[int, Mapping[str, object]]:
        """Scoped transport for the admitted P6 workspace."""

        return self._surface_request_json("m9", method, path, body=body)

    def runtime_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]:
        """Read the explicit product qualification/observability runtime state."""

        if method.upper() != "GET":
            raise LocalBackendError("RUNTIME_HTTP_METHOD_FORBIDDEN")
        if path not in {
            "/runtime/features",
            "/runtime/external-capabilities",
            "/runtime/operations",
            "/runtime/qualification",
            "/runtime/observability",
        }:
            raise LocalBackendError("RUNTIME_HTTP_PATH_FORBIDDEN")
        return self.request_json("GET", path)

    def _get_json(self, path: str) -> tuple[int, dict[str, Any]]:
        if self._port is None or self._token is None:
            raise LocalBackendError("HANDSHAKE_NOT_CONFIGURED")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self._port}{path}",
            headers={"Authorization": f"Bearer {self._token}"},
            method="GET",
        )
        deadline = time.monotonic() + self._startup_timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            process = self._process
            if process is None or process.poll() is not None:
                raise LocalBackendError("BACKEND_EXITED")
            try:
                with urllib.request.urlopen(request, timeout=0.5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise LocalBackendError("INVALID_HTTP_PAYLOAD")
                    return response.status, payload
            except urllib.error.HTTPError as exc:
                try:
                    payload = json.loads(exc.read().decode("utf-8"))
                except Exception:
                    payload = {}
                return exc.code, payload if isinstance(payload, dict) else {}
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = exc
                time.sleep(0.05)
        raise LocalBackendError("HTTP_HANDSHAKE_TIMEOUT") from last_error

    def _perform_http_handshake(self) -> None:
        readiness_status, readiness = self._get_json("/readiness")
        version_status, version = self._get_json("/version")
        self._baseline_diagnostics = snapshot_from_http(
            readiness,
            version,
            backend_state=LocalBackendState.HTTP_HANDSHAKE.value,
        )
        if readiness_status != 200 or readiness.get("ready") is not True or readiness.get("status") != "READY":
            raise LocalBackendError("READINESS_NOT_READY")
        if version_status != 200:
            raise LocalBackendError("VERSION_HANDSHAKE_FAILED")
        expected = version.get("expected")
        observed = version.get("observed")
        if not isinstance(expected, dict) or not isinstance(observed, dict):
            raise LocalBackendError("VERSION_HANDSHAKE_FAILED")
        if expected.get("product_build_version") != self._product_build_version:
            raise LocalBackendError("PRODUCT_BUILD_VERSION_MISMATCH")
        if expected != observed:
            raise LocalBackendError("VERSION_IDENTITY_MISMATCH")

    def __enter__(self) -> LocalBackendController:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.shutdown()
