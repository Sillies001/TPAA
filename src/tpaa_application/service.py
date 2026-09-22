"""Application Service facade exposed to GUI and REST transports."""

from __future__ import annotations

from .models import StorageBaselineStatus
from .use_cases import GetStorageBaselineStatus


class ApplicationService:
    """Typed facade that is the transport-facing business-entry boundary."""

    def __init__(self, *, get_storage_baseline_status: GetStorageBaselineStatus) -> None:
        self._get_storage_baseline_status = get_storage_baseline_status

    def storage_baseline_status(self) -> StorageBaselineStatus:
        """Return persisted storage baseline provenance via an Application use case."""

        return self._get_storage_baseline_status.execute()
