"""Shared durable P3/P4 fixture for PIQB B2 P6 model-build reconstruction."""

from __future__ import annotations

from dataclasses import dataclass

from tools.testing.piqb_b2_p3_fixture import (
    AIRCRAFT,
    CONFIG,
    CONTEXT,
    EVIDENCE,
    build_fixture,
    seed_upstream,
)
from tpaa_application import (
    P3PersistenceRepository,
    P4P5PersistenceRepository,
    P6PersistenceRepository,
)
from tpaa_assessment import P4AssessmentRevision, P4SubjectContext
from tpaa_capability import (
    P6CapabilityTrainingRow,
    P6ManagedModelObject,
    P6ModelBuild,
    evaluate_twin_capability_estimate,
    execute_p6_model_training,
)
from tpaa_context import canonical_hash, pseudonymous_subject_key
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.object_store import LocalObjectStore

SESSION_ORDER_SCOPE = "96100000-0000-4000-8000-000000000020"
ACTOR = "96600000-0000-4000-8000-000000000001"
ROLE_ARTIFACT = "96600000-0000-4000-8000-000000000002"
AS_OF = "2026-09-10T12:00:00Z"


@dataclass(frozen=True, slots=True)
class P6ResolverFixture:
    build: P6ModelBuild
    managed: P6ManagedModelObject
    training_rows: tuple[P6CapabilityTrainingRow, ...]


def _uuid(prefix: str, index: int) -> str:
    return f"{prefix}-0000-4000-8000-{index:012d}"


def _subject_and_revision(
    *,
    estimate,
    session_id: str,
    episode_id: str,
    actor_assessment_id: str,
    order: int,
) -> tuple[P4SubjectContext, P4AssessmentRevision]:
    subject_key = pseudonymous_subject_key(ACTOR)
    subject_values = {
        "subject_key": subject_key,
        "role_code": "PILOT",
        "seat_code": "FRONT",
        "function_code": None,
        "session_id": session_id,
        "episode_id": episode_id,
        "stage_id": None,
        "aircraft_id": AIRCRAFT,
        "twin_revision_id": estimate.twin_revision_id,
        "p3_estimate_id": estimate.estimate_id,
        "assessment_spec_id": "P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        "assessment_spec_version": "1.0.0",
        "role_model_context_artifact_id": ROLE_ARTIFACT,
        "as_of_utc": estimate.as_of_time,
    }
    subject = P4SubjectContext(
        subject_context_id=(
            "P4_SUBJECT_CONTEXT_SHA256:" + canonical_hash(subject_values)
        ),
        subject_key=subject_key,
        actor_id=ACTOR,
        role_code="PILOT",
        seat_code="FRONT",
        function_code=None,
        session_id=session_id,
        episode_id=episode_id,
        stage_id=None,
        aircraft_id=AIRCRAFT,
        twin_revision_id=estimate.twin_revision_id,
        p3_estimate_id=estimate.estimate_id,
        assessment_spec_id="P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        role_model_context_artifact_id=ROLE_ARTIFACT,
        role_model_version="1.0.0",
        world_refs=(),
        evidence_set_id=EVIDENCE,
        as_of_utc=estimate.as_of_time,
        knowledge_time_utc=estimate.as_of_time,
    )
    uncertainty = dict(estimate.uncertainty)
    lower_raw = uncertainty.get("lower")
    upper_raw = uncertainty.get("upper")
    lower = None if lower_raw is None else float(lower_raw)
    upper = None if upper_raw is None else float(upper_raw)
    created_at = f"2026-09-10T06:{order:02d}:00Z"
    revision_values = {
        "subject_context_id": subject.subject_context_id,
        "subject_key": subject.subject_key,
        "actor_id": subject.actor_id,
        "role_code": subject.role_code,
        "seat_code": subject.seat_code,
        "function_code": subject.function_code,
        "session_id": subject.session_id,
        "episode_id": subject.episode_id,
        "aircraft_id": subject.aircraft_id,
        "twin_revision_id": subject.twin_revision_id,
        "p3_estimate_id": subject.p3_estimate_id,
        "assessment_spec_id": subject.assessment_spec_id,
        "assessment_spec_version": subject.assessment_spec_version,
        "role_model_version": subject.role_model_version,
        "world_refs": [],
        "machine_evidence_ids": [],
        "instructor_annotation_ids": [],
        "score": None,
        "grade": None,
        "status": "APPROVED",
        "confidence": 0.9,
        "evidence_set_id": subject.evidence_set_id,
        "created_at_utc": created_at,
        "supersedes_id": None,
        "approval_state": "APPROVED",
        "p3_claim_level": estimate.claim_level,
        "p3_validity_status": estimate.validity_domain_status,
        "p3_as_of_utc": estimate.as_of_time,
        "uncertainty_lower": lower,
        "uncertainty_upper": upper,
    }
    revision = P4AssessmentRevision(
        actor_assessment_id=actor_assessment_id,
        subject_context_id=subject.subject_context_id,
        subject_key=subject.subject_key,
        actor_id=subject.actor_id,
        role_code=subject.role_code,
        seat_code=subject.seat_code,
        function_code=subject.function_code,
        session_id=subject.session_id,
        episode_id=subject.episode_id,
        aircraft_id=subject.aircraft_id,
        twin_revision_id=subject.twin_revision_id,
        p3_estimate_id=subject.p3_estimate_id,
        assessment_spec_id=subject.assessment_spec_id,
        assessment_spec_version=subject.assessment_spec_version,
        role_model_version=subject.role_model_version,
        world_refs=(),
        machine_evidence_ids=(),
        instructor_annotation_ids=(),
        score=None,
        grade=None,
        status="APPROVED",
        confidence=0.9,
        evidence_set_id=subject.evidence_set_id,
        created_at_utc=created_at,
        supersedes_id=None,
        approval_state="APPROVED",
        p3_claim_level=estimate.claim_level,
        p3_validity_status=estimate.validity_domain_status,
        p3_as_of_utc=estimate.as_of_time,
        uncertainty_lower=lower,
        uncertainty_upper=upper,
        logical_content_hash=canonical_hash(revision_values),
    )
    return subject, revision


def seed_p6_model_resolver_case(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
) -> P6ResolverFixture:
    seed_upstream(rows)
    source = build_fixture()
    p3 = P3PersistenceRepository(rows, object_store=object_store)
    p3.register_component(
        segment=source.segment,
        validation=source.validation,
        training=source.training,
        model_build=source.model_build,
        surface_build=source.surface_build,
        model_object=source.model_object,
        surface_object=source.surface_object,
    )
    p3.register_twin(source.twin, components=(source.component,))

    rows.insert(
        "registry.session_order_scope",
        {
            "session_order_scope_id": SESSION_ORDER_SCOPE,
            "scope_code": "PIQB-B2-P6",
            "scope_type": "TRAINING_SEQUENCE",
            "subject_kind": "AIRCRAFT",
            "selector_json": {"aircraft_id": AIRCRAFT},
            "selector_hash": "c" * 64,
            "selector_language_version": "1.0.0",
            "scope_revision": 1,
            "status": "ACTIVE",
            "description": "PIQB B2 P6 durable resolver qualification",
        },
        field_kinds={"selector_json": "json"},
    )

    p4 = P4P5PersistenceRepository(rows)
    training_rows: list[P6CapabilityTrainingRow] = []
    for order in range(1, 5):
        estimate = evaluate_twin_capability_estimate(
            twin=source.twin,
            components=(source.component,),
            capability_type="KINEMATIC_ENERGY_CONTROL",
            condition_point={
                "session_order": order,
                "reference_condition_id": source.segment.reference_condition_id,
            },
            as_of_time_utc="2026-09-10T04:00:00Z",
            created_at_utc=f"2026-09-10T04:{order:02d}:00Z",
        )
        p3.register_estimate(estimate)
        session_id = _uuid("96200000", order)
        assignment_id = _uuid("96300000", order)
        episode_id = _uuid("96400000", order)
        assessment_id = _uuid("96500000", order)
        rows.insert(
            "registry.training_session",
            {
                "session_id": session_id,
                "session_code": f"PIQB-B2-P6-{order}",
                "session_type": "SIM",
                "start_session_time_us": 0,
                "end_session_time_us": 1_000_000,
                "start_occurred_at_utc": f"2026-09-{order:02d}T00:00:00Z",
                "end_occurred_at_utc": f"2026-09-{order:02d}T00:10:00Z",
                "session_order": order,
                "session_order_source": "MANUAL_REVIEWED",
                "session_order_scope_id": SESSION_ORDER_SCOPE,
                "training_type_set": ("QUALIFICATION",),
                "data_status": "READY",
                "source_count": 1,
                "schema_version": "1.8.0",
            },
            field_kinds={"training_type_set": "text_array"},
        )
        rows.insert(
            "registry.session_order_assignment",
            {
                "assignment_id": assignment_id,
                "session_order_scope_id": SESSION_ORDER_SCOPE,
                "session_id": session_id,
                "order_value": order,
                "source": "MANUAL_REVIEWED",
                "revision_no": 1,
                "is_current": True,
                "reason": "PIQB B2 P6 durable resolver qualification",
                "operator_ref": "PIQB-B2",
            },
        )
        rows.insert(
            "episode.training_episode",
            {
                "episode_id": episode_id,
                "session_id": session_id,
                "episode_type": "MISSION",
                "context_id": CONTEXT,
                "start_session_time_us": 0,
                "end_session_time_us": 1_000_000,
                "subject_scope": "AIRCRAFT",
                "primary_aircraft_id": AIRCRAFT,
                "world_capability_code": "P6",
                "episode_status": "COMPLETE",
                "detector_version": "PIQB-B2",
                "coverage": 1.0,
                "confidence": 1.0,
            },
        )
        subject, revision = _subject_and_revision(
            estimate=estimate,
            session_id=session_id,
            episode_id=episode_id,
            actor_assessment_id=assessment_id,
            order=order,
        )
        p4.register_p4_revision(subject, revision)
        training_rows.append(
            P6CapabilityTrainingRow(
                estimate=estimate,
                p4_revision=revision,
                aircraft_id=AIRCRAFT,
                configuration_snapshot_id=CONFIG,
                session_order_assignment_id=assignment_id,
                session_order=order,
            )
        )

    build = execute_p6_model_training(
        tuple(training_rows),
        as_of_utc=AS_OF,
        trained_at_utc="2026-09-10T12:30:00Z",
    )
    managed = P6ManagedModelObject(
        object_ref_id=build.model.model_object_ref_id,
        managed_uri=build.model.model_artifact_uri,
        artifact_sha256=build.model.model_artifact_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
        sealed_at_utc="2026-09-10T12:31:00Z",
    )
    p6 = P6PersistenceRepository(rows, object_store=object_store)
    p6.register_model_build(build, managed)
    return P6ResolverFixture(
        build=build,
        managed=managed,
        training_rows=tuple(training_rows),
    )
