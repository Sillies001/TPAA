"""PRCB C5 downstream qualification preparation for P3 through P6."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import (
    P3PersistenceRepository,
    P4P5ComputeInputRepository,
    P4P5PersistenceRepository,
    P6PersistenceRepository,
)
from tpaa_assessment import (
    P4AssessmentRevision,
    P5AssessmentRevision,
    build_p4_assessment_revision,
    build_p5_aggregation,
    build_p5_assessment_revision,
    materialize_p4_human_machine_evidence,
    materialize_p5_team_mission_evidence,
)
from tpaa_capability import (
    P6ContextRef,
    P6CounterfactualRequestBinding,
    P6CounterfactualRevision,
    P6FactualSourceRevision,
    P6ForecastExecutionProfile,
    P6ForecastRequestBinding,
    P6ForecastRevision,
    build_p6_counterfactual_request_binding,
    build_p6_forecast_request_binding,
    build_p6_input_snapshot,
    execute_p6_counterfactual,
    execute_p6_forecast,
)
from tpaa_context import P3ClaimEnvelope
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.object_store import LocalObjectStore
from tpaa_world import (
    M8EvidenceRef,
    M8WorldFactRef,
    P5ParticipantBinding,
    build_p4_interaction_scope_snapshot,
    build_p5_composition_snapshot,
)

from .prcb_c5_p3_seed import (
    PRCBC5P3QualificationFixture,
    build_prcb_c5_p3_fixture,
    seed_prcb_c5_p3_upstream,
)
from .prcb_c5_p4_p5_seed import (
    AIRCRAFT as P45_AIRCRAFT,
    AS_OF as P45_AS_OF,
    EPISODE as P45_EPISODE,
    EVIDENCE as P45_EVIDENCE,
    ROLE_ARTIFACT as P45_ROLE_ARTIFACT,
    SESSION as P45_SESSION,
    TEAM as P45_TEAM,
    TWIN as P45_TWIN,
    build_prcb_c5_p4_subject,
    seed_prcb_c5_p4_p5_upstream,
)
from .prcb_c5_p6_seed import (
    PRCBC5P6ResolverSeed,
    seed_prcb_c5_p6_model_resolver_case,
)

P5_AS_OF = "2026-09-20T13:00:00Z"
P6_P4_SOURCE = "97100000-0000-4000-8000-000000000002"
P6_CONTEXT = "97100000-0000-4000-8000-000000000003"
P6_FORECAST_PUBLISHED = "2026-09-10T13:30:00Z"
P6_COUNTERFACTUAL_CREATED = "2026-09-10T13:40:00Z"
HASH = "f" * 64


@dataclass(frozen=True, slots=True)
class PRCBC5P3Prepared:
    fixture: PRCBC5P3QualificationFixture


@dataclass(frozen=True, slots=True)
class PRCBC5P4Prepared:
    scope_snapshot_id: str
    expected: P4AssessmentRevision


@dataclass(frozen=True, slots=True)
class PRCBC5P5Prepared:
    selection_snapshot_id: str
    expected: P5AssessmentRevision


@dataclass(frozen=True, slots=True)
class PRCBC5P6Prepared:
    seed: PRCBC5P6ResolverSeed
    forecast_request: P6ForecastRequestBinding
    counterfactual_request: P6CounterfactualRequestBinding
    expected_forecast: P6ForecastRevision
    expected_counterfactual: P6CounterfactualRevision


def prepare_prcb_c5_p3(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
) -> PRCBC5P3Prepared:
    seed_prcb_c5_p3_upstream(rows)
    fixture = build_prcb_c5_p3_fixture()
    repository = P3PersistenceRepository(
        rows,
        object_store=object_store,
    )
    repository.register_component(
        segment=fixture.segment,
        validation=fixture.validation,
        training=fixture.training,
        model_build=fixture.model_build,
        surface_build=fixture.surface_build,
        model_object=fixture.model_object,
        surface_object=fixture.surface_object,
    )
    repository.register_twin(
        fixture.twin,
        components=(fixture.component,),
    )
    return PRCBC5P3Prepared(fixture=fixture)


def prepare_prcb_c5_p4(
    rows: CanonicalRowRepository,
) -> PRCBC5P4Prepared:
    seed_prcb_c5_p4_p5_upstream(rows)
    subject = build_prcb_c5_p4_subject()
    fact = M8WorldFactRef(
        ref_id="world:action:prcb-c5-worker",
        world_layer="ACTION_WORLD",
        episode_id=P45_EPISODE,
        stage_id=None,
        source_hash=HASH,
        knowledge_time_utc="2026-09-20T11:30:00Z",
    )
    machine = M8EvidenceRef(
        evidence_id="machine:action-timing:prcb-c5-worker",
        origin="MACHINE",
        evidence_family="ACTION_TIMING",
        evidence_set_id=P45_EVIDENCE,
        episode_id=P45_EPISODE,
        world_refs=(fact.ref_id,),
        source_refs=("metric:timing:prcb-c5-worker",),
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
    products = P4P5PersistenceRepository(rows)
    products.register_p4_subject(subject)
    snapshot_id = P4P5ComputeInputRepository(rows).register_p4_scope(scope)
    expected = build_p4_assessment_revision(
        subject,
        evidence=materialize_p4_human_machine_evidence(subject, scope),
        annotations=(),
        p3_claim=P3ClaimEnvelope(
            claim_level="P3_EVIDENCE_UNAVAILABLE",
            validity_status="UNAVAILABLE",
            as_of_utc=P45_AS_OF,
            uncertainty_lower=None,
            uncertainty_upper=None,
        ),
        confidence=0.9,
        created_at_utc=P45_AS_OF,
        approval_state="DRAFT",
        supersedes_id=None,
    )
    return PRCBC5P4Prepared(
        scope_snapshot_id=snapshot_id,
        expected=expected,
    )


def prepare_prcb_c5_p5(
    rows: CanonicalRowRepository,
    *,
    p4_revision_id: str,
) -> PRCBC5P5Prepared:
    p4 = P4P5PersistenceRepository(rows).exact_p4_revision(p4_revision_id)
    subject = build_prcb_c5_p4_subject()
    if p4.subject_key != subject.subject_key:
        raise RuntimeError("PRCB_C5_P5_P4_SUBJECT_MISMATCH")
    participant = P5ParticipantBinding(
        subject_key=subject.subject_key,
        role_code="FLIGHT_LEAD",
        aircraft_id=P45_AIRCRAFT,
        twin_revision_id=P45_TWIN,
        p4_revision_id=p4_revision_id,
    )
    composition = build_p5_composition_snapshot(
        session_id=P45_SESSION,
        mission_episode_id=P45_EPISODE,
        team_id=P45_TEAM,
        participants=(participant,),
        world_snapshot_refs=("world:mission:prcb-c5-worker",),
        scenario_context_artifact_id=None,
        role_model_context_artifact_id=P45_ROLE_ARTIFACT,
        assessment_spec_id="P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        as_of_utc=P5_AS_OF,
    )
    objective_refs = (
        "objective:prcb-c5:2",
        "objective:prcb-c5:1",
    )
    snapshot_id = P4P5ComputeInputRepository(rows).register_p5_selection(
        composition,
        objective_result_refs=objective_refs,
        evidence_set_id=P45_EVIDENCE,
        as_of_utc=P5_AS_OF,
    )
    evidence = materialize_p5_team_mission_evidence(
        composition,
        p4_revisions=(p4,),
        evidence_set_id=P45_EVIDENCE,
        objective_result_refs=objective_refs,
        as_of_utc=P5_AS_OF,
    )
    expected = build_p5_assessment_revision(
        composition,
        evidence=evidence,
        aggregation=build_p5_aggregation(evidence),
        confidence=0.8,
        created_at_utc=P5_AS_OF,
        approval_state="DRAFT",
        supersedes=None,
    )
    return PRCBC5P5Prepared(
        selection_snapshot_id=snapshot_id,
        expected=expected,
    )


def prepare_prcb_c5_p6(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
) -> PRCBC5P6Prepared:
    seed = seed_prcb_c5_p6_model_resolver_case(
        rows,
        object_store,
        seed_p3_upstream=False,
    )
    source = build_prcb_c5_p3_fixture()
    snapshot = build_p6_input_snapshot(
        factual_sources=(
            P6FactualSourceRevision(
                phase="P4",
                revision_id=P6_P4_SOURCE,
                publication_status="PUBLISHED",
                knowledge_time_utc="2026-09-10T09:00:00Z",
            ),
        ),
        scenario_context_refs=(
            P6ContextRef(
                context_ref_id=P6_CONTEXT,
                status="ACTIVE",
                knowledge_time_utc="2026-09-10T09:00:00Z",
            ),
        ),
        target_scope="SUBJECT",
        subject_or_composition_ref=source.twin.aircraft_id,
        forecast_origin_utc="2026-09-10T13:00:00Z",
        as_of_utc="2026-09-10T13:00:00Z",
    )
    profile = P6ForecastExecutionProfile.from_canonical()
    forecast_request = build_p6_forecast_request_binding(
        input_snapshot=snapshot,
        forecast_spec_id="P6_FORECAST:P3_CAPABILITY_NEXT_SESSION",
        forecast_spec_version="1.0.0",
        target_code=profile.target_code,
        horizon_spec={
            "type": profile.horizon_type,
            "steps": profile.horizon_steps,
            "target_session_order": 5,
        },
        capability_model_id=seed.build.model.capability_model_id,
        model_profile_id=profile.profile_id,
        model_profile_version=profile.profile_version,
        training_dataset_snapshot_id=seed.build.model.training_dataset_snapshot_id,
        validation_dataset_snapshot_id=seed.build.model.validation_dataset_snapshot_id,
        assumption_profile_id="P6_ASSUMPTION:TRAINING_EVALUATION",
        assumption_profile_version="1.0.0",
    )
    counterfactual_request = build_p6_counterfactual_request_binding(
        input_snapshot=snapshot,
        base_product_refs=(P6_P4_SOURCE,),
        scenario_definition_id=P6_CONTEXT,
        interventions={
            "training_focus": {
                "type": "TRAINING_FOCUS",
                "value": "DEBRIEF_REPEAT",
            }
        },
        held_fixed_assumptions={"configuration": "UNCHANGED"},
        model_refs=(seed.build.model.capability_model_id,),
        applicability_profile_ref=profile.applicability_profile_ref,
    )
    repository = P6PersistenceRepository(rows, object_store=object_store)
    repository.register_input(snapshot)
    repository.register_forecast_request(forecast_request)
    repository.register_counterfactual_request(counterfactual_request)
    expected_forecast = execute_p6_forecast(
        request=forecast_request,
        input_snapshot=snapshot,
        model_build=seed.build,
        managed_object=seed.managed,
        published_at_utc=P6_FORECAST_PUBLISHED,
    )
    expected_counterfactual = execute_p6_counterfactual(
        request=counterfactual_request,
        input_snapshot=snapshot,
        models=(seed.build.model,),
        created_at_utc=P6_COUNTERFACTUAL_CREATED,
    )
    return PRCBC5P6Prepared(
        seed=seed,
        forecast_request=forecast_request,
        counterfactual_request=counterfactual_request,
        expected_forecast=expected_forecast,
        expected_counterfactual=expected_counterfactual,
    )
