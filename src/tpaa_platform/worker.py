"""Spawn-compatible M0 worker payload and process smoke."""

from __future__ import annotations

import multiprocessing
import pickle
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


def _worker_echo(child: Connection, payload: WorkerPayload) -> None:
    child.send(payload)
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
