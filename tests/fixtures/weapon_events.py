"""G5 Weapon Event/Window/Perspective Golden fixtures and in-memory adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from tpaa_application.event_window import WindowAnchorInput
from tpaa_application.weapon_event import (
    AttackCluster,
    WeaponEvent,
    WeaponEventStore,
    WeaponLaunchFact,
)


class InMemoryWeaponEventStore(WeaponEventStore):
    """Deterministic in-memory adapter for Golden fixtures and tests."""

    def __init__(self) -> None:
        self._events: dict[str, WeaponEvent] = {}
        self._clusters: dict[str, AttackCluster] = {}
        self._supersedes: dict[str, str] = {}  # superseding_id -> superseded_id
        self._superseded_by: dict[str, str] = {}  # superseded_id -> superseding_id

    def find_by_identity_material(self, batch_id: str, identity_material: str) -> WeaponEvent | None:
        for event in self._events.values():
            if event.batch_id == batch_id and event.identity_material == identity_material:
                return event
        return None

    def publish(self, event: WeaponEvent) -> None:
        self._events[event.weapon_event_id] = event

    def list_by_batch(self, batch_id: str) -> Sequence[WeaponEvent]:
        return [event for event in self._events.values() if event.batch_id == batch_id]

    def publish_cluster(self, cluster: AttackCluster) -> None:
        self._clusters[cluster.cluster_id] = cluster

    def list_clusters(self, batch_id: str) -> Sequence[AttackCluster]:
        return [cluster for cluster in self._clusters.values() if cluster.batch_id == batch_id]

    def publish_supersession(self, batch_id: str, superseding_id: str, superseded_id: str) -> None:
        if superseding_id not in self._events or superseded_id not in self._events:
            raise ValueError("supersession requires both weapon events to be published")
        self._supersedes[superseding_id] = superseded_id
        self._superseded_by[superseded_id] = superseding_id

    def supersession_of(self, weapon_event_id: str) -> str | None:
        return self._supersedes.get(weapon_event_id)

    def superseded_by_of(self, weapon_event_id: str) -> str | None:
        return self._superseded_by.get(weapon_event_id)

    def attach_cluster(self, weapon_event_id: str, cluster_id: str) -> None:
        self._events[weapon_event_id] = replace(self._events[weapon_event_id], cluster_id=cluster_id)


class StaticLaunchSource:
    """Fixed launch facts for one batch."""

    def __init__(self, facts: Sequence[WeaponLaunchFact]) -> None:
        self._facts = tuple(facts)

    def launch_facts(self, batch_id: str) -> Sequence[WeaponLaunchFact]:
        return tuple(fact for fact in self._facts if fact.batch_id == batch_id)


def launch_fact(
    source_launch_id: str,
    *,
    batch_id: str = "b-batch-0001",
    t1_us: int = 12_170_000,
    weapon_type_raw: str = "IR_MISSILE",
    shooter: str = "ac-blue-03",
    target: str | None = "ac-red-01",
    episode_id: str | None = "ep-0001",
    release_id: str | None = None,
    launch_range_m: int | None = 9_000,
    launch_aspect_deg: float | None = None,
    end_us: int = 90_000_000,
) -> WeaponLaunchFact:
    return WeaponLaunchFact(
        source_launch_id=source_launch_id,
        batch_id=batch_id,
        release_id=release_id,
        episode_id=episode_id,
        stage_id=None,
        shooter_entity_id=shooter,
        target_entity_id=target,
        t1_session_time_us=t1_us,
        weapon_type_raw=weapon_type_raw,
        launch_range_m=launch_range_m,
        launch_aspect_deg=launch_aspect_deg,
        session_time_end_us=end_us,
    )


def shooter_anchors(**overrides: object) -> WindowAnchorInput:
    base: dict[str, object] = {
        "t0s_session_time_us": 10_000_000,
        "t0t_session_time_us": None,
        "t1_session_time_us": 12_170_000,
        "t2_session_time_us": 20_000_000,
        "t3_session_time_us": 22_000_000,
        "cue_session_time_us": None,
        "response_session_time_us": None,
        "j_session_time_us": 30_000_000,
        "alignment_unresolved": False,
        "clock_gap_after_t1": False,
    }
    base.update(overrides)
    return WindowAnchorInput(**base)  # type: ignore[arg-type]
