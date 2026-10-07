"""Deterministic PRCB C5 P3 qualification seed using product domain APIs."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_capability import (
    P3AircraftTwinRevision,
    P3CapabilityEstimate,
    P3CapabilityModelBuild,
    P3CapabilitySurfaceBuild,
    P3ModelExecutionProfile,
    P3TrainingDatasetSnapshot,
    P3TwinComponentBinding,
    build_capability_surface,
    evaluate_twin_capability_estimate,
    execute_capability_model,
    materialize_training_dataset,
    publish_aircraft_twin_revision,
)
from tpaa_longitudinal import (
    P3AdjustedEstimateInput,
    P3AuthorityPolicy,
    P3LifecycleEventInput,
    P3LifecycleSegment,
    P3ManagedObject,
    P3ModelValidationSnapshot,
    build_p3_lifecycle_segment,
    build_p3_validation_snapshot,
)
from tpaa_storage.canonical_rows import CanonicalRowRepository

AIRCRAFT_MODEL = "96100000-0000-4000-8000-000000000001"
AIRCRAFT = "96100000-0000-4000-8000-000000000002"
SESSION = "96100000-0000-4000-8000-000000000003"
EPISODE = "96100000-0000-4000-8000-000000000004"
ENTITY = "96100000-0000-4000-8000-000000000005"
CONTEXT = "96100000-0000-4000-8000-000000000006"
METRIC_DEFINITION = "96100000-0000-4000-8000-000000000007"
METRIC_INSTANCE = "96100000-0000-4000-8000-000000000008"
EVIDENCE = "96100000-0000-4000-8000-000000000009"
P1_JOB = "96100000-0000-4000-8000-00000000000a"
P2_JOB = "96100000-0000-4000-8000-00000000000b"
P1_RELEASE = "96100000-0000-4000-8000-00000000000c"
P2_RELEASE = "96100000-0000-4000-8000-00000000000d"
ATTRIBUTION_RUN = "96100000-0000-4000-8000-00000000000e"
REFERENCE = "96100000-0000-4000-8000-00000000000f"
SEGMENT = "96100000-0000-4000-8000-000000000010"
TRAINING = "96100000-0000-4000-8000-000000000011"
VALIDATION = "96100000-0000-4000-8000-000000000012"
MODEL_OBJECT = "96100000-0000-4000-8000-000000000013"
SURFACE_OBJECT = "96100000-0000-4000-8000-000000000014"
CONFIG = "96100000-0000-4000-8000-000000000015"
TWIN_EVIDENCE = "96100000-0000-4000-8000-000000000016"
LIFECYCLE = "96100000-0000-4000-8000-000000000017"
LIFECYCLE_SOURCE = "96100000-0000-4000-8000-000000000018"
AIRCRAFT_INSTANCE = "96100000-0000-4000-8000-000000000019"
RUN_REQUEST_HASH = "1" * 64
MODEL_ARTIFACT_HASH = "2" * 64
COMPARISON_KEY_HASH = "3" * 64
CONFIG_HASH = "4" * 64


@dataclass(frozen=True, slots=True)
class PRCBC5P3QualificationFixture:
    segment: P3LifecycleSegment
    validation: P3ModelValidationSnapshot
    training: P3TrainingDatasetSnapshot
    model_build: P3CapabilityModelBuild
    surface_build: P3CapabilitySurfaceBuild
    model_object: P3ManagedObject
    surface_object: P3ManagedObject
    component: P3TwinComponentBinding
    twin: P3AircraftTwinRevision
    estimate: P3CapabilityEstimate
    selected_p2_estimate_id: str
    selected_source_observation_id: str


def _p2_input(index: int) -> P3AdjustedEstimateInput:
    digit = f"{index:x}"
    estimate_id = (
        f"{digit * 8}-{digit * 4}-4{digit * 3}-"
        f"8{digit * 3}-{digit * 12}"
    )
    observation_id = (
        f"{digit * 8}-{digit * 4}-4{digit * 3}-"
        f"9{digit * 3}-{digit * 12}"
    )
    configuration_id = (
        f"{digit * 8}-{digit * 4}-4{digit * 3}-"
        f"a{digit * 3}-{digit * 12}"
    )
    session_id = (
        f"{digit * 8}-{digit * 4}-4{digit * 3}-"
        f"b{digit * 3}-{digit * 12}"
    )
    episode_id = (
        f"{digit * 8}-{digit * 4}-4{digit * 3}-"
        f"c{digit * 3}-{digit * 12}"
    )
    value = 9.0 + index
    return P3AdjustedEstimateInput(
        estimate_id=estimate_id,
        p2_release_id=P2_RELEASE,
        p2_release_status="PUBLISHED",
        source_observation_id=observation_id,
        source_release_id=P1_RELEASE,
        source_release_status="PUBLISHED",
        attribution_run_id=ATTRIBUTION_RUN,
        aircraft_id=AIRCRAFT,
        aircraft_model_id=AIRCRAFT_MODEL,
        configuration_snapshot_id=configuration_id,
        configuration_snapshot_hash=CONFIG_HASH,
        configuration_key=f"AIRCRAFT_CONFIG_SHA256:{CONFIG_HASH}",
        session_id=session_id,
        episode_id=episode_id,
        session_occurred_at_utc=f"2026-09-{index:02d}T00:00:00Z",
        session_order_scope_id="96100000-0000-4000-8000-000000000020",
        session_order_scope_status="ACTIVE",
        session_order_assignment_current=True,
        session_order=index,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        metric_semantic_id="metric.test.energy",
        metric_semantic_version=1,
        comparison_key_hash=COMPARISON_KEY_HASH,
        reference_condition_id=REFERENCE,
        adjusted_value=value,
        unit="1",
        uncertainty_lower=value - 0.5,
        uncertainty_upper=value + 0.5,
        factor_effects={},
        claim_level="ASSOCIATION_ONLY",
        status="IDENTIFIABLE",
        evidence_set_id=EVIDENCE,
        knowledge_time_utc=f"2026-09-{index:02d}T12:00:00Z",
        estimate_time=f"2026-09-{index:02d}T12:00:00Z",
        created_at=f"2026-09-{index:02d}T12:00:00Z",
    )


def build_prcb_c5_p3_fixture() -> PRCBC5P3QualificationFixture:
    policy = P3AuthorityPolicy.from_canonical()
    profile = P3ModelExecutionProfile.from_canonical()
    rows = tuple(_p2_input(index) for index in range(1, 5))
    segment = build_p3_lifecycle_segment(
        segment_snapshot_id=SEGMENT,
        estimates=rows,
        lifecycle_events=(
            P3LifecycleEventInput(
                lifecycle_event_id=LIFECYCLE,
                aircraft_id=AIRCRAFT,
                event_type="BASELINE_IMPORT",
                start_occurred_at_utc="2026-08-01T00:00:00Z",
                end_occurred_at_utc="2026-08-01T01:00:00Z",
                source_ref=LIFECYCLE_SOURCE,
            ),
        ),
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    validation = build_p3_validation_snapshot(
        validation_snapshot_id=VALIDATION,
        training_dataset_snapshot_id=TRAINING,
        segment=segment,
        estimates=rows,
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    training = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=rows,
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    model_build = execute_capability_model(
        training=training,
        validation=validation,
        segment=segment,
        estimates=rows,
        trained_at_utc="2026-09-10T02:00:00Z",
        policy=policy,
        profile=profile,
    )
    surface_build = build_capability_surface(
        model_build=model_build,
        created_at_utc="2026-09-10T03:00:00Z",
        profile=profile,
    )
    model_object = P3ManagedObject(
        object_ref_id=MODEL_OBJECT,
        managed_uri=model_build.model.model_artifact_uri,
        artifact_sha256=model_build.model.model_artifact_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    surface_object = P3ManagedObject(
        object_ref_id=SURFACE_OBJECT,
        managed_uri=surface_build.surface.dataset_uri,
        artifact_sha256=surface_build.surface.dataset_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    component = P3TwinComponentBinding(
        model_build=model_build,
        surface_build=surface_build,
        model_object_ref_id=MODEL_OBJECT,
        surface_object_ref_id=SURFACE_OBJECT,
    )
    twin = publish_aircraft_twin_revision(
        aircraft_id=AIRCRAFT,
        components=(component,),
        config_snapshot_id=CONFIG,
        evidence_snapshot_id=TWIN_EVIDENCE,
        valid_from_utc="2026-09-01T00:00:00Z",
        valid_to_utc=None,
        as_of_data_time_utc="2026-09-10T00:00:00Z",
        published_at_utc="2026-09-10T03:30:00Z",
        profile=profile,
    )
    estimate = evaluate_twin_capability_estimate(
        twin=twin,
        components=(component,),
        capability_type="KINEMATIC_ENERGY_CONTROL",
        condition_point={
            "session_order": 4,
            "reference_condition_id": REFERENCE,
        },
        as_of_time_utc="2026-09-10T00:00:00Z",
        created_at_utc="2026-09-10T04:00:00Z",
        profile=profile,
        policy=policy,
    )
    selected = rows[-1]
    return PRCBC5P3QualificationFixture(
        segment=segment,
        validation=validation,
        training=training,
        model_build=model_build,
        surface_build=surface_build,
        model_object=model_object,
        surface_object=surface_object,
        component=component,
        twin=twin,
        estimate=estimate,
        selected_p2_estimate_id=selected.estimate_id,
        selected_source_observation_id=selected.source_observation_id,
    )


def seed_prcb_c5_p3_upstream(rows: CanonicalRowRepository) -> None:
    fixture = build_prcb_c5_p3_fixture()
    selected = _p2_input(4)
    rows.insert(
        "master.aircraft_model",
        {
            "aircraft_model_id": AIRCRAFT_MODEL,
            "type_code": "PRCB-C5-P3",
            "model_name": "PRCB C5 P3 Qualification Model",
        },
    )
    rows.insert(
        "master.aircraft",
        {
            "aircraft_id": AIRCRAFT,
            "aircraft_model_id": AIRCRAFT_MODEL,
            "internal_code": "PRCB-C5-P3-AIRCRAFT",
            "master_data_status": "ACTIVE",
        },
    )
    rows.insert(
        "registry.training_session",
        {
            "session_id": SESSION,
            "session_code": "PRCB-C5-P3",
            "session_type": "SIM",
            "start_session_time_us": 0,
            "end_session_time_us": 1_000_000,
            "training_type_set": ("QUALIFICATION",),
            "data_status": "READY",
            "source_count": 1,
            "schema_version": "1.8.0",
        },
        field_kinds={"training_type_set": "text_array"},
    )
    rows.insert(
        "master.entity",
        {
            "entity_id": ENTITY,
            "session_id": SESSION,
            "entity_type": "AIRCRAFT",
            "alias": "PRCB-C5-P3-SUBJECT",
        },
    )
    rows.insert(
        "context.evaluation_context",
        {
            "context_id": CONTEXT,
            "session_id": SESSION,
            "context_version": "PRCB-C5-P3",
            "revision_no": 1,
            "rule_set_version": "1.0.0",
            "metric_profile_version": "1.0.0",
            "status": "ACTIVE",
        },
    )
    rows.insert(
        "episode.training_episode",
        {
            "episode_id": EPISODE,
            "session_id": SESSION,
            "episode_type": "MISSION",
            "context_id": CONTEXT,
            "start_session_time_us": 0,
            "end_session_time_us": 1_000_000,
            "subject_scope": "AIRCRAFT",
            "primary_aircraft_id": AIRCRAFT,
            "world_capability_code": "P3",
            "episode_status": "COMPLETE",
            "detector_version": "PRCB-C5",
            "coverage": 1.0,
            "confidence": 1.0,
        },
    )
    for job_id, job_key in (
        (P1_JOB, "PRCB-C5-P3-P1"),
        (P2_JOB, "PRCB-C5-P3-P2"),
    ):
        rows.insert(
            "registry.compute_job",
            {
                "job_id": job_id,
                "job_type": "PRCB_C5_P3_QUALIFICATION",
                "session_id": SESSION,
                "episode_id": EPISODE,
                "job_key": job_key,
                "status": "SUCCEEDED",
                "component_version": "PRCB-1.0",
                "input_hash": "5" * 64,
                "progress": 1.0,
                "reason_codes": (),
            },
            field_kinds={"reason_codes": "text_array"},
        )
    for release_id, job_id, release_no in (
        (P1_RELEASE, P1_JOB, 1),
        (P2_RELEASE, P2_JOB, 2),
    ):
        rows.insert(
            "registry.analysis_release",
            {
                "release_id": release_id,
                "scope_type": "SESSION",
                "scope_key": f"SESSION:{SESSION}",
                "session_id": SESSION,
                "release_no": release_no,
                "compute_job_id": job_id,
                "catalog_version": "P1-METRIC-CATALOG-1.0",
                "catalog_hash": "6" * 64,
                "context_binding_hash": "7" * 64,
                "status": "PUBLISHED",
                "manifest_hash": "8" * 64,
                "created_at": "2026-09-04T10:00:00Z",
                "published_at": "2026-09-04T10:01:00Z",
            },
        )
    rows.insert(
        "metric.evidence_set",
        {
            "evidence_set_id": EVIDENCE,
            "release_id": P1_RELEASE,
            "session_id": SESSION,
            "episode_id": EPISODE,
            "series_locator": [],
            "algorithm_versions": {"piqb_b2_p3": "1.0.0"},
        },
        field_kinds={
            "series_locator": "json",
            "algorithm_versions": "json",
        },
    )
    rows.insert(
        "metric.metric_definition",
        {
            "metric_definition_id": METRIC_DEFINITION,
            "metric_code": "PRCB_C5_P3_METRIC",
            "version": "1.0.0",
            "catalog_version": "P1-METRIC-CATALOG-1.0",
            "catalog_hash": "6" * 64,
            "metric_semantic_id": "metric.test.energy",
            "metric_semantic_version": 1,
            "name": "PRCB C5 P3 metric",
            "subject_type": "AIRCRAFT",
            "observation_lane": "AIRCRAFT_CAP_L1_OBSERVATION",
            "publication_route": "CAPABILITY_OBSERVATION",
            "category": "QUALIFICATION",
            "calculation_layer": "P1",
            "capability_level": "CAP_L1_OBSERVED",
            "capability_dimension": "KINEMATIC_ENERGY_CONTROL",
            "required_world_products": [],
            "scope": "EPISODE",
            "spec_uri": "tpaa-object://piqb-b2/p3-metric-spec.json",
            "spec_hash": "9" * 64,
            "definition_hash": "a" * 64,
            "plugin_name": "PRCB_C5_P3",
            "plugin_version": "1.0.0",
            "status": "ACTIVE",
        },
        field_kinds={"required_world_products": "json"},
    )
    rows.insert(
        "metric.metric_instance",
        {
            "metric_instance_id": METRIC_INSTANCE,
            "release_id": P1_RELEASE,
            "metric_definition_id": METRIC_DEFINITION,
            "session_id": SESSION,
            "metric_scope": "EPISODE",
            "episode_id": EPISODE,
            "subject_entity_id": ENTITY,
            "value_numeric": 14.0,
            "unit": "1",
            "status": "VALID",
            "reason_codes": (),
            "coverage": 1.0,
            "confidence": 1.0,
            "confidence_components": {},
            "evidence_set_id": EVIDENCE,
            "context_id": CONTEXT,
            "world_product_versions": {},
            "compute_version": "PRCB-C5",
            "input_hash": "b" * 64,
        },
        field_kinds={
            "reason_codes": "text_array",
            "confidence_components": "json",
            "world_product_versions": "json",
        },
    )
    rows.insert(
        "metric.capability_observation",
        {
            "observation_id": selected.source_observation_id,
            "release_id": P1_RELEASE,
            "session_id": SESSION,
            "episode_id": EPISODE,
            "aircraft_id": AIRCRAFT,
            "aircraft_instance_id": AIRCRAFT_INSTANCE,
            "subject_entity_id": ENTITY,
            "aircraft_model_id": AIRCRAFT_MODEL,
            "context_id": CONTEXT,
            "capability_dimension": "KINEMATIC_ENERGY_CONTROL",
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "capability_level": "CAP_L1_OBSERVED",
            "observed_metric_instance_id": METRIC_INSTANCE,
            "observed_value_numeric": 14.0,
            "unit": "1",
            "observation_start_session_time_us": 0,
            "observation_end_session_time_us": 1_000_000,
            "context_tags": {"qualification": "PRCB_C5_P3"},
            "evidence_set_id": EVIDENCE,
            "coverage": 1.0,
            "confidence": 1.0,
            "eligibility_status": "ELIGIBLE",
            "comparison_key_hash": COMPARISON_KEY_HASH,
            "observation_schema_version": "1.8.0",
            "created_at": "2026-09-04T09:00:00Z",
        },
        field_kinds={"context_tags": "json"},
    )
    rows.insert(
        "assessment.attribution_run",
        {
            "attribution_run_id": ATTRIBUTION_RUN,
            "attribution_spec_id": "P2_ATTRIBUTION:REFERENCE_CONDITION",
            "attribution_spec_version": "1.0.0",
            "model_plugin": "REFERENCE_CONDITION_ASSOCIATION",
            "model_plugin_version": "1.0.0",
            "training_dataset_snapshot_id": (
                "96100000-0000-4000-8000-000000000021"
            ),
            "reference_condition_id": REFERENCE,
            "status": "IDENTIFIABLE",
            "diagnostics": {
                "run_request_hash": RUN_REQUEST_HASH,
                "reason_codes": [],
            },
            "model_artifact_uri": None,
            "model_artifact_hash": MODEL_ARTIFACT_HASH,
            "started_at": "2026-09-04T11:00:00Z",
            "completed_at": "2026-09-04T11:01:00Z",
            "created_by": "PRCB-C5",
        },
        field_kinds={"diagnostics": "json"},
    )
    rows.insert(
        "assessment.attribution_run_request_binding",
        {
            "attribution_run_id": ATTRIBUTION_RUN,
            "run_request_hash": RUN_REQUEST_HASH,
            "compute_job_id": P2_JOB,
        },
    )
    rows.insert(
        "capability.adjusted_capability_estimate",
        {
            "estimate_id": selected.estimate_id,
            "source_observation_id": selected.source_observation_id,
            "attribution_run_id": ATTRIBUTION_RUN,
            "aircraft_id": AIRCRAFT,
            "capability_type": selected.capability_type,
            "reference_condition_id": REFERENCE,
            "adjusted_value": selected.adjusted_value,
            "unit": selected.unit,
            "uncertainty_lower": selected.uncertainty_lower,
            "uncertainty_upper": selected.uncertainty_upper,
            "residual": 0.0,
            "factor_effects": {},
            "claim_level": selected.claim_level,
            "status": selected.status,
            "evidence_set_id": EVIDENCE,
            "estimate_time": selected.estimate_time,
            "created_at": selected.created_at,
        },
        field_kinds={"factor_effects": "json"},
    )
    rows.insert(
        "capability.adjusted_capability_estimate_revision",
        {
            "estimate_id": selected.estimate_id,
            "p2_release_id": P2_RELEASE,
            "reason_codes": (),
        },
        field_kinds={"reason_codes": "text_array"},
    )
    if fixture.selected_p2_estimate_id != selected.estimate_id:
        raise RuntimeError("PRCB C5 P3 qualification seed identity drift")
