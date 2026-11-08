"""G6 durable BatchWorksetSource adapter: exact QUALIFIED-batch read model.

Reads QUALIFIED batch registrations and derives aggregate facts (sortie/episode/WE/
adjudicated counts) from canonical relations.  Task and equipment metric inputs are
returned empty until their Metric Authority admission (G6 defers admission; panels render
an honest unavailable state rather than fabricated trends).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date

from tpaa_application.historical_overview import (
    BatchOverviewRecord,
    BatchWorksetSource,
    EquipmentMetricInput,
    HistoricalOverviewError,
    TaskMetricInput,
)

from .durable_repositories import RuntimeUnitOfWorkFactory

_BATCH_COLUMNS = (
    "batch_id",
    "batch_date",
    "batch_training_type",
    "qualification_status",
)

_WE_COLUMNS = ("relation_id", "properties")


def _properties(value: object) -> Mapping[str, object]:
    # SQLite stores jsonb as TEXT.  Corruption is a degraded source, not an EMPTY
    # workset: surface it so the transport can present an explicit error state.
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise HistoricalOverviewError(
                "CANONICAL_WE_PROPERTIES_INVALID",
                "world_relation.properties is not valid JSON",
                http_status=503,
            ) from exc
    if not isinstance(value, Mapping):
        raise HistoricalOverviewError(
            "CANONICAL_WE_PROPERTIES_INVALID",
            "world_relation.properties is not an object",
            http_status=503,
        )
    return value


class DurableHistoricalOverviewAdapter(BatchWorksetSource):
    """Read the exact V01 workset without cross-batch or latest substitution."""

    def __init__(self, read_uow_factory: RuntimeUnitOfWorkFactory) -> None:
        self._read = read_uow_factory

    def _we_counts(self) -> Mapping[str, tuple[int, int]]:
        """Map batch_id -> (weapon_event_count, adjudicated_event_count)."""

        counts: dict[str, list[int]] = {}
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "world.world_relation",
                where={"relation_type": "WEAPON_EVENT"},
                columns=_WE_COLUMNS,
                order_by=("relation_id",),
            )
        for row in rows:
            props = _properties(row.get("properties"))
            batch_id = props.get("batch_id")
            if not isinstance(batch_id, str) or not batch_id:
                continue
            entry = counts.setdefault(batch_id, [0, 0])
            entry[0] += 1
            if str(props.get("adjudication_state", "")) == "ADJUDICATED":
                entry[1] += 1
        return {key: (value[0], value[1]) for key, value in counts.items()}

    def qualified_batches(self) -> Sequence[BatchOverviewRecord]:
        we_counts = self._we_counts()
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "registry.batch_registration",
                where={"qualification_status": "QUALIFIED"},
                columns=_BATCH_COLUMNS,
                order_by=("batch_date", "batch_id"),
            )
        records: list[BatchOverviewRecord] = []
        for row in rows:
            batch_id = str(row["batch_id"])
            weapon_events, adjudicated = we_counts.get(batch_id, (0, 0))
            try:
                batch_date = date.fromisoformat(str(row["batch_date"]))
            except ValueError:
                continue  # skip malformed rows rather than fabricate a date
            records.append(
                BatchOverviewRecord(
                    batch_id=batch_id,
                    batch_date=batch_date,
                    batch_training_type=str(row["batch_training_type"]),
                    # Sortie/episode per-batch detail is owned by later phases; V01 only
                    # needs exact WE-derived counts here, so these stay zero until populated.
                    sortie_count=0,
                    episode_count=0,
                    weapon_event_count=weapon_events,
                    adjudicated_event_count=adjudicated,
                    qualification_status=str(row["qualification_status"]),
                    has_event_detail=weapon_events > 0,
                )
            )
        return tuple(records)

    def task_metric_inputs(self, batch_ids: Sequence[str]) -> Sequence[TaskMetricInput]:
        # Task-level metric definitions are not yet admitted by Metric Authority; return
        # none so the panel renders an honest unavailable state (no fabricated ratios).
        _ = batch_ids
        return ()

    def equipment_metric_inputs(self, batch_ids: Sequence[str]) -> Sequence[EquipmentMetricInput]:
        # No comparable equipment-metric authority is admitted yet; honest empty.
        _ = batch_ids
        return ()
