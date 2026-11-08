"""G6 Historical Overview Application read model (single transport-facing owner).

Wraps the HistoricalTrainingOverviewQuery with capability/adapter state so the API and
GUI can distinguish CAPABILITY_DISABLED / ADAPTER_UNAVAILABLE / EMPTY / READY and never
conflate an unconfigured backend with "no batches".  Fails closed; no synthetic data.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .historical_overview import (
    BatchWorksetSource,
    HistoricalOverviewError,
    HistoricalTrainingOverviewQuery,
    OverviewQuery,
)


class HistoricalOverviewApplicationService:
    def __init__(
        self,
        adapter: BatchWorksetSource,
        *,
        capability_enabled: bool = True,
        adapter_ready: bool = True,
    ) -> None:
        self._query = HistoricalTrainingOverviewQuery(adapter)
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
            raise HistoricalOverviewError(
                "CAPABILITY_DISABLED",
                "historical-overview capability is not active for this backend",
                http_status=403,
            )
        if not self._adapter_ready:
            raise HistoricalOverviewError(
                "ADAPTER_UNAVAILABLE",
                "historical-overview backend adapter is not configured",
                http_status=503,
            )

    def overview(self, raw_query: Mapping[str, object]) -> dict[str, object]:
        self._require_ready()
        try:
            query = OverviewQuery(
                start_date=date.fromisoformat(str(raw_query.get("start_date", "1970-01-01"))),
                end_date=date.fromisoformat(str(raw_query.get("end_date", "2999-12-31"))),
                model=str(raw_query.get("model", "ALL")),
                training_type=str(raw_query.get("training_type", "ALL")),
            )
        except ValueError as exc:
            raise HistoricalOverviewError(
                "OVERVIEW_QUERY_INVALID", f"invalid overview query: {exc}", http_status=422
            ) from exc
        return self._query.overview(query)
