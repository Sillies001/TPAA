from __future__ import annotations

import pytest

from tpaa_application import (
    BusinessStatus,
    IdempotencyConflict,
    JobStatus,
    M0JobControl,
    business_outcome,
)


def test_same_idempotency_key_same_request_reuses_same_logical_job() -> None:
    control = M0JobControl()
    first = control.submit(
        idempotency_key="key-1",
        command="diagnostic",
        payload={"session_time_us": "9007199254740993"},
        actor="tester",
    )
    second = control.submit(
        idempotency_key="key-1",
        command="diagnostic",
        payload={"session_time_us": "9007199254740993"},
        actor="tester",
    )

    assert first.reused is False
    assert second.reused is True
    assert second.record.job_id == first.record.job_id
    assert second.record.request_hash == first.record.request_hash
    assert second.record.status is JobStatus.SUBMITTED


def test_same_key_different_request_conflicts() -> None:
    control = M0JobControl()
    control.submit(
        idempotency_key="key-1",
        command="diagnostic",
        payload={"value": "a"},
        actor="tester",
    )

    with pytest.raises(IdempotencyConflict):
        control.submit(
            idempotency_key="key-1",
            command="diagnostic",
            payload={"value": "b"},
            actor="tester",
        )


def test_cancel_requires_reason_and_preserves_request_identity() -> None:
    control = M0JobControl()
    submission = control.submit(
        idempotency_key="key-2",
        command="diagnostic",
        payload={},
        actor="tester",
    )
    cancelled = control.cancel(
        job_id=submission.record.job_id,
        actor="tester",
        reason="operator request",
    )

    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.request_hash == submission.record.request_hash
    assert cancelled.cancellation_reason == "operator request"


def test_business_status_is_not_system_error_envelope() -> None:
    payload = business_outcome(
        BusinessStatus.INSUFFICIENT,
        value=None,
        reason_code="NO_ELIGIBLE_DATA",
    )
    assert payload == {
        "outcome": "BUSINESS_STATUS",
        "business_status": "INSUFFICIENT",
        "value": None,
        "reason_code": "NO_ELIGIBLE_DATA",
    }
    assert "error" not in payload
