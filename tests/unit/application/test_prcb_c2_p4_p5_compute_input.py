from __future__ import annotations

from pathlib import Path

from tools.testing.piqb_b2_postgres_p4_p5_persistence import (
    AS_OF,
    EPISODE,
    EVIDENCE,
    _composition,
    _p4,
    _seed,
    _subject,
)
from tpaa_application import (
    P4P5ComputeInputRepository,
    P4P5PersistenceRepository,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite
from tpaa_world import (
    M8EvidenceRef,
    M8WorldFactRef,
    build_p4_interaction_scope_snapshot,
)

H = "a" * 64


def test_prcb_c2_p4_p5_compute_inputs_survive_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    subject = _subject()
    p4 = _p4(subject)
    composition = _composition(subject)
    fact = M8WorldFactRef(
        ref_id="world:action:prcb-c2",
        world_layer="ACTION_WORLD",
        episode_id=EPISODE,
        stage_id=None,
        source_hash=H,
        knowledge_time_utc="2026-09-20T11:30:00Z",
    )
    machine = M8EvidenceRef(
        evidence_id="machine:action-timing:prcb-c2",
        origin="MACHINE",
        evidence_family="ACTION_TIMING",
        evidence_set_id=EVIDENCE,
        episode_id=EPISODE,
        world_refs=("world:action:prcb-c2",),
        source_refs=("metric:timing:prcb-c2",),
        availability_status="AVAILABLE",
        numeric_value=0.25,
        knowledge_time_utc="2026-09-20T11:40:00Z",
    )
    scope = build_p4_interaction_scope_snapshot(
        subject_context_id=subject.subject_context_id,
        episode_id=subject.episode_id,
        as_of_utc=subject.as_of_utc,
        fact_refs=(fact,),
        machine_evidence=(machine,),
        instructor_evidence=(),
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        _seed(uow.canonical_rows)
        products = P4P5PersistenceRepository(uow.canonical_rows)
        products.register_p4_revision(subject, p4)
        products.register_p5_composition(composition)
        snapshots = P4P5ComputeInputRepository(uow.canonical_rows)
        p4_snapshot_id = snapshots.register_p4_scope(scope)
        p5_snapshot_id = snapshots.register_p5_selection(
            composition,
            objective_result_refs=(
                "objective:CAP:2",
                "objective:CAP:1",
            ),
            evidence_set_id=EVIDENCE,
            as_of_utc=AS_OF,
        )
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        restarted = P4P5ComputeInputRepository(uow.canonical_rows)
        assert restarted.exact_p4_scope(p4_snapshot_id) == scope
        p5 = restarted.exact_p5_selection(p5_snapshot_id)
        assert p5.composition == composition
        assert p5.p4_revisions == (p4,)
        assert p5.objective_result_refs == (
            "objective:CAP:1",
            "objective:CAP:2",
        )
        assert p5.evidence_set_id == EVIDENCE
        assert p5.as_of_utc == AS_OF
        uow.commit()
