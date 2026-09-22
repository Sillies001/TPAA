"""GUI-owned local backend lifecycle controller for M0-GUI-002."""

from __future__ import annotations

import json
import queue
import secrets
import subprocess
import sys
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from typing import IO, Any, Sequence

CONTROL_PROTOCOL = "TPAA_LOCAL_BACKEND_CONTROL_V1"
STARTUP_TIMEOUT_SECONDS = 10.0
GRACEFUL_SHUTDOWN_SECONDS = 5.0
TERMINATE_WAIT_SECONDS = 2.0


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
        child_command: Sequence[str] | None = None,
        startup_timeout_seconds: float = STARTUP_TIMEOUT_SECONDS,
        graceful_shutdown_seconds: float = GRACEFUL_SHUTDOWN_SECONDS,
        terminate_wait_seconds: float = TERMINATE_WAIT_SECONDS,
    ) -> None:
        if not product_build_version:
            raise ValueError("product_build_version must be non-empty")
        self._product_build_version = product_build_version
        self._child_command = tuple(
            child_command
            or (sys.executable, str(Path(__file__).resolve().parents[1] / "tpaa_api" / "local_backend_child.py"))
        )
        self._startup_timeout = startup_timeout_seconds
        self._graceful_shutdown = graceful_shutdown_seconds
        self._terminate_wait = terminate_wait_seconds
        self._process: subprocess.Popen[str] | None = None
        self._token: str | None = None
        self._port: int | None = None
        self._state = LocalBackendState.STOPPED
        self._failure_code: str | None = None

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
        self._token = secrets.token_urlsafe(32)
        self._process = subprocess.Popen(
            list(self._child_command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._state = LocalBackendState.SPAWNED
        try:
            self._send_control(
                {
                    "protocol": CONTROL_PROTOCOL,
                    "type": "START",
                    "bearer_token": self._token,
                    "product_build_version": self._product_build_version,
                }
            )
            self._state = LocalBackendState.CONFIG_SENT
            record = self._read_control(self._startup_timeout)
            self._accept_listening(record)
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
            except (BrokenPipeError, LocalBackendError, subprocess.TimeoutExpired):
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
        if readiness_status != 200 or readiness.get("ready") is not True or readiness.get("status") != "READY":
            raise LocalBackendError("READINESS_NOT_READY")
        version_status, version = self._get_json("/version")
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

    def __enter__(self) -> "LocalBackendController":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.shutdown()
