from __future__ import annotations

from dataclasses import replace

import pytest

from tpaa_assessment import (
    P1ObservationInput,
    P2AdmissionEvidence,
    P2ArtifactBinding,
    P2AttributionSpec,
    P2AuthorityPolicy,
    P2CohortSnapshot,
    P2GovernanceError,
    P2ReferenceCondition,
    assert_capability_claim_allowed,
    assert_p1_observed_value_immutable,
    build_p2_input_bundle,
    governed_result,
    project_p1_observation,
    validate_factor_effect_semantics,
)

U = {
    "observation": "11111111-1111-4111-8111-111111111111",
    "release": "22222222-2222-4222-8222-222222222222",
    "episode": "33333333-3333-4333-8333-333333333333",
    "subject": "44444444-4444-4444-8444-444444444444",
    "aircraft": "55555555-5555-4555-8555-555555555555",
    "model": "66666666-6666-4666-8666-666666666666",
    "config": "77777777-7777-4777-8777-777777777777",
    "context": "88888888-8888-4888-8888-888888888888",
    "evidence": "99999999-9999-4999-8999-999999999999",
    "feature_artifact": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "feature_object": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "reference": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "reference_object": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "attribution_artifact": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "attribution_object": "ffffffff-ffff-4fff-8fff-ffffffffffff",
    "dataset": "12121212-1212-4121-8121-121212121212",
    "cohort_observation": "13131313-1313-4131-8131-131313131313",
    "cohort_episode": "14141414-1414-4141-8141-141414141414",
    "cohort_subject": "15151515-1515-4151-8151-151515151515",
}
H = "a" * 64


@pytest.fixture(scope="module")
def policy() -> P2AuthorityPolicy:
    return P2AuthorityPolicy.from_canonical()


def _target() -> P1ObservationInput:
    return P1ObservationInput(
        observation_id=U["observation"],
        release_id=U["release"],
        release_status="PUBLISHED",
        release_sealed=True,
        episode_id=U["episode"],
        subject_entity_id=U["subject"],
        aircraft_id=U["aircraft"],
        aircraft_model_id=U["model"],
        aircraft_configuration_snapshot_id=U["config"],
        context_id=U["context"],
        capability_type="KINEMATIC_ENERGY_CONTROL",
        metric_semantic_id="metric.test.energy",
        metric_semantic_version="1",
        comparison_key_hash=H,
        evidence_set_id=U["evidence"],
        observed_value=42.0,
        unit="1",
        coverage=1.0,
        confidence=0.9,
        eligibility_status="ELIGIBLE",
        knowledge_time_utc="2026-09-01T00:00:00Z",
    )


def _binding(
    kind: str,
    *,
    key: str,
    version: str,
    artifact: str,
    obj: str,
) -> P2ArtifactBinding:
    return P2ArtifactBinding(
        context_artifact_id=artifact,
        object_ref_id=obj,
        artifact_kind=kind,
        logical_key=key,
        artifact_version=version,
        artifact_sha256=H,
        status="ACTIVE",
        sealed=True,
    )


def _inputs(
    policy: P2AuthorityPolicy,
) -> tuple[
    P2ArtifactBinding,
    P2ReferenceCondition,
    P2CohortSnapshot,
    P2AttributionSpec,
]:
    feature = _binding(
        policy.feature_artifact_kind,
        key="P2_FEATURE_SPEC_TEST",
        version="1.0.0",
        artifact=U["feature_artifact"],
        obj=U["feature_object"],
    )
    reference_binding = _binding(
        policy.reference_artifact_kind,
        key="P2_REFERENCE_TEST",
        version="1.0.0",
        artifact=U["reference"],
        obj=U["reference_object"],
    )
    reference = P2ReferenceCondition(
        reference_condition_id=U["reference"],
        binding=reference_binding,
    )
    cohort = P2CohortSnapshot(
        dataset_snapshot_id=U["dataset"],
        snapshot_type=policy.cohort_snapshot_type,
        data_hash=H,
        schema_version="1.6.0",
        frozen=True,
        cohort_spec_id="P2_COHORT_TEST",
        cohort_spec_version="1.0.0",
        comparability_dimensions=(
            ("capability_type", "KINEMATIC_ENERGY_CONTROL"),
            ("metric_semantic_id", "metric.test.energy"),
            ("metric_semantic_version", "1"),
            ("unit", "1"),
            ("aircraft_model_id", U["model"]),
            ("comparison_key_hash", H),
        ),
        knowledge_cutoff_utc="2026-09-02T00:00:00Z",
        raw_record_count=2,
        observation_count=1,
        independent_subject_count=1,
        effective_evidence_count=1.0,
        observation_ids=(U["cohort_observation"],),
        episode_ids=(U["cohort_episode"],),
        subject_ids=(U["cohort_subject"],),
    )
    attribution_binding = _binding(
        policy.attribution_artifact_kind,
        key="P2_ATTRIBUTION_TEST",
        version="1.0.0",
        artifact=U["attribution_artifact"],
        obj=U["attribution_object"],
    )
    spec = P2AttributionSpec(
        attribution_spec_id="P2_ATTRIBUTION_TEST",
        attribution_spec_version="1.0.0",
        model_plugin="test-model",
        model_plugin_version="1.0.0",
        uncertainty_method="bootstrap",
        uncertainty_level="0.95",
        binding=attribution_binding,
    )
    return feature, reference, cohort, spec


def test_m6_batch1_valid_input_bundle_is_deterministic(
    policy: P2AuthorityPolicy,
) -> None:
    feature, reference, cohort, spec = _inputs(policy)
    first = build_p2_input_bundle(
        target=_target(),
        feature_spec=feature,
        reference_condition=reference,
        cohort=cohort,
        attribution_spec=spec,
        as_of_utc="2026-09-03T00:00:00Z",
        policy=policy,
    )
    second = build_p2_input_bundle(
        target=_target(),
        feature_spec=feature,
        reference_condition=reference,
        cohort=cohort,
        attribution_spec=spec,
        as_of_utc="2026-09-03T00:00:00Z",
        policy=policy,
    )
    assert first.input_hash == second.input_hash
    assert len(first.input_hash) == 64


def test_m6_batch1_rejects_unpublished_or_latest_p1(
    policy: P2AuthorityPolicy,
) -> None:
    with pytest.raises(P2GovernanceError) as unpublished:
        project_p1_observation(
            replace(_target(), release_status="DRAFT"),
            policy=policy,
        )
    assert unpublished.value.code == "FAIL_CLOSED_P2_PUBLISHED_P1_REQUIRED"

    with pytest.raises(P2GovernanceError) as latest:
        project_p1_observation(
            replace(_target(), metric_semantic_version="LATEST"),
            policy=policy,
        )
    assert latest.value.code == "FAIL_CLOSED_P2_CURRENT_LATEST_FORBIDDEN"


def test_m6_batch1_rejects_same_episode_and_future_information(
    policy: P2AuthorityPolicy,
) -> None:
    feature, reference, cohort, spec = _inputs(policy)
    with pytest.raises(P2GovernanceError) as episode:
        build_p2_input_bundle(
            target=_target(),
            feature_spec=feature,
            reference_condition=reference,
            cohort=replace(cohort, episode_ids=(U["episode"],)),
            attribution_spec=spec,
            as_of_utc="2026-09-03T00:00:00Z",
            policy=policy,
        )
    assert episode.value.code == "FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE"

    with pytest.raises(P2GovernanceError) as future:
        build_p2_input_bundle(
            target=_target(),
            feature_spec=feature,
            reference_condition=reference,
            cohort=replace(
                cohort,
                knowledge_cutoff_utc="2026-09-04T00:00:00Z",
            ),
            attribution_spec=spec,
            as_of_utc="2026-09-03T00:00:00Z",
            policy=policy,
        )
    assert future.value.code == "FAIL_CLOSED_P2_FUTURE_INFORMATION"


def test_m6_batch1_rejects_stale_or_default_spec(
    policy: P2AuthorityPolicy,
) -> None:
    feature, reference, cohort, spec = _inputs(policy)
    with pytest.raises(P2GovernanceError) as stale:
        build_p2_input_bundle(
            target=_target(),
            feature_spec=replace(feature, artifact_version="LATEST"),
            reference_condition=reference,
            cohort=cohort,
            attribution_spec=spec,
            as_of_utc="2026-09-03T00:00:00Z",
            policy=policy,
        )
    assert stale.value.code == "FAIL_CLOSED_P2_CURRENT_LATEST_FORBIDDEN"


def test_m6_batch1_p1_no_overwrite_and_causal_boundary(
    policy: P2AuthorityPolicy,
) -> None:
    with pytest.raises(P2GovernanceError) as mutation:
        assert_p1_observed_value_immutable(42.0, 41.5)
    assert mutation.value.code == "FAIL_CLOSED_P2_P1_MUTATION_FORBIDDEN"

    with pytest.raises(P2GovernanceError) as causal:
        validate_factor_effect_semantics(
            semantics="CAUSAL",
            causal_evidence_set_id=None,
            policy=policy,
        )
    assert causal.value.code == "FAIL_CLOSED_P2_CAUSAL_EVIDENCE_REQUIRED"


def test_m6_batch1_not_identifiable_is_valid_product(
    policy: P2AuthorityPolicy,
) -> None:
    result = governed_result(
        status="NOT_IDENTIFIABLE",
        adjusted_value=None,
        reason_code="INSUFFICIENT_EFFECTIVE_EVIDENCE",
        policy=policy,
    )
    assert result.status == "NOT_IDENTIFIABLE"
    assert result.adjusted_value is None


def test_m6_batch1_p2_and_future_phase_claims_fail_closed(
    policy: P2AuthorityPolicy,
) -> None:
    evidence = P2AdmissionEvidence(
        source_revision="1" * 40,
        event_name="pull_request",
        git_ref="refs/pull/1/merge",
        protected_main=False,
        m6_exit_decision="NOT_GO",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
        p3_p6_inactive=True,
    )
    with pytest.raises(P2GovernanceError) as p2:
        assert_capability_claim_allowed("P2", evidence=evidence, policy=policy)
    assert p2.value.code == "FAIL_CLOSED_P2_NOT_ADMITTED"

    with pytest.raises(P2GovernanceError) as p3:
        assert_capability_claim_allowed("P3", policy=policy)
    assert p3.value.code == "FAIL_CLOSED_P3_P6_NOT_ADMITTED"
