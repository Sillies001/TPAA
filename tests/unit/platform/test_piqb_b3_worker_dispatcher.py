from __future__ import annotations

import hashlib

import pytest

from tpaa_platform import (
    SpawnWorkerDispatcher,
    WorkerAdmissionController,
    WorkerBackpressureError,
    WorkerClosedError,
    WorkerPayload,
    WorkerTimeoutError,
)


def test_spawn_worker_dispatches_only_governed_serializable_commands() -> None:
    dispatcher = SpawnWorkerDispatcher(max_workers=1)
    echo = dispatcher.dispatch(
        WorkerPayload(
            job_id="job-echo",
            request_hash="a" * 64,
            command="ECHO",
            arguments=("alpha", "beta"),
        )
    )
    assert echo.status == "SUCCEEDED"
    assert echo.output == ("alpha", "beta")

    digest = dispatcher.dispatch(
        WorkerPayload(
            job_id="job-hash",
            request_hash="b" * 64,
            command="SHA256_TEXT",
            arguments=("alpha",),
        )
    )
    assert digest.status == "SUCCEEDED"
    assert digest.output == (hashlib.sha256(b"alpha").hexdigest(),)

    unsupported = dispatcher.dispatch(
        WorkerPayload(
            job_id="job-unsupported",
            request_hash="c" * 64,
            command="SHELL",
            arguments=("echo alpha",),
        )
    )
    assert unsupported.status == "FAILED"
    assert unsupported.error_code == "B3_WORKER_COMMAND_NOT_GOVERNED"
    assert dispatcher.drain(timeout_seconds=0.0) is True


def test_worker_admission_is_bounded_and_close_is_fail_closed() -> None:
    admission = WorkerAdmissionController(1)
    admission.acquire("job-1")
    assert admission.active_job_ids() == ("job-1",)

    with pytest.raises(WorkerBackpressureError):
        admission.acquire("job-2")

    assert admission.drain(timeout_seconds=0.0) is False
    admission.release("job-1")
    assert admission.drain(timeout_seconds=0.0) is True

    admission.close()
    with pytest.raises(WorkerClosedError):
        admission.acquire("job-3")


def test_spawn_worker_timeout_terminates_long_running_child() -> None:
    dispatcher = SpawnWorkerDispatcher(max_workers=1)
    with pytest.raises(WorkerTimeoutError, match="B3_WORKER_TIMEOUT"):
        dispatcher.dispatch(
            WorkerPayload(
                job_id="job-timeout",
                request_hash="d" * 64,
                command="SLEEP_MS",
                arguments=("3000",),
            ),
            timeout_seconds=1.0,
        )

    assert dispatcher.active_job_ids() == ()
    assert dispatcher.drain(timeout_seconds=0.0) is True
