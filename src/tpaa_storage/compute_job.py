"""PIQB B3 durable compute-job row adapter over DB 1.9 registry.compute_job."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from .canonical_rows import CanonicalRowRepository, CanonicalRowRepositoryError


class ComputeJobState(StrEnum):
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ACTIVE_COMPUTE_JOB_STATES = frozenset(
    {ComputeJobState.SUBMITTED, ComputeJobState.QUEUED, ComputeJobState.RUNNING}
)
TERMINAL_COMPUTE_JOB_STATES = frozenset(
    {ComputeJobState.SUCCEEDED, ComputeJobState.FAILED, ComputeJobState.CANCELLED}
)


class ComputeJobPersistenceError(RuntimeError):
    """Fail-closed compute-job persistence error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class ComputeJobRecord:
    job_id: str
    job_type: str
    session_id: str | None
    episode_id: str | None
    job_key: str
    status: ComputeJobState
    component_version: str
    input_hash: str
    progress: float
    reason_codes: tuple[str, ...]
    error_detail: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


_COLUMNS = (
    "job_id",
    "job_type",
    "session_id",
    "episode_id",
    "job_key",
    "status",
    "component_version",
    "input_hash",
    "progress",
    "reason_codes",
    "error_detail",
    "created_at",
    "started_at",
    "finished_at",
)


def _time_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value:
        return value
    raise ComputeJobPersistenceError("B3_COMPUTE_JOB_TIME_INVALID", field)


def _text_array(value: object) -> tuple[str, ...]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ComputeJobPersistenceError(
                "B3_COMPUTE_JOB_REASON_CODES_INVALID",
                value,
            ) from exc
    if not isinstance(parsed, (tuple, list)):
        raise ComputeJobPersistenceError(
            "B3_COMPUTE_JOB_REASON_CODES_INVALID",
            type(parsed).__name__,
        )
    result = tuple(str(item) for item in parsed)
    if any(not item for item in result):
        raise ComputeJobPersistenceError(
            "B3_COMPUTE_JOB_REASON_CODES_INVALID",
            "empty",
        )
    return result


def _progress(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComputeJobPersistenceError(
            "B3_COMPUTE_JOB_PROGRESS_INVALID",
            str(value),
        )
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ComputeJobPersistenceError(
            "B3_COMPUTE_JOB_PROGRESS_INVALID",
            str(value),
        )
    return result


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ComputeJobPersistenceError("B3_COMPUTE_JOB_ROW_INVALID", field)
    return value


def _id_text(
    value: object,
    *,
    field: str,
    optional: bool = False,
) -> str | None:
    if value is None and optional:
        return None
    if isinstance(value, (str, UUID)):
        normalized = str(value)
        if normalized:
            return normalized
    raise ComputeJobPersistenceError("B3_COMPUTE_JOB_ROW_INVALID", field)


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field=field)


def _record(row: dict[str, object]) -> ComputeJobRecord:
    try:
        state = ComputeJobState(_required_text(row.get("status"), field="status"))
    except ValueError as exc:
        raise ComputeJobPersistenceError(
            "B3_COMPUTE_JOB_STATE_INVALID",
            str(row.get("status")),
        ) from exc
    created_at = _time_text(row.get("created_at"), field="created_at")
    job_id = _id_text(row.get("job_id"), field="job_id")
    if created_at is None or job_id is None:
        raise ComputeJobPersistenceError(
            "B3_COMPUTE_JOB_ROW_INVALID",
            "identity_or_created_at",
        )
    return ComputeJobRecord(
        job_id=job_id,
        job_type=_required_text(row.get("job_type"), field="job_type"),
        session_id=_id_text(
            row.get("session_id"),
            field="session_id",
            optional=True,
        ),
        episode_id=_id_text(
            row.get("episode_id"),
            field="episode_id",
            optional=True,
        ),
        job_key=_required_text(row.get("job_key"), field="job_key"),
        status=state,
        component_version=_required_text(
            row.get("component_version"),
            field="component_version",
        ),
        input_hash=_required_text(row.get("input_hash"), field="input_hash"),
        progress=_progress(row.get("progress")),
        reason_codes=_text_array(row.get("reason_codes")),
        error_detail=_optional_text(row.get("error_detail"), field="error_detail"),
        created_at=created_at,
        started_at=_time_text(row.get("started_at"), field="started_at"),
        finished_at=_time_text(row.get("finished_at"), field="finished_at"),
    )


class ComputeJobRepository:
    """Transaction-scoped exact adapter for the existing DB 1.9 job authority."""

    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows

    def exact(self, job_id: str) -> ComputeJobRecord:
        row = self._rows.one(
            "registry.compute_job",
            where={"job_id": job_id},
            columns=_COLUMNS,
        )
        if row is None:
            raise ComputeJobPersistenceError(
                "B3_COMPUTE_JOB_NOT_FOUND",
                job_id,
            )
        return _record(row)

    def by_job_key(self, job_key: str) -> ComputeJobRecord | None:
        rows = self._rows.many(
            "registry.compute_job",
            where={"job_key": job_key},
            columns=_COLUMNS,
            order_by=("job_id",),
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise ComputeJobPersistenceError(
                "B3_COMPUTE_JOB_KEY_CARDINALITY",
                f"{job_key}:{len(rows)}",
            )
        return _record(rows[0])

    def insert_exact(self, record: ComputeJobRecord) -> bool:
        if not record.job_id or not record.job_key or not record.job_type:
            raise ComputeJobPersistenceError(
                "B3_COMPUTE_JOB_IDENTITY_INVALID",
                record.job_id,
            )
        _progress(record.progress)

        existing_id: ComputeJobRecord | None
        try:
            existing_id = self.exact(record.job_id)
        except ComputeJobPersistenceError as exc:
            if exc.code != "B3_COMPUTE_JOB_NOT_FOUND":
                raise
            existing_id = None
        existing_key = self.by_job_key(record.job_key)

        for existing in (existing_id, existing_key):
            if existing is None:
                continue
            if existing == record:
                return True
            raise ComputeJobPersistenceError(
                "B3_COMPUTE_JOB_IMMUTABLE_CONFLICT",
                record.job_key,
            )

        self._rows.insert(
            "registry.compute_job",
            {
                "job_id": record.job_id,
                "job_type": record.job_type,
                "session_id": record.session_id,
                "episode_id": record.episode_id,
                "job_key": record.job_key,
                "status": record.status.value,
                "component_version": record.component_version,
                "input_hash": record.input_hash,
                "progress": record.progress,
                "reason_codes": record.reason_codes,
                "error_detail": record.error_detail,
                "created_at": record.created_at,
                "started_at": record.started_at,
                "finished_at": record.finished_at,
            },
            field_kinds={"reason_codes": "text_array"},
        )
        return False

    def cas_update(
        self,
        *,
        job_id: str,
        expected_state: ComputeJobState,
        state: ComputeJobState,
        progress: float,
        reason_codes: tuple[str, ...],
        error_detail: str | None,
        started_at: str | None,
        finished_at: str | None,
    ) -> ComputeJobRecord:
        _progress(progress)
        try:
            self._rows.update_exact(
                "registry.compute_job",
                where={"job_id": job_id, "status": expected_state.value},
                values={
                    "status": state.value,
                    "progress": progress,
                    "reason_codes": reason_codes,
                    "error_detail": error_detail,
                    "started_at": started_at,
                    "finished_at": finished_at,
                },
                field_kinds={"reason_codes": "text_array"},
            )
        except CanonicalRowRepositoryError as exc:
            if exc.code == "CANONICAL_UPDATE_CARDINALITY":
                raise ComputeJobPersistenceError(
                    "B3_COMPUTE_JOB_CAS_CONFLICT",
                    f"{job_id}:{expected_state.value}",
                ) from exc
            raise
        return self.exact(job_id)

    def all(self) -> tuple[ComputeJobRecord, ...]:
        return tuple(
            _record(row)
            for row in self._rows.many(
                "registry.compute_job",
                where={},
                columns=_COLUMNS,
                order_by=("created_at", "job_id"),
            )
        )

    def active_job_ids(self) -> tuple[str, ...]:
        return tuple(
            item.job_id
            for item in self.all()
            if item.status in ACTIVE_COMPUTE_JOB_STATES
        )
