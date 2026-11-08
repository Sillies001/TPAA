"""Generated from CROSS_LAYER_DTO_CONTRACTS; do not edit manually."""

from typing import TypedDict


class WeaponEventDetailDTO(TypedDict):
    schema: str
    provenance: dict[str, object]
    weapon_event_id: str
    batch_id: str
    release_id: str | None
    category: str
    category_rule_version: str
    classification_exception: bool
    shooter_entity_id: str
    target_entity_id: str | None
    episode_id: str | None
    t1_session_time_us: str
    weapon_terminal_state: str
    adjudication_state: str
    observation_window_state: str
    cluster_id: str | None

class WeaponEventWindowDTO(TypedDict):
    schema: str
    provenance: dict[str, object]
    weapon_event_id: str
    perspective: str
    resolver_version: str
    start_session_time_us: str
    end_session_time_us: str | None
    t0s_session_time_us: str | None
    t0t_session_time_us: str | None
    t1_session_time_us: str
    t2_session_time_us: str | None
    t3_session_time_us: str | None
    cue_session_time_us: str | None
    response_session_time_us: str | None
    j_session_time_us: str | None
    terminal_state: str
    adjudication_state: str
    window_state: str
    alignment_state: str
    coverage: str
    reason: str | None

class WeaponEventPerspectiveDTO(TypedDict):
    schema: str
    provenance: dict[str, object]
    weapon_event_id: str
    perspective: str
    projection_version: str
    allowed: bool
    denial_reason: str | None
    geometry_available: bool
    series_available: bool
