"""Application Service facade exposed to GUI and REST transports."""

from __future__ import annotations

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
    ) -> None:
        self._get_storage_baseline_status = get_storage_baseline_status
        self._get_runtime_baseline_status = get_runtime_baseline_status

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
