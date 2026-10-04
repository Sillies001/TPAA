"""PIQB B3 durable compute-job lifecycle semantics."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid5

from tpaa_storage.compute_job import (
    ComputeJobRecord,
    ComputeJobRepository,
    ComputeJobState,
)
from tpaa_storage.hashing import canonical_request_hash

B3_JOB_COMPONENT_VERSION = "PIQB-B3-JOB-CONTROL-1.0.0"
B3_JOB_NAMESPACE = UUID("a8f9b36f-4da2-57c7-93bc-a544c7a4fb2e")

_ALLOWED_TRANSITIONS: dict[ComputeJobState, frozenset[ComputeJobState]] = {
    ComputeJobState.SUBMITTED: frozenset(
        {ComputeJobState.QUEUED, ComputeJobState.CANCELLED}
    ),
    ComputeJobState.QUEUED: frozenset(
        {
            ComputeJobState.RUNNING,
            ComputeJobState.FAILED,
            ComputeJobState.CANCELLED,
        }
    ),
    ComputeJobState.RUNNING: frozenset(
        {
            ComputeJobState.SUCCEEDED,
            ComputeJobState.FAILED,
            ComputeJobState.CANCELLED,
        }
    ),
    ComputeJobState.SUCCEEDED: frozenset(),
    ComputeJobState.FAILED: frozenset(),
    ComputeJobState.CANCELLED: frozenset(),
}


class DurableJobControlError(RuntimeError):
    """Fail-closed lifecycle error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class DurableJobSubmission:
    record: ComputeJobRecord
    reused: bool


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _time_text(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def _require_token(value: str, *, field: str) -> None:
    if not value or value.strip() != value:
        raise DurableJobControlError("B3_JOB_TOKEN_INVALID", field)


class DurableJobControl:
    """Application lifecycle rules over the durable DB 1.9 compute-job authority."""

    def __init__(
        self,
        repository: ComputeJobRepository,
        *,
        clock: Clock = _utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def submit(
        self,
        *,
        job_key: str,
        job_type: str,
        payload: Mapping[str, object],
        session_id: str | None = None,
        episode_id: str | None = None,
    ) -> DurableJobSubmission:
        _require_token(job_key, field="job_key")
        _require_token(job_type, field="job_type")
        input_hash = canonical_request_hash(
            {"job_type": job_type, "payload": dict(payload)}
        )
        job_id = str(uuid5(B3_JOB_NAMESPACE, f"{job_key}|{input_hash}"))

        existing = self._repository.by_job_key(job_key)
        if existing is not None:
            if (
                existing.job_id == job_id
                and existing.job_type == job_type
                and existing.input_hash == input_hash
            ):
                return DurableJobSubmission(existing, reused=True)
            raise DurableJobControlError(
                "B3_JOB_IDEMPOTENCY_CONFLICT",
                job_key,
            )

        record = ComputeJobRecord(
            job_id=job_id,
            job_type=job_type,
            session_id=session_id,
            episode_id=episode_id,
            job_key=job_key,
            status=ComputeJobState.SUBMITTED,
            component_version=B3_JOB_COMPONENT_VERSION,
            input_hash=input_hash,
            progress=0.0,
            reason_codes=(),
            error_detail=None,
            created_at=_time_text(self._clock()),
            started_at=None,
            finished_at=None,
        )
        reused = self._repository.insert_exact(record)
        return DurableJobSubmission(record=self._repository.exact(job_id), reused=reused)

    def get(self, job_id: str) -> ComputeJobRecord:
        return self._repository.exact(job_id)

    def queue(self, job_id: str) -> ComputeJobRecord:
        return self._transition(job_id, ComputeJobState.QUEUED)

    def start(self, job_id: str) -> ComputeJobRecord:
        return self._transition(job_id, ComputeJobState.RUNNING)

    def succeed(self, job_id: str) -> ComputeJobRecord:
        return self._transition(
            job_id,
            ComputeJobState.SUCCEEDED,
            progress=1.0,
        )

    def fail(
        self,
        job_id: str,
        *,
        reason_code: str,
        error_detail: str | None = None,
    ) -> ComputeJobRecord:
        _require_token(reason_code, field="reason_code")
        return self._transition(
            job_id,
            ComputeJobState.FAILED,
            reason_codes=(reason_code,),
            error_detail=error_detail,
        )

    def cancel(self, job_id: str, *, reason_code: str) -> ComputeJobRecord:
        _require_token(reason_code, field="reason_code")
        return self._transition(
            job_id,
            ComputeJobState.CANCELLED,
            reason_codes=(reason_code,),
        )

    def update_progress(self, job_id: str, progress: float) -> ComputeJobRecord:
        current = self._repository.exact(job_id)
        if current.status is not ComputeJobState.RUNNING:
            raise DurableJobControlError(
                "B3_JOB_PROGRESS_STATE_INVALID",
                current.status.value,
            )
        if not 0.0 <= progress < 1.0 or progress < current.progress:
            raise DurableJobControlError(
                "B3_JOB_PROGRESS_INVALID",
                str(progress),
            )
        return self._repository.cas_update(
            job_id=job_id,
            expected_state=ComputeJobState.RUNNING,
            state=ComputeJobState.RUNNING,
            progress=progress,
            reason_codes=current.reason_codes,
            error_detail=current.error_detail,
            started_at=current.started_at,
            finished_at=None,
        )

    def _transition(
        self,
        job_id: str,
        state: ComputeJobState,
        *,
        progress: float | None = None,
        reason_codes: tuple[str, ...] = (),
        error_detail: str | None = None,
    ) -> ComputeJobRecord:
        current = self._repository.exact(job_id)
        if state not in _ALLOWED_TRANSITIONS[current.status]:
            raise DurableJobControlError(
                "B3_JOB_TRANSITION_INVALID",
                f"{current.status.value}->{state.value}",
            )
        now = _time_text(self._clock())
        started_at = current.started_at
        if state is ComputeJobState.RUNNING and started_at is None:
            started_at = now
        finished_at = now if state in {
            ComputeJobState.SUCCEEDED,
            ComputeJobState.FAILED,
            ComputeJobState.CANCELLED,
        } else None
        next_progress = current.progress if progress is None else progress
        if next_progress < current.progress:
            raise DurableJobControlError(
                "B3_JOB_PROGRESS_REGRESSION",
                f"{current.progress}->{next_progress}",
            )
        return self._repository.cas_update(
            job_id=job_id,
            expected_state=current.status,
            state=state,
            progress=next_progress,
            reason_codes=reason_codes,
            error_detail=error_detail,
            started_at=started_at,
            finished_at=finished_at,
        )
