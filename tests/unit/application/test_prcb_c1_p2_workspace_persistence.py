from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace

from tpaa_application.p2_persistence import P2PersistenceRepository
from tpaa_assessment import (
    P1ObservationInput,
    P2AdjustedCapabilityEstimate,
    P2ArtifactBinding,
    P2AttributionRunProduct,
    P2AttributionSpec,
    P2AuthorityPolicy,
    P2CohortSnapshot,
    P2ExecutionProfile,
    P2FactorFeatureSet,
    P2ReferenceCondition,
    build_p2_input_bundle,
)
from tpaa_storage.canonical_rows import SQLiteCanonicalRowRepository

SOURCE_RELEASE = "95000000-0000-4000-8000-000000000001"
P2_RELEASE = "95000000-0000-4000-8000-000000000002"
OBSERVATION = "95000000-0000-4000-8000-000000000003"
EPISODE = "95000000-0000-4000-8000-000000000004"
SUBJECT = "95000000-0000-4000-8000-000000000005"
AIRCRAFT = "95000000-0000-4000-8000-000000000006"
AIRCRAFT_MODEL = "95000000-0000-4000-8000-000000000007"
CONTEXT = "95000000-0000-4000-8000-000000000008"
EVIDENCE = "95000000-0000-4000-8000-000000000009"
METRIC_INSTANCE = "95000000-0000-4000-8000-000000000010"
METRIC_DEFINITION = "95000000-0000-4000-8000-000000000011"
FEATURE_ARTIFACT = "95000000-0000-4000-8000-000000000012"
REFERENCE_ARTIFACT = "95000000-0000-4000-8000-000000000013"
ATTRIBUTION_ARTIFACT = "95000000-0000-4000-8000-000000000014"
FEATURE_OBJECT = "95000000-0000-4000-8000-000000000015"
REFERENCE_OBJECT = "95000000-0000-4000-8000-000000000016"
ATTRIBUTION_OBJECT = "95000000-0000-4000-8000-000000000017"
FEATURE_SET = "95000000-0000-4000-8000-000000000018"
COHORT = "95000000-0000-4000-8000-000000000019"
RUN = "95000000-0000-4000-8000-000000000020"
ESTIMATE = "95000000-0000-4000-8000-000000000021"
KNOWLEDGE = "2026-10-01T00:00:00Z"
PUBLISHED = "2026-10-02T00:00:00Z"
AS_OF = "2026-10-03T00:00:00Z"


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE "registry.analysis_release" (
            release_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            manifest_hash TEXT NOT NULL,
            published_at TEXT NULL
        );
        CREATE TABLE "metric.metric_definition" (
            metric_definition_id TEXT PRIMARY KEY,
            metric_semantic_id TEXT NOT NULL,
            metric_semantic_version INTEGER NOT NULL
        );
        CREATE TABLE "metric.metric_instance" (
            metric_instance_id TEXT PRIMARY KEY,
            metric_definition_id TEXT NOT NULL
        );
        CREATE TABLE "metric.capability_observation" (
            observation_id TEXT PRIMARY KEY,
            release_id TEXT NOT NULL,
            episode_id TEXT NOT NULL,
            subject_entity_id TEXT NOT NULL,
            aircraft_id TEXT NOT NULL,
            aircraft_model_id TEXT NOT NULL,
            aircraft_configuration_snapshot_id TEXT NULL,
            context_id TEXT NOT NULL,
            capability_type TEXT NOT NULL,
            observed_metric_instance_id TEXT NOT NULL,
            observed_value_numeric REAL NULL,
            unit TEXT NOT NULL,
            evidence_set_id TEXT NOT NULL,
            coverage REAL NOT NULL,
            confidence REAL NOT NULL,
            eligibility_status TEXT NOT NULL,
            comparison_key_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE "registry.object_reference" (
            object_ref_id TEXT PRIMARY KEY,
            artifact_sha256 TEXT NOT NULL,
            sealed INTEGER NOT NULL,
            gc_state TEXT NOT NULL,
            deleted_at TEXT NULL
        );
        CREATE TABLE "registry.context_artifact" (
            context_artifact_id TEXT PRIMARY KEY,
            artifact_kind TEXT NOT NULL,
            logical_key TEXT NOT NULL,
            artifact_version TEXT NOT NULL,
            object_ref_id TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE "assessment.factor_feature_set" (
            factor_feature_set_id TEXT PRIMARY KEY,
            feature_spec_id TEXT NOT NULL,
            feature_spec_version TEXT NOT NULL,
            source_observation_id TEXT NOT NULL,
            reference_condition_id TEXT NULL,
            feature_values TEXT NOT NULL,
            missing_mask TEXT NOT NULL,
            world_refs TEXT NOT NULL,
            coverage REAL NOT NULL,
            confidence REAL NOT NULL,
            input_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE "registry.dataset_snapshot" (
            dataset_snapshot_id TEXT PRIMARY KEY,
            snapshot_type TEXT NOT NULL,
            query_or_manifest TEXT NOT NULL,
            input_refs TEXT NOT NULL,
            data_hash TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            frozen INTEGER NOT NULL
        );
        CREATE TABLE "assessment.attribution_run" (
            attribution_run_id TEXT PRIMARY KEY,
            attribution_spec_id TEXT NOT NULL,
            attribution_spec_version TEXT NOT NULL,
            model_plugin TEXT NOT NULL,
            model_plugin_version TEXT NOT NULL,
            training_dataset_snapshot_id TEXT NOT NULL,
            reference_condition_id TEXT NOT NULL,
            status TEXT NOT NULL,
            diagnostics TEXT NOT NULL,
            model_artifact_uri TEXT NULL,
            model_artifact_hash TEXT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            created_by TEXT NULL
        );
        CREATE TABLE "assessment.attribution_run_request_binding" (
            attribution_run_id TEXT PRIMARY KEY,
            run_request_hash TEXT NOT NULL,
            compute_job_id TEXT NULL
        );
        CREATE TABLE "capability.adjusted_capability_estimate" (
            estimate_id TEXT PRIMARY KEY,
            source_observation_id TEXT NOT NULL,
            attribution_run_id TEXT NOT NULL,
            aircraft_id TEXT NOT NULL,
            capability_type TEXT NOT NULL,
            reference_condition_id TEXT NOT NULL,
            adjusted_value REAL NULL,
            unit TEXT NOT NULL,
            uncertainty_lower REAL NULL,
            uncertainty_upper REAL NULL,
            residual REAL NULL,
            factor_effects TEXT NOT NULL,
            claim_level TEXT NOT NULL,
            status TEXT NOT NULL,
            evidence_set_id TEXT NOT NULL,
            estimate_time TEXT NOT NULL,
            created_at TEXT NOT NULL,
            supersedes_estimate_id TEXT NULL
        );
        CREATE TABLE "capability.adjusted_capability_estimate_revision" (
            estimate_id TEXT PRIMARY KEY,
            p2_release_id TEXT NOT NULL,
            reason_codes TEXT NOT NULL
        );
        """
    )
    return connection


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


def _seed_artifact(
    connection: sqlite3.Connection,
    binding: P2ArtifactBinding,
) -> None:
    connection.execute(
        'INSERT INTO "registry.object_reference" '
        "(object_ref_id, artifact_sha256, sealed, gc_state, deleted_at) "
        "VALUES (?, ?, 1, 'ACTIVE', NULL)",
        (binding.object_ref_id, binding.artifact_sha256),
    )
    connection.execute(
        'INSERT INTO "registry.context_artifact" '
        "(context_artifact_id, artifact_kind, logical_key, artifact_version, "
        "object_ref_id, artifact_sha256, schema_version, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            binding.context_artifact_id,
            binding.artifact_kind,
            binding.logical_key,
            binding.artifact_version,
            binding.object_ref_id,
            binding.artifact_sha256,
            binding.schema_version,
            binding.status,
        ),
    )


def _logical_hash(
    estimate: P2AdjustedCapabilityEstimate,
) -> str:
    payload = {
        "source_observation_id": estimate.source_observation_id,
        "source_release_id": estimate.source_release_id,
        "p2_release_id": estimate.p2_release_id,
        "attribution_run_id": estimate.attribution_run_id,
        "reference_condition_id": estimate.reference_condition_id,
        "status": estimate.status,
        "reason_codes": list(estimate.reason_codes),
        "claim_level": estimate.claim_level,
        "evidence_set_id": estimate.evidence_set_id,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def test_prcb_p2_workspace_rebuilds_from_durable_authority() -> None:
    connection = _connection()
    policy = P2AuthorityPolicy.from_canonical()
    profile = P2ExecutionProfile.from_canonical()

    connection.executemany(
        'INSERT INTO "registry.analysis_release" '
        "(release_id, status, manifest_hash, published_at) VALUES (?, ?, ?, ?)",
        (
            (SOURCE_RELEASE, "PUBLISHED", "1" * 64, PUBLISHED),
            (P2_RELEASE, "PUBLISHED", "2" * 64, PUBLISHED),
        ),
    )
    connection.execute(
        'INSERT INTO "metric.metric_definition" '
        "(metric_definition_id, metric_semantic_id, metric_semantic_version) "
        "VALUES (?, ?, 1)",
        (METRIC_DEFINITION, "metric.prcb.p2"),
    )
    connection.execute(
        'INSERT INTO "metric.metric_instance" '
        "(metric_instance_id, metric_definition_id) VALUES (?, ?)",
        (METRIC_INSTANCE, METRIC_DEFINITION),
    )
    connection.execute(
        'INSERT INTO "metric.capability_observation" '
        "(observation_id, release_id, episode_id, subject_entity_id, aircraft_id, "
        "aircraft_model_id, aircraft_configuration_snapshot_id, context_id, "
        "capability_type, observed_metric_instance_id, observed_value_numeric, "
        "unit, evidence_set_id, coverage, confidence, eligibility_status, "
        "comparison_key_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            OBSERVATION,
            SOURCE_RELEASE,
            EPISODE,
            SUBJECT,
            AIRCRAFT,
            AIRCRAFT_MODEL,
            CONTEXT,
            "KINEMATIC_ENERGY_CONTROL",
            METRIC_INSTANCE,
            17.0,
            "1",
            EVIDENCE,
            1.0,
            0.9,
            policy.required_eligibility_status,
            "3" * 64,
            KNOWLEDGE,
        ),
    )

    feature_spec = _binding(
        artifact_id=FEATURE_ARTIFACT,
        object_id=FEATURE_OBJECT,
        kind=policy.feature_artifact_kind,
        logical_key=f"{policy.feature_logical_key_prefix}PRCB",
        schema=policy.feature_schema_version,
        digest="4" * 64,
    )
    reference_binding = _binding(
        artifact_id=REFERENCE_ARTIFACT,
        object_id=REFERENCE_OBJECT,
        kind=policy.reference_artifact_kind,
        logical_key=f"{policy.reference_logical_key_prefix}PRCB",
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
        _seed_artifact(connection, binding)

    target = P1ObservationInput(
        observation_id=OBSERVATION,
        release_id=SOURCE_RELEASE,
        release_status="PUBLISHED",
        release_sealed=True,
        episode_id=EPISODE,
        subject_entity_id=SUBJECT,
        aircraft_id=AIRCRAFT,
        aircraft_model_id=AIRCRAFT_MODEL,
        aircraft_configuration_snapshot_id=None,
        context_id=CONTEXT,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        metric_semantic_id="metric.prcb.p2",
        metric_semantic_version=1,
        comparison_key_hash="3" * 64,
        evidence_set_id=EVIDENCE,
        observed_value=17.0,
        unit="1",
        coverage=1.0,
        confidence=0.9,
        eligibility_status=policy.required_eligibility_status,
        knowledge_time_utc=KNOWLEDGE,
    )
    cohort = P2CohortSnapshot(
        dataset_snapshot_id=COHORT,
        snapshot_type=policy.cohort_snapshot_type,
        data_hash="7" * 64,
        schema_version="1.9.0",
        frozen=True,
        cohort_spec_id="P2_COHORT_PRCB_V1",
        cohort_spec_version="1.0.0",
        comparability_dimensions=(
            ("capability_type", target.capability_type),
            ("metric_semantic_id", target.metric_semantic_id),
            ("metric_semantic_version", target.metric_semantic_version),
            ("unit", target.unit),
            ("aircraft_model_id", target.aircraft_model_id),
            ("comparison_key_hash", target.comparison_key_hash),
        ),
        knowledge_cutoff_utc=KNOWLEDGE,
        raw_record_count=0,
        observation_count=0,
        independent_subject_count=0,
        effective_evidence_count=0.0,
        observation_ids=(),
        episode_ids=(),
        subject_ids=(),
    )
    attribution_spec = P2AttributionSpec(
        attribution_spec_id=profile.attribution_spec_id,
        attribution_spec_version=profile.attribution_spec_version,
        model_plugin=profile.model_plugin,
        model_plugin_version=profile.model_plugin_version,
        uncertainty_method=profile.uncertainty_method,
        uncertainty_level=profile.uncertainty_level,
        binding=attribution_binding,
    )
    bundle = build_p2_input_bundle(
        target=target,
        feature_spec=feature_spec,
        reference_condition=P2ReferenceCondition(
            reference_condition_id=REFERENCE_ARTIFACT,
            binding=reference_binding,
        ),
        cohort=cohort,
        attribution_spec=attribution_spec,
        as_of_utc=AS_OF,
    )
    feature = P2FactorFeatureSet(
        factor_feature_set_id=FEATURE_SET,
        feature_spec_id=feature_spec.logical_key,
        feature_spec_version=feature_spec.artifact_version,
        source_observation_id=OBSERVATION,
        reference_condition_id=REFERENCE_ARTIFACT,
        feature_values=(("x", 3.0),),
        missing_mask=(("x", False),),
        world_refs=(),
        coverage=1.0,
        confidence=0.9,
        input_hash="8" * 64,
        created_at=AS_OF,
    )
    reason = "INSUFFICIENT_INDEPENDENT_SUBJECTS"
    diagnostics = {
        "reason_codes": [reason],
        "run_request_hash": "9" * 64,
        "uncertainty_method": profile.uncertainty_method,
        "uncertainty_level": profile.uncertainty_level,
        "factor_effect_semantics": profile.factor_effect_semantics,
        "claim_level": profile.claim_level,
    }
    run = P2AttributionRunProduct(
        attribution_run_id=RUN,
        attribution_spec_id=profile.attribution_spec_id,
        attribution_spec_version=profile.attribution_spec_version,
        model_plugin=profile.model_plugin,
        model_plugin_version=profile.model_plugin_version,
        training_dataset_snapshot_id=COHORT,
        reference_condition_id=REFERENCE_ARTIFACT,
        status="NOT_IDENTIFIABLE",
        diagnostics_json=json.dumps(
            diagnostics,
            sort_keys=True,
            separators=(",", ":"),
        ),
        model_artifact_uri=None,
        model_artifact_hash=None,
        started_at=AS_OF,
        completed_at=AS_OF,
        created_by="PRCB-C1",
        run_request_hash="9" * 64,
    )
    draft = P2AdjustedCapabilityEstimate(
        estimate_id=ESTIMATE,
        source_observation_id=OBSERVATION,
        source_release_id=SOURCE_RELEASE,
        p2_release_id=P2_RELEASE,
        attribution_run_id=RUN,
        aircraft_id=AIRCRAFT,
        capability_type=target.capability_type,
        reference_condition_id=REFERENCE_ARTIFACT,
        adjusted_value=None,
        unit="1",
        uncertainty_lower=None,
        uncertainty_upper=None,
        uncertainty_method=profile.uncertainty_method,
        uncertainty_level=profile.uncertainty_level,
        residual=None,
        factor_effects=(),
        claim_level=profile.claim_level,
        status="NOT_IDENTIFIABLE",
        reason_codes=(reason,),
        evidence_set_id=EVIDENCE,
        estimate_time=AS_OF,
        created_at=AS_OF,
        supersedes_estimate_id=None,
        logical_hash="0" * 64,
    )
    estimate = replace(
        draft,
        logical_hash=_logical_hash(draft),
    )

    repository = P2PersistenceRepository(
        SQLiteCanonicalRowRepository(connection)
    )
    repository.register_workspace_inputs(
        bundle,
        feature,
        cohort_rows=(),
        reference_factor_values={"x": 1.5},
    )
    repository.register_attribution_run(run)
    repository.register_adjusted_estimate(estimate)
    connection.commit()

    restarted_repository = P2PersistenceRepository(
        SQLiteCanonicalRowRepository(connection)
    )
    compute_input = restarted_repository.exact_compute_input(COHORT)
    restarted = restarted_repository.exact_workspace_material(ESTIMATE)

    assert compute_input.input_bundle == bundle
    assert compute_input.target_feature_set == feature
    assert compute_input.cohort_rows == ()
    assert compute_input.reference_factor_values == {"x": 1.5}
    assert restarted.input_bundle == bundle
    assert restarted.target_feature_set == feature
    assert restarted.attribution_run == run
    assert restarted.adjusted_estimate == estimate
    assert restarted.p2_release_id == P2_RELEASE
    assert restarted.p2_release_status == "PUBLISHED"
    assert restarted.p2_release_sealed is True
    assert restarted.model_artifact_json is None
