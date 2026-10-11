"""Presentation-only ED-2 B3 linked debrief adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from uuid import UUID


class ED2LinkedDebriefError(RuntimeError):
    """Fail-closed linked debrief presentation error."""


@dataclass(frozen=True, slots=True)
class ED2LinkedDebriefProjection:
    snapshot_id: str
    release_id: str
    semantic_layers: tuple[str, ...]
    timeline: tuple[dict[str, object], ...]
    media: tuple[dict[str, object], ...]
    bookmarks: tuple[dict[str, object], ...]
    playlists: tuple[dict[str, object], ...]
    cesium_linked: bool
    view_2d: bool
    view_3d: bool


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ED2LinkedDebriefError(f"ED2_DEBRIEF_MAPPING_INVALID:{field}")
    return dict(cast(Mapping[str, object], value))


def _uuid(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ED2LinkedDebriefError(f"ED2_DEBRIEF_UUID_INVALID:{field}")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ED2LinkedDebriefError(
            f"ED2_DEBRIEF_UUID_INVALID:{field}"
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise ED2LinkedDebriefError(f"ED2_DEBRIEF_UUID_INVALID:{field}")
    return value


def _records(value: object, field: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise ED2LinkedDebriefError(f"ED2_DEBRIEF_SEQUENCE_INVALID:{field}")
    return tuple(
        _mapping(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def build_linked_debrief_projection(
    projection: Mapping[str, object],
    *,
    expected_snapshot_id: str,
) -> ED2LinkedDebriefProjection:
    """Validate one exact frozen upper-product DTO for presentation only."""

    if projection.get("schema") != "TPAA_ED2_UPPER_PRODUCT_PROJECTION_V1":
        raise ED2LinkedDebriefError("ED2_DEBRIEF_SCHEMA_INVALID")
    snapshot_id = _uuid(projection.get("snapshot_id"), "snapshot_id")
    if snapshot_id != expected_snapshot_id:
        raise ED2LinkedDebriefError("ED2_DEBRIEF_SNAPSHOT_ID_MISMATCH")
    if projection.get("kind") != "MEDIA_DEBRIEF":
        raise ED2LinkedDebriefError("ED2_DEBRIEF_KIND_INVALID")
    if projection.get("frozen") is not True:
        raise ED2LinkedDebriefError("ED2_DEBRIEF_FROZEN_REQUIRED")
    if projection.get("mutable_alias_resolution") is not False:
        raise ED2LinkedDebriefError("ED2_DEBRIEF_MUTABLE_ALIAS_FORBIDDEN")

    payload = _mapping(projection.get("payload"), "payload")
    release_id = _uuid(payload.get("release_id"), "release_id")
    source_release_ids = projection.get("source_release_ids")
    if (
        not isinstance(source_release_ids, list)
        or release_id not in source_release_ids
    ):
        raise ED2LinkedDebriefError("ED2_DEBRIEF_RELEASE_BINDING_INVALID")
    if payload.get("business_recompute") is not False:
        raise ED2LinkedDebriefError("ED2_DEBRIEF_RECOMPUTE_FORBIDDEN")
    if (
        payload.get("cesium_linked") is not True
        or payload.get("view_2d") is not True
        or payload.get("view_3d") is not True
    ):
        raise ED2LinkedDebriefError("ED2_DEBRIEF_VIEW_BINDING_INVALID")

    raw_layers = payload.get("semantic_layers")
    if not isinstance(raw_layers, list) or not all(
        isinstance(item, str) for item in raw_layers
    ):
        raise ED2LinkedDebriefError("ED2_DEBRIEF_LAYERS_INVALID")
    layers = tuple(cast(list[str], raw_layers))
    if not {"W", "P", "A", "J", "M"}.issubset(set(layers)):
        raise ED2LinkedDebriefError("ED2_DEBRIEF_LAYERS_INVALID")

    timeline = _records(payload.get("timeline"), "timeline")
    previous: int | None = None
    for index, item in enumerate(timeline):
        current = item.get("session_time_us")
        if isinstance(current, bool) or not isinstance(current, int):
            raise ED2LinkedDebriefError(
                f"ED2_DEBRIEF_TIME_INVALID:timeline[{index}]"
            )
        if previous is not None and current < previous:
            raise ED2LinkedDebriefError("ED2_DEBRIEF_TIME_ORDER_INVALID")
        previous = current

    return ED2LinkedDebriefProjection(
        snapshot_id=snapshot_id,
        release_id=release_id,
        semantic_layers=layers,
        timeline=timeline,
        media=_records(payload.get("media"), "media"),
        bookmarks=_records(payload.get("bookmarks"), "bookmarks"),
        playlists=_records(payload.get("playlists"), "playlists"),
        cesium_linked=True,
        view_2d=True,
        view_3d=True,
    )
