"""Application Service facade exposed to GUI and REST transports."""

from __future__ import annotations

from typing import Protocol

from .job_control import JobRecord, JobSubmission, M0JobControl
from .m1_publication import (
    M1PublicationService,
    M1PublishSessionCommand,
    M1PublishSessionResult,
)
from .models import StorageBaselineStatus
from .runtime import GetRuntimeBaselineStatus, RuntimeBaselineStatus


class StorageBaselineStatusUseCase(Protocol):
    """Structural Application dependency for persisted baseline status."""

    def execute(self) -> StorageBaselineStatus:
        """Return engine-neutral persisted baseline metadata."""
        ...


class ApplicationService:
    """Typed facade that is the transport-facing business-entry boundary."""

    def __init__(
        self,
        *,
        get_storage_baseline_status: StorageBaselineStatusUseCase,
        get_runtime_baseline_status: GetRuntimeBaselineStatus | None = None,
        job_control: M0JobControl | None = None,
        m1_publication: M1PublicationService | None = None,
    ) -> None:
        self._get_storage_baseline_status = get_storage_baseline_status
        self._get_runtime_baseline_status = get_runtime_baseline_status
        self._job_control = job_control or M0JobControl()
        self._m1_publication = m1_publication

    def storage_baseline_status(self) -> StorageBaselineStatus:
        """Return persisted storage baseline provenance via an Application use case."""

        return self._get_storage_baseline_status.execute()

    def runtime_baseline_status(self) -> RuntimeBaselineStatus:
        """Return the Core-authoritative runtime handshake projection.

        M0-API-002 requires this use case to be wired before exposing readiness/version.
        """

        if self._get_runtime_baseline_status is None:
            raise RuntimeError("runtime baseline status use case is not configured")
        return self._get_runtime_baseline_status.execute()


    def submit_job(
        self,
        *,
        idempotency_key: str,
        command: str,
        payload: dict[str, object],
        actor: str,
    ) -> JobSubmission:
        """Submit an M0 control-plane job skeleton with canonical request identity."""

        return self._job_control.submit(
            idempotency_key=idempotency_key,
            command=command,
            payload=payload,
            actor=actor,
        )

    def job(self, job_id: str) -> JobRecord:
        """Return an M0 job record without transport-specific behavior."""

        return self._job_control.get(job_id)

    def cancel_job(self, *, job_id: str, actor: str, reason: str) -> JobRecord:
        """Cancel an M0 job skeleton; this does not implement M1 compute cancellation."""

        return self._job_control.cancel(job_id=job_id, actor=actor, reason=reason)


    def _m1(self) -> M1PublicationService:
        if self._m1_publication is None:
            raise RuntimeError("M1 publication service is not configured")
        return self._m1_publication

    def import_m1_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        """Validate one governed source fixture through the M1 import command."""

        return self._m1().import_session(
            fixture_id=fixture_id,
            idempotency_key=idempotency_key,
        )

    def compute_m1_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        """Compute one staged M1 World/Metric product without publication."""

        return self._m1().compute_session(
            fixture_id=fixture_id,
            idempotency_key=idempotency_key,
        )

    def publish_m1_session(
        self,
        command: M1PublishSessionCommand,
        *,
        idempotency_key: str,
    ) -> M1PublishSessionResult:
        """Publish one exact SESSION Release through the M1 Application service."""

        return self._m1().publish_session(command, idempotency_key=idempotency_key)

    def m1_release(self, release_id: str) -> dict[str, object]:
        return self._m1().release_summary(release_id)

    def m1_observations(self, release_id: str) -> list[dict[str, object]]:
        return [dict(item) for item in self._m1().observations(release_id)]

    def m1_metrics(self, release_id: str) -> list[dict[str, object]]:
        return self._m1().metric_list(release_id)

    def m1_metric(self, release_id: str, metric_code: str) -> dict[str, object]:
        return self._m1().metric_detail(release_id, metric_code)

    def m1_metric_evidence(self, release_id: str, metric_code: str) -> dict[str, object]:
        return self._m1().metric_evidence(release_id, metric_code)

    def m1_context(self, release_id: str) -> dict[str, object]:
        return dict(self._m1().context_projection(release_id))

    def m1_session_episode_stages(self, release_id: str) -> dict[str, object]:
        return dict(self._m1().session_episode_stage_projection(release_id))

    def replay_m1_release(self, release_id: str) -> dict[str, object]:
        return self._m1().replay(release_id)

    def m1_series_range(
        self,
        release_id: str,
        *,
        start_session_time_us: int,
        end_session_time_us: int,
        limit: int,
    ) -> dict[str, object]:
        return self._m1().series_range(
            release_id,
            start_session_time_us=start_session_time_us,
            end_session_time_us=end_session_time_us,
            limit=limit,
        )
