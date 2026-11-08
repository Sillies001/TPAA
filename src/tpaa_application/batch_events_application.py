"""G7 Batch Events Application read model (single transport-facing owner)."""

from __future__ import annotations

from collections.abc import Mapping

from .batch_events import BatchEventsError, BatchEventSource, BatchEventsQuery


class BatchEventsApplicationService:
    def __init__(
        self,
        adapter: BatchEventSource,
        *,
        capability_enabled: bool = True,
        adapter_ready: bool = True,
    ) -> None:
        self._query = BatchEventsQuery(adapter)
        self._capability_enabled = capability_enabled
        self._adapter_ready = adapter_ready

    def capability_state(self) -> str:
        if not self._capability_enabled:
            return "CAPABILITY_DISABLED"
        if not self._adapter_ready:
            return "ADAPTER_UNAVAILABLE"
        return "READY"

    def _require_ready(self) -> None:
        if not self._capability_enabled:
            raise BatchEventsError(
                "CAPABILITY_DISABLED",
                "batch-events capability is not active for this backend",
                http_status=403,
            )
        if not self._adapter_ready:
            raise BatchEventsError(
                "ADAPTER_UNAVAILABLE",
                "batch-events backend adapter is not configured",
                http_status=503,
            )

    def workbench(
        self,
        batch_id: str,
        raw_filter: Mapping[str, object],
        *,
        cursor: str | None,
        limit: int,
        request_id: str,
    ) -> dict[str, object]:
        self._require_ready()
        return self._query.workbench(
            batch_id,
            raw_filter,
            cursor=cursor,
            limit=limit,
            request_id=request_id,
        )
