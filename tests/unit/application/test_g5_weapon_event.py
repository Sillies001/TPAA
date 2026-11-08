"""G5 Weapon Event/Window/Perspective exit-gate tests (positive and negative)."""

from __future__ import annotations

import pytest

from tests.fixtures.weapon_events import (
    InMemoryWeaponEventStore,
    StaticLaunchSource,
    launch_fact,
    shooter_anchors,
)
from tpaa_application.event_window import (
    AlignmentState,
    WindowAdjudicationState,
    WindowPerspective,
    WindowState,
    WindowTerminalState,
    resolve_window,
    windows_overlap,
)
from tpaa_application.perspective import Perspective, PerspectiveInput, PerspectiveService
from tpaa_application.weapon_event import (
    AttackClusterResolver,
    WeaponCategory,
    WeaponEventDetector,
    WeaponEventEpisodeLinker,
    WeaponEventIdentityService,
    resolve_category,
    stable_weapon_event_id,
)

BATCH = "b-batch-0001"


def _detect(store: InMemoryWeaponEventStore, *facts: object) -> list:
    source = StaticLaunchSource(facts)  # type: ignore[arg-type]
    return WeaponEventDetector(source, store).detect_and_publish(BATCH)


def test_single_launch_yields_single_weapon_event() -> None:
    store = InMemoryWeaponEventStore()
    events = _detect(store, launch_fact("L1"))
    assert len(events) == 1
    assert events[0].batch_id == BATCH
    assert events[0].category is WeaponCategory.WVR
    # One WE per launch; detector is the unique owner and does not duplicate.
    assert len(_detect(store, launch_fact("L1"))) == 1
    assert len(store.list_by_batch(BATCH)) == 1


def test_salvo_yields_multiple_we_plus_cluster_relation() -> None:
    store = InMemoryWeaponEventStore()
    events = _detect(
        store,
        launch_fact("L1", t1_us=12_170_000),
        launch_fact("L2", t1_us=12_230_000),
    )
    assert len(events) == 2
    clusters = AttackClusterResolver(store).resolve(BATCH, [(events[0].weapon_event_id, events[1].weapon_event_id)])
    assert len(clusters) == 1
    assert set(clusters[0].weapon_event_ids) == {event.weapon_event_id for event in events}
    # Cluster is a relation only: WE cardinality unchanged.
    assert len(store.list_by_batch(BATCH)) == 2
    # A single-WE "salvo" is not a cluster.
    store2 = InMemoryWeaponEventStore()
    single = _detect(store2, launch_fact("L9"))
    assert AttackClusterResolver(store2).resolve(BATCH, [(single[0].weapon_event_id,)]) == []


def test_episode_multi_and_interleaved_we_keep_exact_links() -> None:
    store = InMemoryWeaponEventStore()
    events = _detect(
        store,
        launch_fact("L1", episode_id="ep-1", t1_us=12_000_000),
        launch_fact("L2", episode_id="ep-2", t1_us=13_000_000),
        launch_fact("L3", episode_id="ep-1", t1_us=18_000_000),
    )
    linker = WeaponEventEpisodeLinker()
    links = [linker.link(event) for event in events]
    assert [link[0] for link in links] == ["ep-1", "ep-2", "ep-1"]
    assert all(link[2] == "LINKED_FROM_SOURCE_FACT" for link in links)


def test_unlinked_we_carries_explicit_reason() -> None:
    store = InMemoryWeaponEventStore()
    event = _detect(store, launch_fact("L1", episode_id=None))[0]
    episode, stage, reason = WeaponEventEpisodeLinker().link(event)
    assert episode is None and stage is None and reason == "EPISODE_NOT_ASSOCIATED_IN_SOURCE"


def test_identity_is_stable_and_idempotent() -> None:
    store = InMemoryWeaponEventStore()
    fact = launch_fact("L1")
    first = WeaponEventIdentityService(store).resolve(BATCH, fact)
    second = WeaponEventIdentityService(store).resolve(BATCH, fact)
    assert first.weapon_event_id == second.weapon_event_id
    assert first.weapon_event_id == stable_weapon_event_id(fact)
    assert len(store.list_by_batch(BATCH)) == 1


@pytest.mark.parametrize(
    ("raw", "range_m", "expected", "exception"),
    [
        ("IR_MISSILE", 9_000, WeaponCategory.WVR, False),
        ("RADAR_BVR_MISSILE", 60_000, WeaponCategory.BVR, False),
        ("STRIKE_ROCKET", None, WeaponCategory.STRIKE, False),
        ("MYSTERY_DEVICE", None, WeaponCategory.UNKNOWN, True),
        ("IR_MISSILE", 25_000, WeaponCategory.WVR, True),  # geometry flags, never reclassifies
        ("RADAR_BVR_MISSILE", 3_000, WeaponCategory.BVR, True),
    ],
)
def test_category_resolution_rules(
    raw: str, range_m: int | None, expected: WeaponCategory, exception: bool
) -> None:
    category, flag = resolve_category(raw, range_m)
    assert category is expected
    assert flag is exception


def test_terminal_adjudication_window_states_are_independent() -> None:
    # Missing T2 => TERMINAL_UNKNOWN, but adjudication/window still resolve independently.
    window = resolve_window(
        "we-1",
        WindowPerspective.SHOOTER,
        shooter_anchors(t2_session_time_us=None, j_session_time_us=40_000_000, t3_session_time_us=50_000_000),
    )
    assert window.terminal_state is WindowTerminalState.TERMINAL_UNKNOWN
    assert window.adjudication_state is WindowAdjudicationState.ADJUDICATED
    assert window.window_state is WindowState.WINDOW_CLOSED


def test_missing_t2_t3_yields_open_window() -> None:
    window = resolve_window(
        "we-1",
        WindowPerspective.SHOOTER,
        shooter_anchors(t2_session_time_us=None, t3_session_time_us=None, j_session_time_us=None),
    )
    assert window.end_session_time_us is None
    assert window.window_state is WindowState.WINDOW_OPEN
    assert window.terminal_state is WindowTerminalState.TERMINAL_UNKNOWN
    assert window.adjudication_state is WindowAdjudicationState.ADJUDICATION_PENDING
    assert window.coverage == "OPEN_END"


def test_clock_gap_and_unresolved_alignment_are_distinct() -> None:
    gap = resolve_window("we-1", WindowPerspective.SHOOTER, shooter_anchors(clock_gap_after_t1=True))
    assert gap.coverage == "PARTIAL_GAP"
    assert gap.alignment_state is AlignmentState.ALIGNED
    unresolved = resolve_window("we-1", WindowPerspective.SHOOTER, shooter_anchors(alignment_unresolved=True))
    assert unresolved.alignment_state is AlignmentState.ALIGNMENT_UNRESOLVED
    assert unresolved.coverage == "UNRESOLVED"


def test_windows_are_half_open_and_may_overlap() -> None:
    anchors = shooter_anchors()
    first = resolve_window("we-1", WindowPerspective.SHOOTER, anchors)
    # Half-open [start, end): start inclusive, end exclusive.
    assert first.contains(first.start_session_time_us)
    assert first.end_session_time_us is not None and not first.contains(first.end_session_time_us)
    # Overlapping windows within an episode are allowed (no force slicing).
    second = resolve_window("we-2", WindowPerspective.SHOOTER, shooter_anchors(t1_session_time_us=15_000_000))
    assert windows_overlap(first, second)


def test_target_window_never_uses_cue_as_t0t() -> None:
    window = resolve_window(
        "we-1",
        WindowPerspective.TARGET,
        shooter_anchors(t0t_session_time_us=None, cue_session_time_us=11_500_000, response_session_time_us=13_000_000),
    )
    assert window.start_session_time_us == 11_500_000  # falls back to cue, not mislabeled T0-T
    assert window.t0t_session_time_us is None
    assert window.cue_session_time_us == 11_500_000
    assert window.response_session_time_us == 13_000_000


def test_perspective_shooter_allowed_target_fail_closed_for_strike() -> None:
    store = InMemoryWeaponEventStore()
    service = PerspectiveService()
    wvr = _detect(store, launch_fact("L1", weapon_type_raw="IR_MISSILE"))[0]
    strike = _detect(store, launch_fact("L2", weapon_type_raw="STRIKE_ROCKET"))[0]
    available = PerspectiveInput(True, True, True)
    assert service.project(wvr, Perspective.SHOOTER, available).allowed
    target = service.project(wvr, Perspective.TARGET, available)
    assert target.allowed and target.geometry_available
    denied = service.project(strike, Perspective.TARGET, available)
    assert not denied.allowed and denied.denial_reason == "NOT_APPLICABLE_STRIKE_TARGET"


def test_perspective_missing_geometry_surfaces_unavailable_not_fabricated() -> None:
    store = InMemoryWeaponEventStore()
    service = PerspectiveService()
    wvr = _detect(store, launch_fact("L1"))[0]
    projection = service.project(wvr, Perspective.SHOOTER, PerspectiveInput(False, False, True))
    assert projection.allowed
    assert not projection.geometry_available and not projection.series_available


def test_cross_batch_fact_is_rejected_at_detector_and_identity() -> None:
    from tpaa_application.weapon_event import WeaponEventError
    store = InMemoryWeaponEventStore()
    # A (misbehaving) source that returns a batch-B fact even when asked for batch-A.
    cross = launch_fact("L1", batch_id="batch-B")

    class _RawSource:
        def launch_facts(self, batch_id: str):  # noqa: ANN001
            return (cross,)

    detector = WeaponEventDetector(_RawSource(), store)
    with pytest.raises(WeaponEventError) as excinfo:
        detector.detect_and_publish("batch-A")
    assert excinfo.value.code == "CROSS_BATCH_WEAPON_EVENT_FORBIDDEN"
    # Identity must reject the same cross-batch fact.
    with pytest.raises(WeaponEventError):
        WeaponEventIdentityService(store).resolve("batch-A", cross)
    # No WE may leak into another batch.
    assert store.list_by_batch("batch-A") == []


def test_cluster_id_is_stable_regardless_of_input_order() -> None:
    store = InMemoryWeaponEventStore()
    events = _detect(store, launch_fact("L1", t1_us=12_000_000), launch_fact("L2", t1_us=13_000_000))
    ids = [event.weapon_event_id for event in events]
    first = AttackClusterResolver(store).resolve(BATCH, [(ids[0], ids[1])])
    store2 = InMemoryWeaponEventStore()
    events2 = _detect(store2, launch_fact("L1", t1_us=12_000_000), launch_fact("L2", t1_us=13_000_000))
    ids2 = [event.weapon_event_id for event in events2]
    # Same salvo set, reversed input order must produce the same cluster id.
    second = AttackClusterResolver(store2).resolve(BATCH, [(ids2[1], ids2[0])])
    assert first[0].cluster_id == second[0].cluster_id


def test_source_revision_yields_new_uuid_supersession_not_mutation() -> None:
    store = InMemoryWeaponEventStore()
    original = WeaponEventIdentityService(store).resolve(BATCH, launch_fact("L1", t1_us=12_170_000))
    # Same fact replayed is idempotent.
    replayed = WeaponEventIdentityService(store).resolve(BATCH, launch_fact("L1", t1_us=12_170_000))
    assert replayed.weapon_event_id == original.weapon_event_id
    # A source revision (t1 changes) yields a NEW stable UUID, never an in-place mutation.
    revised = WeaponEventIdentityService(store).resolve(BATCH, launch_fact("L1", t1_us=12_171_000))
    assert revised.weapon_event_id != original.weapon_event_id
    # Both coexist (supersession preserves history); the old WE is not overwritten.
    assert len(store.list_by_batch(BATCH)) == 2


class _RecordingAuditSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record(self, event_type: str, details: dict) -> None:
        self.events.append((event_type, details))


def test_supersession_relation_is_published_and_queryable() -> None:
    store = InMemoryWeaponEventStore()
    identity = WeaponEventIdentityService(store)
    original = identity.resolve(BATCH, launch_fact("L1", t1_us=12_170_000))
    revised = identity.resolve(BATCH, launch_fact("L1", t1_us=12_171_000))
    assert revised.weapon_event_id != original.weapon_event_id
    # The new WE supersedes the old via an explicit, queryable relation (not just coexistence).
    assert store.supersession_of(revised.weapon_event_id) == original.weapon_event_id
    assert store.superseded_by_of(original.weapon_event_id) == revised.weapon_event_id
    assert store.supersession_of(original.weapon_event_id) is None


def test_three_revisions_form_a_linear_supersession_chain() -> None:
    store = InMemoryWeaponEventStore()
    identity = WeaponEventIdentityService(store)
    first = identity.resolve(BATCH, launch_fact("L1", t1_us=12_170_000))
    second = identity.resolve(BATCH, launch_fact("L1", t1_us=12_171_000))
    third = identity.resolve(BATCH, launch_fact("L1", t1_us=12_172_000))

    assert store.supersession_of(second.weapon_event_id) == first.weapon_event_id
    assert store.supersession_of(third.weapon_event_id) == second.weapon_event_id
    assert store.superseded_by_of(first.weapon_event_id) == second.weapon_event_id
    assert store.superseded_by_of(second.weapon_event_id) == third.weapon_event_id
    assert store.superseded_by_of(third.weapon_event_id) is None


def test_cross_batch_rejection_is_audited() -> None:
    from tpaa_application.weapon_event import WeaponEventError
    store = InMemoryWeaponEventStore()
    audit = _RecordingAuditSink()
    cross = launch_fact("L1", batch_id="batch-B")

    class _RawSource:
        def launch_facts(self, batch_id: str):
            return (cross,)

    detector = WeaponEventDetector(_RawSource(), store, audit=audit)
    with pytest.raises(WeaponEventError):
        detector.detect_and_publish("batch-A")
    assert audit.events and audit.events[0][0] == "CROSS_BATCH_WEAPON_EVENT_REJECTED"
    assert audit.events[0][1]["fact_batch_id"] == "batch-B"
    assert audit.events[0][1]["requested_batch_id"] == "batch-A"


def test_identity_cross_batch_rejection_records_identity_actor() -> None:
    from tpaa_application.weapon_event import WeaponEventError

    store = InMemoryWeaponEventStore()
    audit = _RecordingAuditSink()
    with pytest.raises(WeaponEventError):
        WeaponEventIdentityService(store, audit=audit).resolve(
            "batch-A",
            launch_fact("L1", batch_id="batch-B"),
        )
    assert audit.events[0][1]["actor"] == "weapon_event_identity"


def test_cross_batch_rejection_can_be_persisted_through_shared_security_sink() -> None:
    from tpaa_application import InMemorySecurityAuditSink
    from tpaa_application.weapon_event import WeaponEventError
    from tpaa_runtime.security_audit import WeaponEventSecurityAuditAdapter

    store = InMemoryWeaponEventStore()
    persistent_port = InMemorySecurityAuditSink()
    audit = WeaponEventSecurityAuditAdapter(persistent_port)
    with pytest.raises(WeaponEventError):
        WeaponEventIdentityService(store, audit=audit).resolve(
            "batch-A",
            launch_fact("L1", batch_id="batch-B"),
        )
    record = persistent_port.events[0]
    assert record.action == "CROSS_BATCH_WEAPON_EVENT_REJECTED"
    assert record.outcome == "DENY"
    assert record.reason == "CROSS_BATCH_WEAPON_EVENT_FORBIDDEN"
