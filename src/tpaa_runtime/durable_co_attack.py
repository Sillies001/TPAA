"""G8 durable CoAttackEventSource adapter: exact cluster/WE/context facts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from tpaa_application.co_attack import CoAttackError, CoAttackEventSource

from .durable_repositories import RuntimeUnitOfWorkFactory


def _props(value: object) -> Mapping[str, object]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CoAttackError(
                "CANONICAL_RELATION_PROPERTIES_INVALID",
                "world_relation.properties is not valid JSON",
                http_status=503,
            ) from exc
    if not isinstance(value, Mapping):
        raise CoAttackError(
            "CANONICAL_RELATION_PROPERTIES_INVALID",
            "world_relation.properties is not an object",
            http_status=503,
        )
    return value


class DurableCoAttackSource(CoAttackEventSource):
    """Read the exact V24 facts without cross-batch or latest substitution."""

    def __init__(self, read_uow_factory: RuntimeUnitOfWorkFactory) -> None:
        self._read = read_uow_factory

    def cluster(self, cluster_id: str) -> Mapping[str, object] | None:
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "world.world_relation",
                where={"relation_type": "ATTACK_CLUSTER"},
                columns=("relation_id", "properties"),
                order_by=("relation_id",),
            )
        for row in rows:
            if str(row["relation_id"]) != cluster_id:
                continue
            props = _props(row.get("properties"))
            ids = props.get("weapon_event_ids")
            return {
                "cluster_id": cluster_id,
                "batch_id": props.get("batch_id"),
                "weapon_event_ids": ids if isinstance(ids, list) else [],
            }
        return None

    def events(self, batch_id: str, weapon_event_ids: Sequence[str]) -> Sequence[Mapping[str, object]]:
        wanted = {str(value) for value in weapon_event_ids}
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "world.world_relation",
                where={"relation_type": "WEAPON_EVENT"},
                columns=("relation_id", "subject_ref", "start_session_time_us", "properties"),
                order_by=("relation_id",),
            )
        result: list[Mapping[str, object]] = []
        for row in rows:
            relation_id = str(row["relation_id"])
            if relation_id not in wanted:
                continue
            props = _props(row.get("properties"))
            result.append(
                {
                    "weapon_event_id": relation_id,
                    "batch_id": str(props.get("batch_id", "")),
                    "category": str(props.get("category", "UNKNOWN")),
                    "t1_session_time_us": str(row.get("start_session_time_us", "0")),
                    "shooter_entity_id": str(row.get("subject_ref", "")),
                    "target_entity_id": props.get("target_entity_id"),
                    "weapon_terminal_state": str(props.get("weapon_terminal_state", "TERMINAL_UNKNOWN")),
                    "adjudication_state": str(props.get("adjudication_state", "ADJUDICATION_PENDING")),
                    "observation_window_state": str(props.get("observation_window_state", "WINDOW_OPEN")),
                }
            )
        return tuple(result)

    def formation(self, context_id: str) -> Mapping[str, object] | None:
        with self._read() as uow:
            revisions = uow.canonical_rows.many(
                "context.force_formation_context_revision",
                where={"context_id": context_id},
                columns=("context_revision_id", "revision_no", "valid_from_session_time_us", "valid_to_session_time_us"),
                order_by=("revision_no",),
            )
            if not revisions:
                return None
            row = revisions[-1]
            members = uow.canonical_rows.many(
                "context.force_formation_member",
                where={"context_revision_id": str(row["context_revision_id"])},
                columns=("aircraft_id", "formation_id", "side", "member_role", "independent_target"),
                order_by=("aircraft_id",),
            )
        return {
            "context_id": context_id,
            "revision_no": int(str(row["revision_no"])),
            "valid_from_session_time_us": str(row["valid_from_session_time_us"]),
            "valid_to_session_time_us": (
                None if row.get("valid_to_session_time_us") is None else str(row["valid_to_session_time_us"])
            ),
            "members": [
                {
                    "aircraft_id": str(member["aircraft_id"]),
                    "formation_id": member.get("formation_id"),
                    "side": str(member["side"]),
                    "member_role": str(member["member_role"]),
                    "independent_target": bool(member["independent_target"]),
                }
                for member in members
            ],
        }
