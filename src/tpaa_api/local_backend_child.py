"""Isolated local FastAPI child process for M0-GUI-002."""

from __future__ import annotations

import json
import socket
import sys
import threading
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import uvicorn  # noqa: E402

from tpaa_api import create_desktop_app  # noqa: E402
from tpaa_application import (  # noqa: E402
    ApplicationService,
    build_trusted_runtime_status_use_case,
)

CONTROL_PROTOCOL = "TPAA_LOCAL_BACKEND_CONTROL_V1"


class _UnusedStorageUseCase:
    def execute(self) -> object:
        raise RuntimeError("storage baseline status is not part of local lifecycle handshake")


def _read_record() -> dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError("CONTROL_CHANNEL_CLOSED")
    record = json.loads(line)
    if not isinstance(record, dict):
        raise RuntimeError("MALFORMED_CONTROL_RECORD")
    return record


def _emit(record: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _application(product_build_version: str) -> ApplicationService:
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorageUseCase(),  # type: ignore[arg-type]
        get_runtime_baseline_status=build_trusted_runtime_status_use_case(
            product_build_version=product_build_version
        ),
    )


def main() -> int:
    start = _read_record()
    if start.get("protocol") != CONTROL_PROTOCOL or start.get("type") != "START":
        return 2
    token = start.get("bearer_token")
    build = start.get("product_build_version")
    if not isinstance(token, str) or not token or not isinstance(build, str) or not build:
        return 2

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(2048)
    port = int(sock.getsockname()[1])

    app = create_desktop_app(application=_application(build), bearer_token=token)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_config=None,
        access_log=False,
        server_header=False,
        date_header=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    _emit({"protocol": CONTROL_PROTOCOL, "type": "LISTENING", "pid": __import__("os").getpid(), "port": port})

    try:
        while True:
            record = _read_record()
            if record.get("protocol") != CONTROL_PROTOCOL:
                continue
            if record.get("type") == "SHUTDOWN":
                server.should_exit = True
                thread.join(timeout=4.5)
                return 0 if not thread.is_alive() else 3
    finally:
        server.should_exit = True
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
