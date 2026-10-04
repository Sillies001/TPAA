from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tpaa_application import DurableJobControl, DurableJobControlError
from tpaa_storage import (
    ComputeJobRepository,
    ComputeJobState,
    SQLiteCanonicalRowRepository,
    bootstrap_sqlite,
)


def _clock() -> Callable[[], datetime]:
    current = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)

    def now() -> datetime:
        nonlocal current
        value = current
        current += timedelta(seconds=1)
        return value

    return now


def _control(connection: sqlite3.Connection) -> DurableJobControl:
    repository = ComputeJobRepository(SQLiteCanonicalRowRepository(connection))
    return DurableJobControl(repository, clock=_clock())


def test_durable_job_lifecycle_survives_sqlite_restart(tmp_path: Path) -> None:
    database = tmp_path / "jobs.sqlite3"
    bootstrap_sqlite(database)

    connection = sqlite3.connect(database)
    control = _control(connection)
    submission = control.submit(
        job_key="B3-JOB-001",
        job_type="ECHO",
        payload={"arguments": ["alpha"]},
    )
    assert submission.reused is False
    assert submission.record.status is ComputeJobState.SUBMITTED

    queued = control.queue(submission.record.job_id)
    assert queued.status is ComputeJobState.QUEUED
    running = control.start(submission.record.job_id)
    assert running.status is ComputeJobState.RUNNING
    assert running.started_at is not None
    progressed = control.update_progress(submission.record.job_id, 0.4)
    assert progressed.progress == 0.4
    connection.commit()
    connection.close()

    restarted_connection = sqlite3.connect(database)
    restarted = _control(restarted_connection)
    exact = restarted.get(submission.record.job_id)
    assert exact.status is ComputeJobState.RUNNING
    assert exact.progress == 0.4

    completed = restarted.succeed(submission.record.job_id)
    assert completed.status is ComputeJobState.SUCCEEDED
    assert completed.progress == 1.0
    assert completed.finished_at is not None
    restarted_connection.commit()
    restarted_connection.close()


def test_job_key_idempotency_and_transition_rules_fail_closed(tmp_path: Path) -> None:
    database = tmp_path / "jobs.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    control = _control(connection)

    first = control.submit(
        job_key="B3-JOB-IDEMPOTENT",
        job_type="SHA256_TEXT",
        payload={"text": "alpha"},
    )
    reused = control.submit(
        job_key="B3-JOB-IDEMPOTENT",
        job_type="SHA256_TEXT",
        payload={"text": "alpha"},
    )
    assert reused.reused is True
    assert reused.record == first.record

    with pytest.raises(
        DurableJobControlError,
        match="B3_JOB_IDEMPOTENCY_CONFLICT",
    ):
        control.submit(
            job_key="B3-JOB-IDEMPOTENT",
            job_type="SHA256_TEXT",
            payload={"text": "drift"},
        )

    with pytest.raises(
        DurableJobControlError,
        match="B3_JOB_TRANSITION_INVALID",
    ):
        control.succeed(first.record.job_id)

    queued = control.queue(first.record.job_id)
    assert queued.status is ComputeJobState.QUEUED
    cancelled = control.cancel(
        first.record.job_id,
        reason_code="USER_CANCELLED",
    )
    assert cancelled.status is ComputeJobState.CANCELLED
    assert cancelled.reason_codes == ("USER_CANCELLED",)

    with pytest.raises(
        DurableJobControlError,
        match="B3_JOB_TRANSITION_INVALID",
    ):
        control.start(first.record.job_id)
    connection.close()
