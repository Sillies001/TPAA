"""G7 durable BatchEventSource adapter: exact Batch WE/cluster read model.

Reads registered batches and derives the V26 workset from canonical WEAPON_EVENT /
ATTACK_CLUSTER relations, mirroring the G5 durable WE projection (jsonb TEXT decoded).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from tpaa_application.batch_events import BatchEventRecord, BatchEventsError, BatchEventSource

from .durable_repositories import RuntimeUnitOfWorkFactory

_BATCH_COLUMNS = ("batch_id", "context_id")
_EVENT_COLUMNS = (
    "relation_id",
    "release_id",
    "episode_id",
    "subject_ref",
    "start_session_time_us",
    "properties",
)
_CLUSTER_COLUMNS = ("relation_id", "properties")


def _properties(value: object) -> Mapping[str, object]:
    # Corrupt Canonical data is DEGRADED/ERROR, never an empty result.  Silently
    # returning {} would hide affected events and undercount an exact Batch.
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise BatchEventsError(
                "CANONICAL_RELATION_PROPERTIES_INVALID",
                "world_relation.properties is not valid JSON",
                http_status=503,
            ) from exc
    if not isinstance(value, Mapping):
        raise BatchEventsError(
            "CANONICAL_RELATION_PROPERTIES_INVALID",
            "world_relation.properties is not an object",
            http_status=503,
        )
    return value


class DurableBatchEventSource(BatchEventSource):
    """Read the exact V26 workset without cross-batch or latest substitution."""

    def __init__(self, read_uow_factory: RuntimeUnitOfWorkFactory) -> None:
        self._read = read_uow_factory

    def batch_ids(self) -> Sequence[str]:
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "registry.batch_registration",
                where={},
                columns=_BATCH_COLUMNS,
                order_by=("batch_id",),
            )
        return tuple(str(row["batch_id"]) for row in rows)

    def _cluster_map(self, batch_id: str) -> Mapping[str, str]:
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "world.world_relation",
                where={"relation_type": "ATTACK_CLUSTER"},
                columns=_CLUSTER_COLUMNS,
                order_by=("relation_id",),
            )
        mapping: dict[str, str] = {}
        for row in rows:
            props = _properties(row.get("properties"))
            if str(props.get("batch_id")) != batch_id:
                continue
            ids = props.get("weapon_event_ids")
            if not isinstance(ids, list):
                continue
            for weapon_event_id in ids:
                mapping[str(weapon_event_id)] = str(row["relation_id"])
        return mapping

    def batch_context(self, batch_id: str) -> str | None:
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "registry.batch_registration",
                where={"batch_id": batch_id},
                columns=_BATCH_COLUMNS,
                order_by=("batch_id",),
            )
        if not rows:
            return None
        context_id = rows[0].get("context_id")
        return None if context_id is None else str(context_id)

    def events(self, batch_id: str) -> Sequence[BatchEventRecord]:
        clusters = self._cluster_map(batch_id)
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "world.world_relation",
                where={"relation_type": "WEAPON_EVENT"},
                columns=_EVENT_COLUMNS,
                order_by=("relation_id",),
            )
        records: list[BatchEventRecord] = []
        for row in rows:
            props = _properties(row.get("properties"))
            if str(props.get("batch_id")) != batch_id:
                continue
            try:
                records.append(
                    BatchEventRecord(
                        weapon_event_id=str(row["relation_id"]),
                        revision_no=int(str(props.get("revision_no", 1))),
                        batch_id=batch_id,
                        t1_session_time_us=int(str(row["start_session_time_us"])),
                        category=str(props.get("category", "UNKNOWN")),
                        classification_exception=bool(props.get("classification_exception", False)),
                        shooter_entity_id=str(row["subject_ref"]),
                        target_entity_id=(
                            None
                            if props.get("target_entity_id") is None
                            else str(props["target_entity_id"])
                        ),
                        episode_id=(
                            None if row.get("episode_id") is None else str(row["episode_id"])
                        ),
                        weapon_terminal_state=str(
                            props.get("weapon_terminal_state", "TERMINAL_UNKNOWN")
                        ),
                        adjudication_state=str(
                            props.get("adjudication_state", "ADJUDICATION_PENDING")
                        ),
                        observation_window_state=str(
                            props.get("observation_window_state", "WINDOW_OPEN")
                        ),
                        cluster_id=clusters.get(str(row["relation_id"])),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise BatchEventsError(
                    "CANONICAL_WE_ROW_INVALID",
                    f"weapon event {row.get('relation_id')!r} is malformed",
                    http_status=503,
                ) from exc
        return tuple(records)

    def cluster_of(self, batch_id: str, weapon_event_id: str) -> str | None:
        return self._cluster_map(batch_id).get(weapon_event_id)
