"""No-shell process transport used by the governed worker boundary."""

from __future__ import annotations

import os
import subprocess
import sys


class IsolatedWorkerProcess:
    """Narrow lifecycle facade; business worker code never receives OS drivers."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    def poll(self) -> int | None:
        return self._process.poll()

    def communicate(self, *, input: bytes) -> tuple[bytes, bytes | None]:
        return self._process.communicate(input=input)

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()

    def wait(self, *, timeout: float | None = None) -> int:
        return self._process.wait(timeout=timeout)


def launch_worker() -> IsolatedWorkerProcess:
    executable = sys.executable
    environment: dict[str, str] | None = None
    if os.name == "nt":
        base_executable = getattr(sys, "_base_executable", executable)
        if isinstance(base_executable, str) and base_executable:
            environment = dict(os.environ)
            environment["__PYVENV_LAUNCHER__"] = executable
            executable = base_executable
    process = subprocess.Popen(
        [executable, "-m", "tpaa_platform.worker_child"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        shell=False,
    )
    return IsolatedWorkerProcess(process)


def stop_worker(process: IsolatedWorkerProcess) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
