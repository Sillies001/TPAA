"""G5 Weapon Event unique owners: detector, identity, episode linker, category and cluster.

One Weapon Event (WE) per actual weapon launch; an Attack Cluster only relates WEs and
never changes WE cardinality.  WE is realised as an existing Event subtype plus relations
and Cluster as an existing Relation subtype (G1 admission); this module is the single owner
of detection, identity, linkage, categorisation and clustering — GUI/REST never recompute.

All states (weapon terminal / adjudication / observation window) are independent dimensions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid5

WE_NAMESPACE = UUID("8f5d2c10-7c1e-4a0b-9e3f-2d6a4b8c1e05")
CATEGORY_RULE_VERSION = "WE-CAT-1.0.0"
CLUSTER_RULE_VERSION = "WE-CLUSTER-1.0.0"


class WeaponCategory(StrEnum):
    WVR = "WVR"
    BVR = "BVR"
    STRIKE = "STRIKE"
    UNKNOWN = "UNKNOWN"


class WeaponTerminalState(StrEnum):
    TERMINAL_KNOWN = "TERMINAL_KNOWN"
    TERMINAL_UNKNOWN = "TERMINAL_UNKNOWN"


class AdjudicationState(StrEnum):
    ADJUDICATED = "ADJUDICATED"
    ADJUDICATION_PENDING = "ADJUDICATION_PENDING"


class ObservationWindowState(StrEnum):
    WINDOW_OPEN = "WINDOW_OPEN"
    WINDOW_PARTIAL = "WINDOW_PARTIAL"
    WINDOW_CLOSED = "WINDOW_CLOSED"


class WeaponEventError(RuntimeError):
    """Transport-safe, fail-closed G5 error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class WeaponLaunchFact:
    """Approved source fact consumed by the detector (Application-owned projection)."""

    source_launch_id: str
    batch_id: str
    release_id: str | None
    episode_id: str | None
    stage_id: str | None
    shooter_entity_id: str
    target_entity_id: str | None
    t1_session_time_us: int
    weapon_type_raw: str
    launch_range_m: int | None
    launch_aspect_deg: float | None
    session_time_end_us: int


@dataclass(frozen=True, slots=True)
class WeaponEvent:
    weapon_event_id: str
    batch_id: str
    release_id: str | None
    episode_id: str | None
    stage_id: str | None
    category: WeaponCategory
    category_rule_version: str
    classification_exception: bool
    shooter_entity_id: str
    target_entity_id: str | None
    t1_session_time_us: int
    weapon_terminal_state: WeaponTerminalState
    adjudication_state: AdjudicationState
    observation_window_state: ObservationWindowState
    cluster_id: str | None
    identity_material: str


@dataclass(frozen=True, slots=True)
class AttackCluster:
    cluster_id: str
    batch_id: str
    rule_version: str
    weapon_event_ids: tuple[str, ...]
    relation_kind: str = "SALVO"


class WeaponEventSource(Protocol):
    """Read approved weapon-launch source facts for exactly one batch."""

    def launch_facts(self, batch_id: str) -> Sequence[WeaponLaunchFact]: ...


class WeaponEventStore(Protocol):
    """Persist/lookup published Weapon Events (existing Event subtype + relations)."""

    def find_by_identity_material(self, batch_id: str, identity_material: str) -> WeaponEvent | None: ...

    def publish(self, event: WeaponEvent) -> None: ...

    def list_by_batch(self, batch_id: str) -> Sequence[WeaponEvent]: ...

    def publish_cluster(self, cluster: AttackCluster) -> None: ...

    def list_clusters(self, batch_id: str) -> Sequence[AttackCluster]: ...

    def publish_supersession(self, batch_id: str, superseding_id: str, superseded_id: str) -> None: ...

    def supersession_of(self, weapon_event_id: str) -> str | None: ...

    def superseded_by_of(self, weapon_event_id: str) -> str | None: ...


def _identity_material(fact: WeaponLaunchFact) -> str:
    return (
        f"{fact.batch_id}|{fact.source_launch_id}|{fact.shooter_entity_id}|"
        f"{fact.t1_session_time_us}|{fact.weapon_type_raw}"
    )


def _require_exact_batch(
    fact: WeaponLaunchFact,
    batch_id: str,
    audit: WeaponEventAuditSink | None = None,
    *,
    actor: str,
) -> None:
    """Fail closed when a source fact does not belong to the requested exact batch.

    Cross-batch WE borrowing is FORBIDDEN; a mismatched fact is rejected at the
    detector/identity boundary AND audited, not merely filtered at read time.
    """

    if fact.batch_id != batch_id:
        if audit is not None:
            audit.record(
                "CROSS_BATCH_WEAPON_EVENT_REJECTED",
                {
                    "requested_batch_id": batch_id,
                    "fact_batch_id": fact.batch_id,
                    "source_launch_id": fact.source_launch_id,
                    "actor": actor,
                },
            )
        raise WeaponEventError(
            "CROSS_BATCH_WEAPON_EVENT_FORBIDDEN",
            f"source launch fact batch {fact.batch_id!r} does not match requested batch {batch_id!r}",
        )


class WeaponEventAuditSink(Protocol):
    """Audit sink for cross-batch ingress rejections (DETECTOR_IDENTITY_IMMEDIATE_AUDITED)."""

    def record(self, event_type: str, details: Mapping[str, object]) -> None: ...


def stable_weapon_event_id(fact: WeaponLaunchFact) -> str:
    """Deterministic stable WE id from batch + launch identity material (UUID5)."""

    return str(uuid5(WE_NAMESPACE, _identity_material(fact)))


def resolve_category(
    weapon_type_raw: str,
    launch_range_m: int | None,
) -> tuple[WeaponCategory, bool]:
    """Classify WVR/BVR/Strike by weapon type primarily, geometry as a check.

    Returns (category, classification_exception).  Geometry never overrides the weapon
    type; a mismatch raises an exception flag rather than silently reclassifying.
    """

    raw = weapon_type_raw.strip().upper()
    if raw in {"", "UNKNOWN", "未识别"}:
        return WeaponCategory.UNKNOWN, True
    strike_tokens = ("STRIKE", "AIR_TO_GROUND", "对地", "航弹", "火箭")
    bvr_tokens = ("BVR", "RADAR", "中距", "远距", "主动雷达")
    wvr_tokens = ("WVR", "IR", "红外", "航炮", "近距")
    if any(token in raw for token in strike_tokens):
        return WeaponCategory.STRIKE, False
    if any(token in raw for token in bvr_tokens):
        category = WeaponCategory.BVR
    elif any(token in raw for token in wvr_tokens):
        category = WeaponCategory.WVR
    else:
        return WeaponCategory.UNKNOWN, True
    # Geometry is an auxiliary consistency check only; it flags, never reclassifies.
    exception = False
    if category is WeaponCategory.WVR and launch_range_m is not None and launch_range_m > 18_000:
        exception = True
    if category is WeaponCategory.BVR and launch_range_m is not None and launch_range_m < 5_000:
        exception = True
    return category, exception


def _terminal_state(facts_end_us: int, t1_us: int) -> WeaponTerminalState:
    # Terminal is UNKNOWN unless authoritative termination exists; coverage to data end
    # does NOT imply weapon terminal (terminal/adjudication/window are independent).
    _ = facts_end_us, t1_us
    return WeaponTerminalState.TERMINAL_UNKNOWN


class WeaponEventDetector:
    """Single owner: turn approved source launch facts into published WEs."""

    def __init__(
        self,
        source: WeaponEventSource,
        store: WeaponEventStore,
        audit: WeaponEventAuditSink | None = None,
    ) -> None:
        self._source = source
        self._store = store
        self._audit = audit

    def detect_and_publish(self, batch_id: str) -> list[WeaponEvent]:
        published: list[WeaponEvent] = []
        for fact in self._source.launch_facts(batch_id):
            _require_exact_batch(
                fact,
                batch_id,
                self._audit,
                actor="weapon_event_detector",
            )
            material = _identity_material(fact)
            existing = self._store.find_by_identity_material(batch_id, material)
            if existing is not None:
                # Idempotent replay / duplicate source record: keep stable identity.
                published.append(existing)
                continue
            category, exception = resolve_category(fact.weapon_type_raw, fact.launch_range_m)
            event = WeaponEvent(
                weapon_event_id=stable_weapon_event_id(fact),
                batch_id=fact.batch_id,
                release_id=fact.release_id,
                episode_id=fact.episode_id,
                stage_id=fact.stage_id,
                category=category,
                category_rule_version=CATEGORY_RULE_VERSION,
                classification_exception=exception,
                shooter_entity_id=fact.shooter_entity_id,
                target_entity_id=fact.target_entity_id,
                t1_session_time_us=fact.t1_session_time_us,
                weapon_terminal_state=_terminal_state(fact.session_time_end_us, fact.t1_session_time_us),
                adjudication_state=AdjudicationState.ADJUDICATION_PENDING,
                observation_window_state=ObservationWindowState.WINDOW_OPEN,
                cluster_id=None,
                identity_material=material,
            )
            self._store.publish(event)
            published.append(event)
        return published


class WeaponEventIdentityService:
    """Single owner: stable WE identity, supersession and dedup decisions.

    Identity material includes the exact launch fingerprint (batch + source launch id +
    shooter + t1 + weapon type).  Replaying the identical fact is idempotent (same UUID).
    A source revision that changes any fingerprint component yields a NEW stable UUID —
    it supersedes the old WE via relation rather than mutating it in place; history stays.
    """

    def __init__(self, store: WeaponEventStore, audit: WeaponEventAuditSink | None = None) -> None:
        self._store = store
        self._audit = audit

    def resolve(self, batch_id: str, fact: WeaponLaunchFact) -> WeaponEvent:
        _require_exact_batch(
            fact,
            batch_id,
            self._audit,
            actor="weapon_event_identity",
        )
        material = _identity_material(fact)
        existing = self._store.find_by_identity_material(batch_id, material)
        if existing is not None:
            return existing
        detector = WeaponEventDetector(_SingleFactSource(fact), self._store)
        created = detector.detect_and_publish(batch_id)[0]
        self._link_supersession(created, fact)
        return created

    def _link_supersession(self, created: WeaponEvent, fact: WeaponLaunchFact) -> None:
        """Record supersession when a revised fact re-identifies the same logical launch.

        Same (batch, source_launch_id, shooter) but different fingerprint => the new WE
        supersedes the prior one via an explicit relation (never an in-place mutation).
        The launch key is the identity material minus its t1/weapon-type suffix.
        """

        launch_key = f"{fact.batch_id}|{fact.source_launch_id}|{fact.shooter_entity_id}"
        current_candidates: list[WeaponEvent] = []
        for candidate in self._store.list_by_batch(fact.batch_id):
            if candidate.weapon_event_id == created.weapon_event_id:
                continue
            candidate_key = _launch_key_from_material(candidate.identity_material)
            if candidate_key == launch_key and candidate.identity_material != created.identity_material:
                if self._store.superseded_by_of(candidate.weapon_event_id) is None:
                    current_candidates.append(candidate)
        if len(current_candidates) > 1:
            raise WeaponEventError(
                "WEAPON_EVENT_SUPERSESSION_AMBIGUOUS",
                f"logical launch {launch_key!r} has multiple current revisions",
            )
        if current_candidates:
            self._store.publish_supersession(
                fact.batch_id,
                created.weapon_event_id,
                current_candidates[0].weapon_event_id,
            )


def _launch_key_from_material(material: str) -> str:
    """Return the logical-launch key (batch|source_launch_id|shooter) from identity material."""

    return material.rsplit("|", 2)[0]


class WeaponEventEpisodeLinker:
    """Single owner: bind a WE to its exact Episode/Stage with reason/confidence."""

    def link(self, event: WeaponEvent) -> tuple[str | None, str | None, str]:
        """Return (episode_id, stage_id, reason).  Unlinked WEs carry an explicit reason."""

        if event.episode_id:
            return event.episode_id, event.stage_id, "LINKED_FROM_SOURCE_FACT"
        return None, None, "EPISODE_NOT_ASSOCIATED_IN_SOURCE"


class AttackClusterResolver:
    """Single owner: group WEs into salvo clusters by salvo relation without merging WEs."""

    def __init__(self, store: WeaponEventStore) -> None:
        self._store = store

    def resolve(self, batch_id: str, salvo_groups: Iterable[Iterable[str]]) -> list[AttackCluster]:
        events = {event.weapon_event_id: event for event in self._store.list_by_batch(batch_id)}
        clusters: list[AttackCluster] = []
        for group in salvo_groups:
            ids = tuple(sorted({event_id for event_id in group if event_id in events}))
            if len(ids) < 2:
                # A salvo relation requires at least two WEs; a single WE is not a cluster.
                continue
            # Stable cluster identity derives only from the exact WE id set (order/position free).
            cluster_id = str(uuid5(WE_NAMESPACE, f"cluster|{batch_id}|{'|'.join(ids)}"))
            cluster = AttackCluster(
                cluster_id=cluster_id,
                batch_id=batch_id,
                rule_version=CLUSTER_RULE_VERSION,
                weapon_event_ids=ids,
            )
            self._store.publish_cluster(cluster)
            clusters.append(cluster)
        return clusters


@dataclass(slots=True)
class _SingleFactSource:
    fact: WeaponLaunchFact

    def launch_facts(self, batch_id: str) -> Sequence[WeaponLaunchFact]:
        _ = batch_id
        return (self.fact,)


def episode_link_summary(events: Sequence[WeaponEvent]) -> Mapping[str, int]:
    """Cardinality guard: WEs and Episodes are many-to-many via explicit link reasons."""

    linked = sum(1 for event in events if event.episode_id)
    return {"total": len(events), "linked": linked, "unlinked": len(events) - linked}
