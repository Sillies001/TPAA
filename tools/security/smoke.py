#!/usr/bin/env python3
"""M0 security/audit/data-governance smoke."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_application import JobAudit, M0JobControl  # noqa: E402
from tpaa_audit import (  # noqa: E402
    AuditEvent,
    DataClassification,
    DataPolicyError,
    DevelopmentDataGuard,
    InMemoryAuditSink,
    SecretFieldError,
    structured_record,
)


def run() -> dict[str, object]:
    sink = InMemoryAuditSink()

    def audit_job(event: JobAudit) -> None:
        sink.record(
            AuditEvent.create(
                actor=event.actor,
                action=event.action,
                request_id=event.job_id,
                reason=event.reason or "submitted",
                product_version="0.0.0",
                authority_hash=event.request_hash,
            )
        )

    jobs = M0JobControl(audit=audit_job)
    submitted = jobs.submit(
        idempotency_key="sec-smoke",
        command="diagnostic",
        payload={"classification": "SYNTHETIC"},
        actor="security-smoke",
    )
    jobs.cancel(
        job_id=submitted.record.job_id,
        actor="security-smoke",
        reason="smoke cleanup",
    )

    guard = DevelopmentDataGuard()
    guard.authorize(DataClassification.SYNTHETIC)
    controlled_blocked = False
    try:
        guard.authorize(DataClassification.SENSITIVE)
    except DataPolicyError:
        controlled_blocked = True

    secret_blocked = False
    try:
        structured_record(
            component="security-smoke",
            product_version="0.0.0",
            reason_code="SECRET_PROBE",
            fields={"authorization": "Bearer forbidden"},
        )
    except SecretFieldError:
        secret_blocked = True

    safe_record = structured_record(
        component="security-smoke",
        product_version="0.0.0",
        reason_code="PASS",
        fields={
            "request_id": submitted.record.job_id,
            "session_time_us": "9007199254740993",
        },
    )
    checks = {
        "job_audit_submit_cancel": len(sink.events) == 2
        and [event.action for event in sink.events] == ["JOB_SUBMIT", "JOB_CANCEL"],
        "controlled_data_fail_closed": controlled_blocked,
        "secret_field_fail_closed": secret_blocked,
        "system_business_time_separated": safe_record["system_time_utc"]
        != safe_record["session_time_us"],
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "TPAA_M0_SECURITY_SMOKE_V1",
        "status": status,
        "tasks": ["M0-SEC-001", "M0-SEC-002", "M0-SEC-003", "M0-SEC-004"],
        "checks": checks,
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
