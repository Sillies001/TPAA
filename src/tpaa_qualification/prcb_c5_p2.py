"""PRCB C5 deterministic P2 qualification input bound to a real P1 observation."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import P2PersistenceRepository
from tpaa_assessment import (
    P2ArtifactBinding,
    P2AttributionSpec,
    P2AuthorityPolicy,
    P2CohortSnapshot,
    P2ExecutionProfile,
    P2ReferenceCondition,
    build_p2_input_bundle,
    materialize_factor_feature_set,
)
from tpaa_storage.canonical_rows import CanonicalRowRepository

FEATURE_ARTIFACT = "97000000-0000-4000-8000-000000000012"
REFERENCE_ARTIFACT = "97000000-0000-4000-8000-000000000013"
ATTRIBUTION_ARTIFACT = "97000000-0000-4000-8000-000000000014"
FEATURE_OBJECT = "97000000-0000-4000-8000-000000000015"
REFERENCE_OBJECT = "97000000-0000-4000-8000-000000000016"
ATTRIBUTION_OBJECT = "97000000-0000-4000-8000-000000000017"
COHORT = "97000000-0000-4000-8000-000000000019"
QUALIFICATION_AS_OF_UTC = "2026-12-31T23:58:00Z"
QUALIFICATION_EXECUTION_TIME_UTC = "2026-12-31T23:59:00Z"


@dataclass(frozen=True, slots=True)
class PRCBC5P2QualificationSeed:
    dataset_snapshot_id: str
    target_observation_id: str
    as_of_utc: str
    execution_time_utc: str


def _binding(
    *,
    artifact_id: str,
    object_id: str,
    kind: str,
    logical_key: str,
    schema: str,
    digest: str,
) -> P2ArtifactBinding:
    return P2ArtifactBinding(
        context_artifact_id=artifact_id,
        object_ref_id=object_id,
        artifact_kind=kind,
        logical_key=logical_key,
        artifact_version="1.0.0",
        schema_version=schema,
        artifact_sha256=digest,
        status="ACTIVE",
        sealed=True,
    )


def _ensure_artifact(
    rows: CanonicalRowRepository,
    binding: P2ArtifactBinding,
) -> None:
    current = rows.one(
        "registry.context_artifact",
        where={"context_artifact_id": binding.context_artifact_id},
        columns=("context_artifact_id",),
    )
    if current is not None:
        raise RuntimeError(
            "PRCB_C5_P2_SEED_CONFLICT:"
            + binding.context_artifact_id
        )
    rows.insert(
        "registry.object_reference",
        {
            "object_ref_id": binding.object_ref_id,
            "managed_uri": (
                "tpaa-object://prcb-c5/p2-authority/"
                + binding.object_ref_id
                + ".json"
            ),
            "media_type": "application/json",
            "size_bytes": 2,
            "artifact_sha256": binding.artifact_sha256,
            "logical_content_hash": binding.artifact_sha256,
            "storage_backend": "LOCAL_OBJECT_STORE",
            "sealed": True,
            "gc_state": "ACTIVE",
            "gc_state_version": 0,
        },
    )
    rows.insert(
        "registry.context_artifact",
        {
            "context_artifact_id": binding.context_artifact_id,
            "artifact_kind": binding.artifact_kind,
            "logical_key": binding.logical_key,
            "artifact_version": binding.artifact_version,
            "object_ref_id": binding.object_ref_id,
            "artifact_sha256": binding.artifact_sha256,
            "schema_version": binding.schema_version,
            "status": binding.status,
        },
    )


def prepare_prcb_c5_p2_workspace(
    rows: CanonicalRowRepository,
    *,
    observation_id: str,
) -> PRCBC5P2QualificationSeed:
    policy = P2AuthorityPolicy.from_canonical()
    profile = P2ExecutionProfile.from_canonical()
    repository = P2PersistenceRepository(rows)
    target = repository.exact_source_observation(observation_id)
    if target.eligibility_status != policy.required_eligibility_status:
        raise RuntimeError("PRCB_C5_P2_TARGET_NOT_ELIGIBLE")

    feature_spec = _binding(
        artifact_id=FEATURE_ARTIFACT,
        object_id=FEATURE_OBJECT,
        kind=policy.feature_artifact_kind,
        logical_key=f"{policy.feature_logical_key_prefix}PRCB-C5",
        schema=policy.feature_schema_version,
        digest="4" * 64,
    )
    reference_binding = _binding(
        artifact_id=REFERENCE_ARTIFACT,
        object_id=REFERENCE_OBJECT,
        kind=policy.reference_artifact_kind,
        logical_key=f"{policy.reference_logical_key_prefix}PRCB-C5",
        schema=policy.reference_schema_version,
        digest="5" * 64,
    )
    attribution_binding = _binding(
        artifact_id=ATTRIBUTION_ARTIFACT,
        object_id=ATTRIBUTION_OBJECT,
        kind=policy.attribution_artifact_kind,
        logical_key=profile.attribution_spec_id,
        schema=policy.attribution_schema_version,
        digest="6" * 64,
    )
    for binding in (feature_spec, reference_binding, attribution_binding):
        _ensure_artifact(rows, binding)

    cohort = P2CohortSnapshot(
        dataset_snapshot_id=COHORT,
        snapshot_type=policy.cohort_snapshot_type,
        data_hash="7" * 64,
        schema_version="1.9.0",
        frozen=True,
        cohort_spec_id="P2_COHORT_PRCB_C5_V1",
        cohort_spec_version="1.0.0",
        comparability_dimensions=(
            ("capability_type", target.capability_type),
            ("metric_semantic_id", target.metric_semantic_id),
            ("metric_semantic_version", target.metric_semantic_version),
            ("unit", target.unit),
            ("aircraft_model_id", target.aircraft_model_id),
            ("comparison_key_hash", target.comparison_key_hash),
        ),
        knowledge_cutoff_utc=target.knowledge_time_utc,
        raw_record_count=0,
        observation_count=0,
        independent_subject_count=0,
        effective_evidence_count=0.0,
        observation_ids=(),
        episode_ids=(),
        subject_ids=(),
    )
    bundle = build_p2_input_bundle(
        target=target,
        feature_spec=feature_spec,
        reference_condition=P2ReferenceCondition(
            reference_condition_id=REFERENCE_ARTIFACT,
            binding=reference_binding,
        ),
        cohort=cohort,
        attribution_spec=P2AttributionSpec(
            attribution_spec_id=profile.attribution_spec_id,
            attribution_spec_version=profile.attribution_spec_version,
            model_plugin=profile.model_plugin,
            model_plugin_version=profile.model_plugin_version,
            uncertainty_method=profile.uncertainty_method,
            uncertainty_level=profile.uncertainty_level,
            binding=attribution_binding,
        ),
        as_of_utc=QUALIFICATION_AS_OF_UTC,
    )
    feature = materialize_factor_feature_set(
        source=target,
        feature_spec=feature_spec,
        factor_order=("x",),
        factor_values={"x": 3.0},
        world_refs=(),
        confidence=target.confidence,
        created_at=QUALIFICATION_AS_OF_UTC,
        reference_condition_id=REFERENCE_ARTIFACT,
        profile=profile,
    )
    repository.register_workspace_inputs(
        bundle,
        feature,
        cohort_rows=(),
        reference_factor_values={"x": 1.5},
    )
    rebuilt = repository.exact_compute_input(COHORT)
    if (
        rebuilt.input_bundle != bundle
        or rebuilt.target_feature_set != feature
        or rebuilt.cohort_rows != ()
        or rebuilt.reference_factor_values != {"x": 1.5}
    ):
        raise RuntimeError("PRCB_C5_P2_COMPUTE_INPUT_REBUILD_FAILED")
    return PRCBC5P2QualificationSeed(
        dataset_snapshot_id=COHORT,
        target_observation_id=target.observation_id,
        as_of_utc=QUALIFICATION_AS_OF_UTC,
        execution_time_utc=QUALIFICATION_EXECUTION_TIME_UTC,
    )
