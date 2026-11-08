"""G5 Weapon Event Application read models (detail / window / perspective).

This facade is the single transport-facing owner wiring the G5 domain services
(weapon_event / event_window / perspective) to the API.  It never recomputes in the
transport layer and fails closed with a stable error code for unknown or out-of-scope
weapon events — it never borrows data from another batch and never falls back to latest.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .event_window import (
    AlignmentState,
    EventWindow,
    WindowAnchorInput,
    WindowPerspective,
    resolve_window,
)
from .generated_g5_dto import (
    WeaponEventDetailDTO,
    WeaponEventPerspectiveDTO,
    WeaponEventWindowDTO,
)
from .perspective import Perspective, PerspectiveInput, PerspectiveService
from .weapon_event import WeaponEvent, WeaponEventStore


class WeaponEventApplicationError(RuntimeError):
    def __init__(self, code: str, detail: str, *, http_status: int = 404) -> None:
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class WeaponEventSnapshot:
    event: WeaponEvent
    anchors: WindowAnchorInput
    geometry_available: bool
    series_available: bool
    target_projection_available: bool
    context_id: str | None = None


@dataclass(frozen=True, slots=True)
class WeaponEventScope:
    weapon_event_id: str
    batch_id: str
    release_id: str | None
    episode_id: str | None
    context_id: str | None


class WeaponEventReadAdapter(Protocol):
    """Exact canonical WE projection used by Application; no latest fallback."""

    def get(self, weapon_event_id: str) -> WeaponEventSnapshot | None: ...

    def list_ids(self, batch_id: str) -> Sequence[str]: ...

    def cluster_id(self, batch_id: str, weapon_event_id: str) -> str | None: ...


def _provenance(event: WeaponEvent, resolver_version: str) -> dict[str, object]:
    return {
        "authority_id": "GUI_WEAPON_EVENT_AUTHORITY",
        "resolver_version": resolver_version,
        "batch_id": event.batch_id,
        "release_id": event.release_id,
        "exact_identity": True,
        "latest_fallback": False,
    }


class WeaponEventApplicationService:
    """Single owner of the G5 weapon-event read models for one backend process.

    Distinguishes four runtime states so callers never mistake an unconfigured backend
    for "no weapon events": CAPABILITY_DISABLED (G5 not active), ADAPTER_UNAVAILABLE
    (backend adapter not configured), READY (source configured; may hold zero WEs), and
    per-request 404 only for a precise-but-absent WE id.
    """

    def __init__(
        self,
        store: WeaponEventStore | None = None,
        adapter: WeaponEventReadAdapter | None = None,
        *,
        capability_enabled: bool = True,
        adapter_ready: bool = True,
    ) -> None:
        self._stored: dict[str, WeaponEventSnapshot] = {}
        self._store = store
        self._adapter = adapter
        self._capability_enabled = capability_enabled
        self._adapter_ready = adapter_ready
        self._perspective = PerspectiveService()

    def capability_state(self) -> str:
        if not self._capability_enabled:
            return "CAPABILITY_DISABLED"
        if not self._adapter_ready:
            return "ADAPTER_UNAVAILABLE"
        return "READY"

    def batch_read_state(self, batch_id: str) -> str:
        """Data-level read state for one batch: EMPTY means a READY backend with zero WEs.

        The four-state contract (CAPABILITY_DISABLED / ADAPTER_UNAVAILABLE / EMPTY / READY)
        is fully realised: EMPTY is produced here for a ready backend that has no WE under
        the exact batch, never conflated with an unconfigured adapter or a missing WE id.
        """

        capability = self.capability_state()
        if capability != "READY":
            return capability
        return "READY" if self.list_ids(batch_id) else "EMPTY"

    def _require_ready(self) -> None:
        if not self._capability_enabled:
            raise WeaponEventApplicationError(
                "CAPABILITY_DISABLED",
                "weapon-event capability is not active for this backend",
                http_status=403,
            )
        if not self._adapter_ready:
            raise WeaponEventApplicationError(
                "ADAPTER_UNAVAILABLE",
                "weapon-event backend adapter is not configured",
                http_status=503,
            )

    def register(
        self,
        event: WeaponEvent,
        anchors: WindowAnchorInput,
        *,
        geometry_available: bool = False,
        series_available: bool = False,
        target_projection_available: bool = False,
        context_id: str | None = None,
    ) -> None:
        """Publish a detected WE + its authoritative anchors for read models."""

        self._stored[event.weapon_event_id] = WeaponEventSnapshot(
            event=event,
            anchors=anchors,
            geometry_available=geometry_available,
            series_available=series_available,
            target_projection_available=target_projection_available,
            context_id=context_id,
        )
        if self._store is not None:
            self._store.publish(event)

    def _require(self, weapon_event_id: str) -> WeaponEventSnapshot:
        self._require_ready()
        stored = self._stored.get(weapon_event_id)
        if stored is None and self._adapter is not None:
            stored = self._adapter.get(weapon_event_id)
        if stored is None:
            # 404 only means: the exact WE id does not exist under a READY backend.
            raise WeaponEventApplicationError(
                "WEAPON_EVENT_NOT_FOUND",
                f"weapon event not registered in this backend: {weapon_event_id}",
                http_status=404,
            )
        return stored

    def _cluster_id_for(self, event: WeaponEvent) -> str | None:
        """Resolve the cluster relation from the store (relation layer), not the event row.

        Attack Cluster is a relation over WEs; it never rewrites the WE itself, so the
        detail read model looks the relation up by WE id rather than trusting a stored
        event.cluster_id that was null at publish time.
        """

        if self._store is None:
            return (
                None
                if self._adapter is None
                else self._adapter.cluster_id(event.batch_id, event.weapon_event_id)
            )
        for cluster in self._store.list_clusters(event.batch_id):
            if event.weapon_event_id in cluster.weapon_event_ids:
                return cluster.cluster_id
        return None

    def resource_scope(self, weapon_event_id: str) -> WeaponEventScope:
        stored = self._require(weapon_event_id)
        event = stored.event
        return WeaponEventScope(
            weapon_event_id=event.weapon_event_id,
            batch_id=event.batch_id,
            release_id=event.release_id,
            episode_id=event.episode_id,
            context_id=stored.context_id,
        )

    def detail(self, weapon_event_id: str) -> WeaponEventDetailDTO:
        event = self._require(weapon_event_id).event
        return {
            "schema": "TPAA_G5_WEAPON_EVENT_DETAIL_V1",
            "weapon_event_id": event.weapon_event_id,
            "batch_id": event.batch_id,
            "release_id": event.release_id,
            "category": event.category.value,
            "category_rule_version": event.category_rule_version,
            "classification_exception": event.classification_exception,
            "shooter_entity_id": event.shooter_entity_id,
            "target_entity_id": event.target_entity_id,
            "episode_id": event.episode_id,
            "t1_session_time_us": str(event.t1_session_time_us),
            "weapon_terminal_state": event.weapon_terminal_state.value,
            "adjudication_state": event.adjudication_state.value,
            "observation_window_state": event.observation_window_state.value,
            "cluster_id": self._cluster_id_for(event),
            "provenance": _provenance(event, event.category_rule_version),
        }

    def window(self, weapon_event_id: str, perspective: str) -> WeaponEventWindowDTO:
        stored = self._require(weapon_event_id)
        try:
            side = WindowPerspective(perspective)
        except ValueError as exc:
            raise WeaponEventApplicationError(
                "PERSPECTIVE_INVALID", f"unsupported perspective: {perspective}", http_status=422
            ) from exc
        window = resolve_window(weapon_event_id, side, stored.anchors)
        return self._window_dto(window)

    @staticmethod
    def _window_dto(window: EventWindow) -> WeaponEventWindowDTO:
        def opt(value: int | None) -> str | None:
            return None if value is None else str(value)

        return {
            "schema": "TPAA_G5_WEAPON_EVENT_WINDOW_V1",
            "weapon_event_id": window.weapon_event_id,
            "perspective": window.perspective.value,
            "resolver_version": window.resolver_version,
            "start_session_time_us": str(window.start_session_time_us),
            "end_session_time_us": opt(window.end_session_time_us),
            "t0s_session_time_us": opt(window.t0s_session_time_us),
            "t0t_session_time_us": opt(window.t0t_session_time_us),
            "t1_session_time_us": str(window.t1_session_time_us),
            "t2_session_time_us": opt(window.t2_session_time_us),
            "t3_session_time_us": opt(window.t3_session_time_us),
            "cue_session_time_us": opt(window.cue_session_time_us),
            "response_session_time_us": opt(window.response_session_time_us),
            "j_session_time_us": opt(window.j_session_time_us),
            "terminal_state": window.terminal_state.value,
            "adjudication_state": window.adjudication_state.value,
            "window_state": window.window_state.value,
            "alignment_state": window.alignment_state.value,
            "coverage": window.coverage,
            "reason": window.reason,
            "provenance": {
                "authority_id": "GUI_WEAPON_EVENT_AUTHORITY",
                "resolver_version": window.resolver_version,
                "window_interval": "HALF_OPEN",
            },
        }

    def perspective(self, weapon_event_id: str, perspective: str) -> WeaponEventPerspectiveDTO:
        stored = self._require(weapon_event_id)
        try:
            side = Perspective(perspective)
        except ValueError as exc:
            raise WeaponEventApplicationError(
                "PERSPECTIVE_INVALID", f"unsupported perspective: {perspective}", http_status=422
            ) from exc
        projection = self._perspective.project(
            stored.event,
            side,
            PerspectiveInput(
                geometry_available=stored.geometry_available,
                series_available=stored.series_available,
                target_side_projection_available=stored.target_projection_available,
            ),
        )
        return {
            "schema": "TPAA_G5_WEAPON_EVENT_PERSPECTIVE_V1",
            "weapon_event_id": projection.weapon_event_id,
            "perspective": projection.perspective.value,
            "projection_version": projection.projection_version,
            "allowed": projection.allowed,
            "denial_reason": projection.denial_reason,
            "geometry_available": projection.geometry_available,
            "series_available": projection.series_available,
            "provenance": {
                "authority_id": "GUI_WEAPON_EVENT_AUTHORITY",
                "projection_version": projection.projection_version,
            },
        }

    def list_ids(self, batch_id: str) -> list[str]:
        local = [key for key, stored in self._stored.items() if stored.event.batch_id == batch_id]
        durable = [] if self._adapter is None else list(self._adapter.list_ids(batch_id))
        return sorted(set(local + durable))


def alignment_of(anchors: WindowAnchorInput) -> AlignmentState:
    return AlignmentState.ALIGNMENT_UNRESOLVED if anchors.alignment_unresolved else AlignmentState.ALIGNED
