from __future__ import annotations

import json

import pytest

from tpaa_audit import (
    AuditEvent,
    DataClassification,
    DataPolicyError,
    DevelopmentDataGuard,
    InMemoryAuditSink,
    SecretFieldError,
    structured_record,
)


def test_audit_event_requires_actor_request_reason_version_and_hash() -> None:
    sink = InMemoryAuditSink()
    event = AuditEvent.create(
        actor="developer",
        action="BASELINE_VALIDATE",
        request_id="req-1",
        reason="manual verification",
        product_version="0.0.0",
        authority_hash="a" * 64,
    )
    sink.record(event)
    payload = sink.events[0].as_dict()
    assert payload["actor"] == "developer"
    assert payload["request_id"] == "req-1"
    assert payload["reason"] == "manual verification"
    assert payload["product_version"] == "0.0.0"
    assert payload["authority_hash"] == "a" * 64
    assert payload["system_time_utc"]


def test_development_data_guard_allows_synthetic_public_and_blocks_controlled() -> None:
    guard = DevelopmentDataGuard()
    guard.authorize(DataClassification.SYNTHETIC)
    guard.authorize(DataClassification.PUBLIC)
    with pytest.raises(DataPolicyError):
        guard.authorize(DataClassification.OPERATIONAL)
    with pytest.raises(DataPolicyError):
        guard.authorize(DataClassification.SENSITIVE)
    guard.authorize(
        DataClassification.OPERATIONAL,
        approval_reference="APPROVAL-TEST-ONLY",
    )


def test_structured_observability_separates_system_and_business_time_and_rejects_secrets() -> None:
    record = structured_record(
        component="test",
        product_version="0.0.0",
        reason_code="OK",
        fields={
            "request_id": "req-1",
            "session_time_us": "9007199254740993",
        },
    )
    assert record["system_time_utc"] != record["session_time_us"]
    json.dumps(record)

    with pytest.raises(SecretFieldError):
        structured_record(
            component="test",
            product_version="0.0.0",
            reason_code="NOPE",
            fields={"bearer_token": "must-not-appear"},
        )
