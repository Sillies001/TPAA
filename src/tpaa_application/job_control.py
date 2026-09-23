"""M0 job submission/query/cancel and idempotency skeleton.

This module intentionally does not execute M1 domain work. It freezes request identity,
idempotency-key behavior, and controlled job lifecycle at the Application boundary.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from tpaa_storage.hashing import canonical_request_hash


class JobStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    CANCELLED = "CANCELLED"


class BusinessStatus(StrEnum):
    VALID = "VALID"
    N_A = "N_A"
    INSUFFICIENT = "INSUFFICIENT"


class IdempotencyConflict(RuntimeError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"IDEMPOTENCY_KEY_CONFLICT key={key}")


class JobNotFound(LookupError):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"JOB_NOT_FOUND job_id={job_id}")


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    idempotency_key: str
    request_hash: str
    command: str
    status: JobStatus
    cancellation_reason: str | None = None


@dataclass(frozen=True)
class JobSubmission:
    record: JobRecord
    reused: bool


@dataclass(frozen=True)
class JobAudit:
    action: str
    actor: str
    job_id: str
    request_hash: str
    reason: str | None


AuditCallback = Callable[[JobAudit], None]


class M0JobControl:
    """Thread-safe in-memory M0 control skeleton with exact idempotency behavior."""

    def __init__(self, audit: AuditCallback | None = None) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self._idempotency: dict[str, str] = {}
        self._audit = audit

    def submit(
        self,
        *,
        idempotency_key: str,
        command: str,
        payload: dict[str, object],
        actor: str,
    ) -> JobSubmission:
        if not idempotency_key:
            raise ValueError("idempotency_key must be non-empty")
        if not command:
            raise ValueError("command must be non-empty")
        request_hash = canonical_request_hash({"command": command, "payload": payload})
        with self._lock:
            existing_job_id = self._idempotency.get(idempotency_key)
            if existing_job_id is not None:
                existing = self._jobs[existing_job_id]
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(idempotency_key)
                return JobSubmission(existing, reused=True)
            job_id = str(uuid.uuid4())
            record = JobRecord(
                job_id=job_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                command=command,
                status=JobStatus.SUBMITTED,
            )
            self._jobs[job_id] = record
            self._idempotency[idempotency_key] = job_id
        self._emit("JOB_SUBMIT", actor, record, None)
        return JobSubmission(record, reused=False)

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise JobNotFound(job_id)
        return record

    def cancel(self, *, job_id: str, actor: str, reason: str) -> JobRecord:
        if not reason:
            raise ValueError("reason must be non-empty")
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise JobNotFound(job_id)
            if record.status is JobStatus.CANCELLED:
                return record
            cancelled = JobRecord(
                job_id=record.job_id,
                idempotency_key=record.idempotency_key,
                request_hash=record.request_hash,
                command=record.command,
                status=JobStatus.CANCELLED,
                cancellation_reason=reason,
            )
            self._jobs[job_id] = cancelled
        self._emit("JOB_CANCEL", actor, cancelled, reason)
        return cancelled

    def _emit(self, action: str, actor: str, record: JobRecord, reason: str | None) -> None:
        if self._audit is not None:
            self._audit(
                JobAudit(
                    action=action,
                    actor=actor,
                    job_id=record.job_id,
                    request_hash=record.request_hash,
                    reason=reason,
                )
            )


def business_outcome(
    status: BusinessStatus,
    *,
    value: object = None,
    reason_code: str | None = None,
) -> dict[str, object]:
    """Project business validity separately from transport/system failures."""

    return {
        "outcome": "BUSINESS_STATUS",
        "business_status": status.value,
        "value": value,
        "reason_code": reason_code,
    }
