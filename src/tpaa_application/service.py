"""Application Service facade exposed to GUI and REST transports."""

from __future__ import annotations

from .job_control import JobRecord, JobSubmission, M0JobControl
from .models import StorageBaselineStatus
from .runtime import GetRuntimeBaselineStatus, RuntimeBaselineStatus
from .use_cases import GetStorageBaselineStatus


class ApplicationService:
    """Typed facade that is the transport-facing business-entry boundary."""

    def __init__(
        self,
        *,
        get_storage_baseline_status: GetStorageBaselineStatus,
        get_runtime_baseline_status: GetRuntimeBaselineStatus | None = None,
        job_control: M0JobControl | None = None,
    ) -> None:
        self._get_storage_baseline_status = get_storage_baseline_status
        self._get_runtime_baseline_status = get_runtime_baseline_status
        self._job_control = job_control or M0JobControl()

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
