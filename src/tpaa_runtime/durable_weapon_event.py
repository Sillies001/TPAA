"""Durable read adapter for G5 Weapon Event projections.

G5 introduces no schema migration.  Weapon Events and their relations are read
from the admitted ``world.world_relation`` subtype rows.  Missing rows mean an
honest EMPTY/404 state; malformed admitted rows fail closed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from tpaa_application.event_window import WindowAnchorInput
from tpaa_application.weapon_event import (
    AdjudicationState,
    ObservationWindowState,
    WeaponCategory,
    WeaponEvent,
    WeaponTerminalState,
)
from tpaa_application.weapon_event_application import (
    WeaponEventReadAdapter,
    WeaponEventSnapshot,
)

from .durable_repositories import RuntimeUnitOfWorkFactory


class DurableWeaponEventError(RuntimeError):
    """Canonical WE projection is malformed or cannot be read safely."""


def _properties(value: object) -> Mapping[str, object]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise DurableWeaponEventError("WEAPON_EVENT_PROPERTIES_INVALID") from exc
    if not isinstance(value, Mapping):
        raise DurableWeaponEventError("WEAPON_EVENT_PROPERTIES_INVALID")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise DurableWeaponEventError("WEAPON_EVENT_ANCHOR_INVALID")
    try:
        return int(str(value))
    except ValueError as exc:
        raise DurableWeaponEventError("WEAPON_EVENT_ANCHOR_INVALID") from exc


class DurableWeaponEventReadAdapter(WeaponEventReadAdapter):
    """Read exact G5 projections without cross-batch or latest substitution."""

    _EVENT_COLUMNS = (
        "relation_id",
        "release_id",
        "episode_id",
        "stage_id",
        "subject_ref",
        "object_ref",
        "start_session_time_us",
        "properties",
    )

    def __init__(self, read_uow_factory: RuntimeUnitOfWorkFactory) -> None:
        self._read_uow_factory = read_uow_factory

    def _rows(self) -> Sequence[Mapping[str, object]]:
        with self._read_uow_factory() as uow:
            return uow.canonical_rows.many(
                "world.world_relation",
                where={"relation_type": "WEAPON_EVENT"},
                columns=self._EVENT_COLUMNS,
                order_by=("relation_id",),
            )

    @staticmethod
    def _snapshot(row: Mapping[str, object]) -> WeaponEventSnapshot:
        props = _properties(row.get("properties"))
        try:
            event = WeaponEvent(
                weapon_event_id=str(row["relation_id"]),
                batch_id=str(props["batch_id"]),
                release_id=None if row.get("release_id") is None else str(row["release_id"]),
                episode_id=None if row.get("episode_id") is None else str(row["episode_id"]),
                stage_id=None if row.get("stage_id") is None else str(row["stage_id"]),
                category=WeaponCategory(str(props["category"])),
                category_rule_version=str(props["category_rule_version"]),
                classification_exception=bool(props["classification_exception"]),
                shooter_entity_id=str(row["subject_ref"]),
                target_entity_id=(
                    None
                    if props.get("target_entity_id") is None
                    else str(props["target_entity_id"])
                ),
                t1_session_time_us=int(str(row["start_session_time_us"])),
                weapon_terminal_state=WeaponTerminalState(str(props["weapon_terminal_state"])),
                adjudication_state=AdjudicationState(str(props["adjudication_state"])),
                observation_window_state=ObservationWindowState(
                    str(props["observation_window_state"])
                ),
                cluster_id=None,
                identity_material=str(props["identity_material"]),
            )
            anchors = WindowAnchorInput(
                t0s_session_time_us=_optional_int(props.get("t0s_session_time_us")),
                t0t_session_time_us=_optional_int(props.get("t0t_session_time_us")),
                t1_session_time_us=event.t1_session_time_us,
                t2_session_time_us=_optional_int(props.get("t2_session_time_us")),
                t3_session_time_us=_optional_int(props.get("t3_session_time_us")),
                cue_session_time_us=_optional_int(props.get("cue_session_time_us")),
                response_session_time_us=_optional_int(props.get("response_session_time_us")),
                j_session_time_us=_optional_int(props.get("j_session_time_us")),
                alignment_unresolved=bool(props.get("alignment_unresolved", False)),
                clock_gap_after_t1=bool(props.get("clock_gap_after_t1", False)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DurableWeaponEventError("WEAPON_EVENT_CANONICAL_ROW_INVALID") from exc
        return WeaponEventSnapshot(
            event=event,
            anchors=anchors,
            geometry_available=bool(props.get("geometry_available", False)),
            series_available=bool(props.get("series_available", False)),
            target_projection_available=bool(props.get("target_projection_available", False)),
            context_id=None if props.get("context_id") is None else str(props["context_id"]),
        )

    def get(self, weapon_event_id: str) -> WeaponEventSnapshot | None:
        matches = [row for row in self._rows() if str(row["relation_id"]) == weapon_event_id]
        if len(matches) > 1:
            raise DurableWeaponEventError("WEAPON_EVENT_ID_NOT_UNIQUE")
        return None if not matches else self._snapshot(matches[0])

    def list_ids(self, batch_id: str) -> Sequence[str]:
        result: list[str] = []
        for row in self._rows():
            if str(_properties(row.get("properties")).get("batch_id")) == batch_id:
                result.append(str(row["relation_id"]))
        return tuple(result)

    def cluster_id(self, batch_id: str, weapon_event_id: str) -> str | None:
        with self._read_uow_factory() as uow:
            rows = uow.canonical_rows.many(
                "world.world_relation",
                where={"relation_type": "ATTACK_CLUSTER"},
                columns=("relation_id", "properties"),
                order_by=("relation_id",),
            )
        matches = []
        for row in rows:
            props = _properties(row.get("properties"))
            ids = props.get("weapon_event_ids")
            if (
                str(props.get("batch_id")) == batch_id
                and isinstance(ids, list)
                and weapon_event_id in {str(value) for value in ids}
            ):
                matches.append(str(row["relation_id"]))
        if len(matches) > 1:
            raise DurableWeaponEventError("WEAPON_EVENT_CLUSTER_NOT_UNIQUE")
        return None if not matches else matches[0]


__all__ = ["DurableWeaponEventError", "DurableWeaponEventReadAdapter"]
