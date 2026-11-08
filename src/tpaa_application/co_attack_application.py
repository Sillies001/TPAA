"""G8 Co-attack Analysis Application read model (single transport-facing owner)."""

from __future__ import annotations

from collections.abc import Mapping

from .co_attack import CoAttackAnalysisQuery, CoAttackError, CoAttackEventSource


class CoAttackApplicationService:
    def __init__(
        self,
        adapter: CoAttackEventSource,
        *,
        capability_enabled: bool = True,
        adapter_ready: bool = True,
    ) -> None:
        self._query = CoAttackAnalysisQuery(adapter)
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
            raise CoAttackError(
                "CAPABILITY_DISABLED",
                "co-attack capability is not active for this backend",
                http_status=403,
            )
        if not self._adapter_ready:
            raise CoAttackError(
                "ADAPTER_UNAVAILABLE",
                "co-attack backend adapter is not configured",
                http_status=503,
            )

    def analysis(self, cluster_id: str, raw_query: Mapping[str, object], *, request_id: str) -> dict[str, object]:
        self._require_ready()
        return self._query.analysis(cluster_id, raw_query, request_id=request_id)
