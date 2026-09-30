from __future__ import annotations

from dataclasses import replace

import pytest

from tpaa_longitudinal import (
    P3AdjustedEstimateInput,
    P3AdmissionEvidence,
    P3AuthorityPolicy,
    P3GovernanceError,
    P3LifecycleEventInput,
    P3ManagedObject,
    assert_capability_claim_allowed,
    assert_p1_p2_immutable,
    assert_p3_claim_level,
    build_p3_lifecycle_segment,
    build_p3_validation_snapshot,
    project_p2_adjusted_estimate,
    validate_managed_object,
)

H = "a" * 64
CONFIG_HASH = "b" * 64
U = {
    "p2_release": "11111111-1111-4111-8111-111111111111",
    "p1_release": "22222222-2222-4222-8222-222222222222",
    "attribution": "33333333-3333-4333-8333-333333333333",
    "aircraft": "44444444-4444-4444-8444-444444444444",
    "model": "55555555-5555-4555-8555-555555555555",
    "scope": "66666666-6666-4666-8666-666666666666",
    "reference": "77777777-7777-4777-8777-777777777777",
    "evidence": "88888888-8888-4888-8888-888888888888",
    "segment": "99999999-9999-4999-8999-999999999999",
    "training": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "validation": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "object": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "lifecycle": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "source_ref": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
}


@pytest.fixture(scope="module")
def policy() -> P3AuthorityPolicy:
    return P3AuthorityPolicy.from_canonical()


def _estimate(index: int) -> P3AdjustedEstimateInput:
    digit = f"{index:x}"
    estimate = f"{digit * 8}-{digit * 4}-4{digit * 3}-8{digit * 3}-{digit * 12}"
    observation = f"{digit * 8}-{digit * 4}-4{digit * 3}-9{digit * 3}-{digit * 12}"
    config = f"{digit * 8}-{digit * 4}-4{digit * 3}-a{digit * 3}-{digit * 12}"
    session = f"{digit * 8}-{digit * 4}-4{digit * 3}-b{digit * 3}-{digit * 12}"
    episode = f"{digit * 8}-{digit * 4}-4{digit * 3}-c{digit * 3}-{digit * 12}"
    day = index + 1
    return P3AdjustedEstimateInput(
        estimate_id=estimate,
        p2_release_id=U["p2_release"],
        p2_release_status="PUBLISHED",
        source_observation_id=observation,
        source_release_id=U["p1_release"],
        source_release_status="PUBLISHED",
        attribution_run_id=U["attribution"],
        aircraft_id=U["aircraft"],
        aircraft_model_id=U["model"],
        configuration_snapshot_id=config,
        configuration_snapshot_hash=CONFIG_HASH,
        configuration_key=f"AIRCRAFT_CONFIG_SHA256:{CONFIG_HASH}",
        session_id=session,
        episode_id=episode,
        session_occurred_at_utc=f"2026-09-{day:02d}T00:00:00Z",
        session_order_scope_id=U["scope"],
        session_order_scope_status="ACTIVE",
        session_order_assignment_current=True,
        session_order=index,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        metric_semantic_id="metric.test.energy",
        metric_semantic_version=1,
        comparison_key_hash=H,
        reference_condition_id=U["reference"],
        adjusted_value=40.0 + index,
        unit="1",
        uncertainty_lower=39.0 + index,
        uncertainty_upper=41.0 + index,
        factor_effects={"factor": 0.1},
        claim_level="ASSOCIATION_ONLY",
        status="IDENTIFIABLE",
        evidence_set_id=U["evidence"],
        knowledge_time_utc=f"2026-09-{day:02d}T12:00:00Z",
        estimate_time=f"2026-09-{day:02d}T12:00:00Z",
        created_at=f"2026-09-{day:02d}T12:00:00Z",
    )


def _events() -> tuple[P3LifecycleEventInput, ...]:
    return (
        P3LifecycleEventInput(
            lifecycle_event_id=U["lifecycle"],
            aircraft_id=U["aircraft"],
            event_type="BASELINE_IMPORT",
            start_occurred_at_utc="2026-08-01T00:00:00Z",
            end_occurred_at_utc="2026-08-01T01:00:00Z",
            source_ref=U["source_ref"],
        ),
    )


def test_m7_batch1_exact_segment_and_validation_snapshot_are_deterministic(
    policy: P3AuthorityPolicy,
) -> None:
    estimates = tuple(_estimate(index) for index in range(1, 5))
    first = build_p3_lifecycle_segment(
        segment_snapshot_id=U["segment"],
        estimates=estimates,
        lifecycle_events=_events(),
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    second = build_p3_lifecycle_segment(
        segment_snapshot_id=U["segment"],
        estimates=tuple(reversed(estimates)),
        lifecycle_events=_events(),
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    assert first.segment_hash == second.segment_hash
    assert first.configuration_key == f"AIRCRAFT_CONFIG_SHA256:{CONFIG_HASH}"
    assert first.configuration_snapshot_ids != ()
    assert first.lifecycle_event_ids == (U["lifecycle"],)
    validation = build_p3_validation_snapshot(
        validation_snapshot_id=U["validation"],
        training_dataset_snapshot_id=U["training"],
        segment=first,
        estimates=estimates,
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    assert len(validation.training_estimate_ids) == 3
    assert len(validation.validation_estimate_ids) == 1
    assert validation.claim_evidence_tier == "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"
    assert len(validation.data_hash) == 64


def test_m7_batch1_not_identifiable_and_uncertainty_fail_closed(
    policy: P3AuthorityPolicy,
) -> None:
    with pytest.raises(P3GovernanceError) as ni:
        project_p2_adjusted_estimate(
            replace(
                _estimate(1),
                status="NOT_IDENTIFIABLE",
                adjusted_value=None,
                uncertainty_lower=None,
                uncertainty_upper=None,
            ),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert ni.value.code == "FAIL_CLOSED_P3_NOT_IDENTIFIABLE_NUMERIC_USE"

    with pytest.raises(P3GovernanceError) as uncertainty:
        project_p2_adjusted_estimate(
            replace(_estimate(1), uncertainty_lower=42.0),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert uncertainty.value.code == "FAIL_CLOSED_P3_UNCERTAINTY_REQUIRED"


def test_m7_batch1_configuration_key_and_duplicate_order_fail_closed(
    policy: P3AuthorityPolicy,
) -> None:
    estimates = tuple(_estimate(index) for index in range(1, 5))
    with pytest.raises(P3GovernanceError) as config:
        build_p3_lifecycle_segment(
            segment_snapshot_id=U["segment"],
            estimates=(
                estimates[0],
                replace(
                    estimates[1],
                    configuration_snapshot_hash="c" * 64,
                    configuration_key=f"AIRCRAFT_CONFIG_SHA256:{'c' * 64}",
                ),
                *estimates[2:],
            ),
            lifecycle_events=_events(),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert config.value.code == "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED"

    with pytest.raises(P3GovernanceError) as duplicate:
        build_p3_lifecycle_segment(
            segment_snapshot_id=U["segment"],
            estimates=(estimates[0], replace(estimates[1], session_order=1), *estimates[2:]),
            lifecycle_events=_events(),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert duplicate.value.code == "FAIL_CLOSED_P3_SESSION_ORDER_REQUIRED"


def test_m7_batch1_lifecycle_boundaries_and_future_information_fail_closed(
    policy: P3AuthorityPolicy,
) -> None:
    estimates = tuple(_estimate(index) for index in range(1, 5))
    inside = replace(
        _events()[0],
        start_occurred_at_utc="2026-09-03T12:00:00Z",
        end_occurred_at_utc="2026-09-03T13:00:00Z",
    )
    with pytest.raises(P3GovernanceError) as boundary:
        build_p3_lifecycle_segment(
            segment_snapshot_id=U["segment"],
            estimates=estimates,
            lifecycle_events=(inside,),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert boundary.value.code == "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED"

    future = replace(
        _events()[0],
        start_occurred_at_utc="2026-09-11T00:00:00Z",
        end_occurred_at_utc=None,
    )
    with pytest.raises(P3GovernanceError) as future_error:
        build_p3_lifecycle_segment(
            segment_snapshot_id=U["segment"],
            estimates=estimates,
            lifecycle_events=(future,),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert future_error.value.code == "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION"


def test_m7_batch1_validation_requires_four_points_and_no_episode_overlap(
    policy: P3AuthorityPolicy,
) -> None:
    estimates = tuple(_estimate(index) for index in range(1, 5))
    segment = build_p3_lifecycle_segment(
        segment_snapshot_id=U["segment"],
        estimates=estimates,
        lifecycle_events=_events(),
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    with pytest.raises(P3GovernanceError) as short:
        short_estimates = estimates[:3]
        short_segment = build_p3_lifecycle_segment(
            segment_snapshot_id=U["segment"],
            estimates=short_estimates,
            lifecycle_events=_events(),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
        build_p3_validation_snapshot(
            validation_snapshot_id=U["validation"],
            training_dataset_snapshot_id=U["training"],
            segment=short_segment,
            estimates=short_estimates,
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert short.value.code == "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED"

    leaked = (*estimates[:3], replace(estimates[3], episode_id=estimates[0].episode_id))
    leaked_segment = build_p3_lifecycle_segment(
        segment_snapshot_id=U["segment"],
        estimates=leaked,
        lifecycle_events=_events(),
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    with pytest.raises(P3GovernanceError) as overlap:
        build_p3_validation_snapshot(
            validation_snapshot_id=U["validation"],
            training_dataset_snapshot_id=U["training"],
            segment=leaked_segment,
            estimates=leaked,
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert overlap.value.code == "FAIL_CLOSED_P3_TRAINING_VALIDATION_LEAKAGE"
    assert segment.independent_aircraft_count == 1


def test_m7_batch1_estimate_creation_after_as_of_fails_closed(
    policy: P3AuthorityPolicy,
) -> None:
    with pytest.raises(P3GovernanceError) as future:
        project_p2_adjusted_estimate(
            replace(
                _estimate(1),
                estimate_time="2026-09-11T00:00:00Z",
                created_at="2026-09-11T00:00:00Z",
            ),
            as_of_utc="2026-09-10T00:00:00Z",
            policy=policy,
        )
    assert future.value.code == "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION"


def test_m7_batch1_managed_object_binding_is_exact(
    policy: P3AuthorityPolicy,
) -> None:
    good = P3ManagedObject(
        object_ref_id=U["object"],
        managed_uri="managed://p3/models/model-1",
        artifact_sha256=H,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    assert (
        validate_managed_object(
            good,
            expected_uri=good.managed_uri,
            expected_hash=H,
            policy=policy,
        )
        == good
    )
    with pytest.raises(P3GovernanceError) as unsealed:
        validate_managed_object(
            replace(good, sealed=False),
            expected_uri=good.managed_uri,
            expected_hash=H,
            policy=policy,
        )
    assert unsealed.value.code == "FAIL_CLOSED_P3_MANAGED_OBJECT_REQUIRED"
    with pytest.raises(P3GovernanceError) as mismatch:
        validate_managed_object(
            good,
            expected_uri=good.managed_uri,
            expected_hash="b" * 64,
            policy=policy,
        )
    assert mismatch.value.code == "FAIL_CLOSED_P3_MANAGED_OBJECT_HASH_MISMATCH"
    with pytest.raises(P3GovernanceError) as file_uri:
        validate_managed_object(
            replace(good, managed_uri="file:///tmp/model.bin"),
            expected_uri="file:///tmp/model.bin",
            expected_hash=H,
            policy=policy,
        )
    assert file_uri.value.code == "FAIL_CLOSED_P3_MANAGED_OBJECT_REQUIRED"
    with pytest.raises(P3GovernanceError) as alias:
        validate_managed_object(
            replace(good, managed_uri="managed://p3/models/LATEST"),
            expected_uri="managed://p3/models/LATEST",
            expected_hash=H,
            policy=policy,
        )
    assert alias.value.code == "FAIL_CLOSED_P3_MANAGED_OBJECT_REQUIRED"


def test_m7_batch1_claim_and_admission_guards_remain_fail_closed(
    policy: P3AuthorityPolicy,
) -> None:
    assert_p3_claim_level(
        "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        policy=policy,
    )
    with pytest.raises(P3GovernanceError) as intrinsic:
        assert_p3_claim_level("INTRINSIC_CAPABILITY_ESTIMATE", policy=policy)
    assert intrinsic.value.code == "FAIL_CLOSED_P3_CLAIM_EVIDENCE_REQUIRED"

    blocked = P3AdmissionEvidence(
        source_revision="1" * 40,
        event_name="pull_request",
        git_ref="refs/pull/1/merge",
        protected_main=False,
        m7_exit_decision="PENDING_PROTECTED_MAIN",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
        p4_p6_inactive=True,
    )
    with pytest.raises(P3GovernanceError) as p3:
        assert_capability_claim_allowed("P3", evidence=blocked, policy=policy)
    assert p3.value.code == "FAIL_CLOSED_P3_NOT_ADMITTED"

    allowed = replace(
        blocked,
        event_name="push",
        git_ref="refs/heads/main",
        protected_main=True,
        m7_exit_decision="GO",
    )
    assert_capability_claim_allowed("P3", evidence=allowed, policy=policy)

    with pytest.raises(P3GovernanceError) as p4:
        assert_capability_claim_allowed("P4", policy=policy)
    assert p4.value.code == "FAIL_CLOSED_P4_P6_NOT_ADMITTED"


def test_m7_batch1_p1_p2_products_cannot_be_overwritten() -> None:
    with pytest.raises(P3GovernanceError) as mutation:
        assert_p1_p2_immutable({"value": 1}, {"value": 2})
    assert mutation.value.code == "FAIL_CLOSED_P3_P1_P2_MUTATION_FORBIDDEN"
