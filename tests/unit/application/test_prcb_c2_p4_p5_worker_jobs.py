from __future__ import annotations

from pathlib import Path

from tools.testing.piqb_b2_postgres_p4_p5_persistence import (
    AIRCRAFT,
    AS_OF,
    EPISODE,
    EVIDENCE,
    ROLE_ARTIFACT,
    SESSION,
    TEAM,
    TWIN,
    _seed,
    _subject,
)
from tpaa_application import (
    JobStatus,
    P4P5ComputeInputRepository,
    P4P5PersistenceRepository,
)
from tpaa_assessment import (
    build_p4_assessment_revision,
    build_p5_aggregation,
    build_p5_assessment_revision,
    materialize_p4_human_machine_evidence,
    materialize_p5_team_mission_evidence,
)
from tpaa_context import P3ClaimEnvelope
from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite
from tpaa_world import (
    M8EvidenceRef,
    M8WorldFactRef,
    P5ParticipantBinding,
    build_p4_interaction_scope_snapshot,
    build_p5_composition_snapshot,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
P5_AS_OF = "2026-09-20T13:00:00Z"
HASH = "f" * 64


def test_prcb_c2_p4_p5_run_through_durable_governed_workers(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    object_root = tmp_path / "objects"
    bootstrap_sqlite(database)
    subject = _subject()
    fact = M8WorldFactRef(
        ref_id="world:action:prcb-c2-worker",
        world_layer="ACTION_WORLD",
        episode_id=EPISODE,
        stage_id=None,
        source_hash=HASH,
        knowledge_time_utc="2026-09-20T11:30:00Z",
    )
    machine = M8EvidenceRef(
        evidence_id="machine:action-timing:prcb-c2-worker",
        origin="MACHINE",
        evidence_family="ACTION_TIMING",
        evidence_set_id=EVIDENCE,
        episode_id=EPISODE,
        world_refs=(fact.ref_id,),
        source_refs=("metric:timing:prcb-c2-worker",),
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
        products.register_p4_subject(subject)
        p4_snapshot_id = P4P5ComputeInputRepository(
            uow.canonical_rows
        ).register_p4_scope(scope)
        uow.commit()

    expected_p4 = build_p4_assessment_revision(
        subject,
        evidence=materialize_p4_human_machine_evidence(subject, scope),
        annotations=(),
        p3_claim=P3ClaimEnvelope(
            claim_level="P3_EVIDENCE_UNAVAILABLE",
            validity_status="UNAVAILABLE",
            as_of_utc=AS_OF,
            uncertainty_lower=None,
            uncertainty_upper=None,
        ),
        confidence=0.9,
        created_at_utc=AS_OF,
        approval_state="DRAFT",
        supersedes_id=None,
    )

    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=AUTHORITY,
            object_root=object_root,
            desktop_database_path=database,
        )
    )
    p4_job = runtime.application.submit_job(
        idempotency_key="prcb-c2-p4-assessment",
        command="P4_ASSESSMENT",
        payload={
            "scope_snapshot_id": p4_snapshot_id,
            "confidence": "0.9",
            "created_at_utc": AS_OF,
        },
        actor="PRCB-C2-TEST",
    )
    assert p4_job.record.status is JobStatus.SUCCEEDED

    with SQLiteDesktopUnitOfWork(database) as uow:
        products = P4P5PersistenceRepository(uow.canonical_rows)
        persisted_p4 = products.exact_p4_revision(
            expected_p4.actor_assessment_id
        )
        assert persisted_p4 == expected_p4
        assert persisted_p4.approval_state == "DRAFT"
        assert persisted_p4.instructor_annotation_ids == ()
        uow.commit()

    participant = P5ParticipantBinding(
        subject_key=subject.subject_key,
        role_code="FLIGHT_LEAD",
        aircraft_id=AIRCRAFT,
        twin_revision_id=TWIN,
        p4_revision_id=expected_p4.actor_assessment_id,
    )
    composition = build_p5_composition_snapshot(
        session_id=SESSION,
        mission_episode_id=EPISODE,
        team_id=TEAM,
        participants=(participant,),
        world_snapshot_refs=("world:mission:prcb-c2-worker",),
        scenario_context_artifact_id=None,
        role_model_context_artifact_id=ROLE_ARTIFACT,
        assessment_spec_id="P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        as_of_utc=P5_AS_OF,
    )
    objective_refs = (
        "objective:prcb-c2:2",
        "objective:prcb-c2:1",
    )
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        p5_snapshot_id = P4P5ComputeInputRepository(
            uow.canonical_rows
        ).register_p5_selection(
            composition,
            objective_result_refs=objective_refs,
            evidence_set_id=EVIDENCE,
            as_of_utc=P5_AS_OF,
        )
        uow.commit()

    p5_evidence = materialize_p5_team_mission_evidence(
        composition,
        p4_revisions=(expected_p4,),
        evidence_set_id=EVIDENCE,
        objective_result_refs=objective_refs,
        as_of_utc=P5_AS_OF,
    )
    expected_p5 = build_p5_assessment_revision(
        composition,
        evidence=p5_evidence,
        aggregation=build_p5_aggregation(p5_evidence),
        confidence=0.8,
        created_at_utc=P5_AS_OF,
        approval_state="DRAFT",
        supersedes=None,
    )
    p5_job = runtime.application.submit_job(
        idempotency_key="prcb-c2-p5-assessment",
        command="P5_ASSESSMENT",
        payload={
            "selection_snapshot_id": p5_snapshot_id,
            "confidence": "0.8",
            "created_at_utc": P5_AS_OF,
        },
        actor="PRCB-C2-TEST",
    )
    assert p5_job.record.status is JobStatus.SUCCEEDED

    with SQLiteDesktopUnitOfWork(database) as uow:
        persisted_p5 = P4P5PersistenceRepository(
            uow.canonical_rows
        ).exact_p5_revision(expected_p5.mission_assessment_id)
        assert persisted_p5 == expected_p5
        assert persisted_p5.approval_state == "DRAFT"
        assert persisted_p5.overall_score is None
        assert persisted_p5.grade is None
        uow.commit()

    restarted = build_desktop_production_runtime(runtime.config)
    assert restarted.application.job(
        p4_job.record.job_id
    ).status is JobStatus.SUCCEEDED
    assert restarted.application.job(
        p5_job.record.job_id
    ).status is JobStatus.SUCCEEDED
