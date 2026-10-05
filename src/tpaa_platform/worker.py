"""Spawn-compatible governed worker commands and bounded dispatch."""

from __future__ import annotations

import hashlib
import importlib
import multiprocessing
import pickle
import threading
import time
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any


@dataclass(frozen=True)
class WorkerPayload:
    """Serializable job envelope; no inherited process state is required."""

    job_id: str
    request_hash: str
    command: str
    arguments: tuple[str, ...] = ()
    handler: str | None = None
    domain_payload: object | None = None


@dataclass(frozen=True)
class WorkerResult:
    job_id: str
    request_hash: str
    command: str
    status: str
    output: tuple[str, ...] = ()
    error_code: str | None = None
    domain_payload: object | None = None


GOVERNED_WORKER_HANDLERS = frozenset(
    {"tpaa_runtime.production_worker:execute"}
)


class WorkerDispatchError(RuntimeError):
    """Base fail-closed worker-dispatch error."""


class WorkerBackpressureError(WorkerDispatchError):
    pass


class WorkerClosedError(WorkerDispatchError):
    pass


class WorkerTimeoutError(WorkerDispatchError):
    pass


class WorkerCancelledError(WorkerDispatchError):
    pass


class WorkerAdmissionController:
    """Deterministic bounded admission independent of process implementation."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._condition = threading.Condition()
        self._active: set[str] = set()
        self._closed = False

    def acquire(self, job_id: str) -> None:
        if not job_id:
            raise ValueError("job_id must be non-empty")
        with self._condition:
            if self._closed:
                raise WorkerClosedError("worker dispatcher is closed")
            if job_id in self._active:
                raise WorkerBackpressureError(f"job already active: {job_id}")
            if len(self._active) >= self._capacity:
                raise WorkerBackpressureError(
                    f"worker capacity exhausted: {self._capacity}"
                )
            self._active.add(job_id)

    def release(self, job_id: str) -> None:
        with self._condition:
            self._active.discard(job_id)
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def active_job_ids(self) -> tuple[str, ...]:
        with self._condition:
            return tuple(sorted(self._active))

    def drain(self, *, timeout_seconds: float) -> bool:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            while self._active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True


def _worker_echo(child: Connection, payload: WorkerPayload) -> None:
    child.send(payload)
    child.close()


def _execute_command(payload: WorkerPayload) -> WorkerResult:
    command = payload.command
    if payload.handler is not None:
        if payload.handler not in GOVERNED_WORKER_HANDLERS:
            return WorkerResult(
                job_id=payload.job_id,
                request_hash=payload.request_hash,
                command=command,
                status="FAILED",
                error_code="B3_WORKER_HANDLER_NOT_GOVERNED",
            )
        module_name, function_name = payload.handler.split(":", 1)
        try:
            module = importlib.import_module(module_name)
            callback = getattr(module, function_name)
            result = callback(payload)
        except Exception:
            return WorkerResult(
                job_id=payload.job_id,
                request_hash=payload.request_hash,
                command=command,
                status="FAILED",
                error_code="B3_WORKER_HANDLER_FAILED",
            )
        if not isinstance(result, WorkerResult):
            return WorkerResult(
                job_id=payload.job_id,
                request_hash=payload.request_hash,
                command=command,
                status="FAILED",
                error_code="B3_WORKER_RESULT_INVALID",
            )
        return result
    if command == "ECHO":
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=command,
            status="SUCCEEDED",
            output=payload.arguments,
        )
    if command == "SHA256_TEXT":
        if len(payload.arguments) != 1:
            return WorkerResult(
                job_id=payload.job_id,
                request_hash=payload.request_hash,
                command=command,
                status="FAILED",
                error_code="B3_WORKER_ARGUMENTS_INVALID",
            )
        digest = hashlib.sha256(payload.arguments[0].encode("utf-8")).hexdigest()
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=command,
            status="SUCCEEDED",
            output=(digest,),
        )
    if command == "SLEEP_MS":
        if len(payload.arguments) != 1:
            return WorkerResult(
                job_id=payload.job_id,
                request_hash=payload.request_hash,
                command=command,
                status="FAILED",
                error_code="B3_WORKER_ARGUMENTS_INVALID",
            )
        try:
            milliseconds = int(payload.arguments[0])
        except ValueError:
            milliseconds = -1
        if not 0 <= milliseconds <= 60_000:
            return WorkerResult(
                job_id=payload.job_id,
                request_hash=payload.request_hash,
                command=command,
                status="FAILED",
                error_code="B3_WORKER_ARGUMENTS_INVALID",
            )
        time.sleep(milliseconds / 1000.0)
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=command,
            status="SUCCEEDED",
            output=(str(milliseconds),),
        )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=command,
        status="FAILED",
        error_code="B3_WORKER_COMMAND_NOT_GOVERNED",
    )


def _worker_execute(child: Connection, payload: WorkerPayload) -> None:
    try:
        child.send(_execute_command(payload))
    finally:
        child.close()


def serialize_worker_payload(payload: WorkerPayload) -> bytes:
    return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)


def run_spawn_echo(payload: WorkerPayload, *, timeout_seconds: float = 10.0) -> WorkerPayload:
    """Round-trip a payload through a real multiprocessing spawn context."""

    serialize_worker_payload(payload)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_worker_echo, args=(child, payload))
    process.start()
    child.close()
    try:
        if not parent.poll(timeout_seconds):
            process.terminate()
            process.join(timeout=2.0)
            raise RuntimeError("spawn worker timed out")
        received: Any = parent.recv()
    finally:
        parent.close()
    process.join(timeout=timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=2.0)
        raise RuntimeError("spawn worker did not exit")
    if process.exitcode != 0:
        raise RuntimeError(f"spawn worker exit code {process.exitcode}")
    if not isinstance(received, WorkerPayload):
        raise RuntimeError("spawn worker returned unexpected payload type")
    return received


class SpawnWorkerDispatcher:
    """Fresh-spawn governed worker dispatcher with bounded resource admission."""

    def __init__(self, *, max_workers: int = 2) -> None:
        self._admission = WorkerAdmissionController(max_workers)
        self._lock = threading.Lock()
        self._processes: dict[str, Any] = {}
        self._cancelled: set[str] = set()

    def active_job_ids(self) -> tuple[str, ...]:
        return self._admission.active_job_ids()

    def close(self) -> None:
        self._admission.close()

    def drain(self, *, timeout_seconds: float) -> bool:
        return self._admission.drain(timeout_seconds=timeout_seconds)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            process = self._processes.get(job_id)
            if process is None:
                return False
            self._cancelled.add(job_id)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2.0)
        return True

    def dispatch(
        self,
        payload: WorkerPayload,
        *,
        timeout_seconds: float = 30.0,
    ) -> WorkerResult:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        serialize_worker_payload(payload)
        self._admission.acquire(payload.job_id)

        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=_worker_execute, args=(child, payload))
        try:
            process.start()
            child.close()
            with self._lock:
                self._processes[payload.job_id] = process

            deadline = time.monotonic() + timeout_seconds
            received: Any | None = None
            while received is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=2.0)
                    raise WorkerTimeoutError(
                        f"B3_WORKER_TIMEOUT job_id={payload.job_id}"
                    )
                if parent.poll(min(0.05, remaining)):
                    received = parent.recv()
                    break
                with self._lock:
                    cancelled = payload.job_id in self._cancelled
                if cancelled:
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=2.0)
                    raise WorkerCancelledError(
                        f"B3_WORKER_CANCELLED job_id={payload.job_id}"
                    )
                if not process.is_alive():
                    if parent.poll(0):
                        received = parent.recv()
                        break
                    raise WorkerDispatchError(
                        "B3_WORKER_EXIT_WITHOUT_RESULT "
                        f"job_id={payload.job_id} exitcode={process.exitcode}"
                    )

            process.join(timeout=2.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2.0)
                raise WorkerDispatchError(
                    f"B3_WORKER_DID_NOT_EXIT job_id={payload.job_id}"
                )
            if process.exitcode != 0:
                raise WorkerDispatchError(
                    "B3_WORKER_NONZERO_EXIT "
                    f"job_id={payload.job_id} exitcode={process.exitcode}"
                )
            if not isinstance(received, WorkerResult):
                raise WorkerDispatchError(
                    f"B3_WORKER_RESULT_INVALID job_id={payload.job_id}"
                )
            if (
                received.job_id != payload.job_id
                or received.request_hash != payload.request_hash
                or received.command != payload.command
            ):
                raise WorkerDispatchError(
                    f"B3_WORKER_RESULT_IDENTITY_MISMATCH job_id={payload.job_id}"
                )
            return received
        finally:
            try:
                child.close()
            except OSError:
                pass
            parent.close()
            with self._lock:
                self._processes.pop(payload.job_id, None)
                self._cancelled.discard(payload.job_id)
            self._admission.release(payload.job_id)
