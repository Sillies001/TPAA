from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_capability import (
    P3ModelExecutionProfile,
    build_capability_surface,
    evaluate_surface,
    evaluate_temporal_holdout,
    execute_capability_model,
    materialize_training_dataset,
)
from tpaa_longitudinal import (
    P3AdjustedEstimateInput,
    P3AuthorityPolicy,
    P3GovernanceError,
    P3LifecycleEventInput,
    P3LifecycleSegment,
    P3ManagedObject,
    P3ModelValidationSnapshot,
    build_p3_lifecycle_segment,
    build_p3_validation_snapshot,
    validate_managed_object,
)
from tpaa_storage.object_seal import LocalSealedObjectFlow
from tpaa_storage.object_store import LocalObjectStore

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "fixtures" / "m7" / "p3_capability_model_golden.json"

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
    "model_object": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "lifecycle": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "source_ref": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "surface_object": "ffffffff-ffff-4fff-8fff-ffffffffffff",
}


@pytest.fixture(scope="module")
def policy() -> P3AuthorityPolicy:
    return P3AuthorityPolicy.from_canonical()


@pytest.fixture(scope="module")
def profile() -> P3ModelExecutionProfile:
    return P3ModelExecutionProfile.from_canonical()


def _estimate(index: int) -> P3AdjustedEstimateInput:
    digit = f"{index:x}"
    estimate = f"{digit * 8}-{digit * 4}-4{digit * 3}-8{digit * 3}-{digit * 12}"
    observation = f"{digit * 8}-{digit * 4}-4{digit * 3}-9{digit * 3}-{digit * 12}"
    config = f"{digit * 8}-{digit * 4}-4{digit * 3}-a{digit * 3}-{digit * 12}"
    session = f"{digit * 8}-{digit * 4}-4{digit * 3}-b{digit * 3}-{digit * 12}"
    episode = f"{digit * 8}-{digit * 4}-4{digit * 3}-c{digit * 3}-{digit * 12}"
    day = index + 1
    value = 9.0 + index
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
        adjusted_value=value,
        unit="1",
        uncertainty_lower=value - 0.5,
        uncertainty_upper=value + 0.5,
        factor_effects={"factor": 0.1},
        claim_level="ASSOCIATION_ONLY",
        status="IDENTIFIABLE",
        evidence_set_id=U["evidence"],
        knowledge_time_utc=f"2026-09-{day:02d}T12:00:00Z",
        estimate_time=f"2026-09-{day:02d}T12:00:00Z",
        created_at=f"2026-09-{day:02d}T12:00:00Z",
    )


def _estimates() -> tuple[P3AdjustedEstimateInput, ...]:
    return tuple(_estimate(index) for index in range(1, 5))


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


def _substrate(
    *,
    estimates: tuple[P3AdjustedEstimateInput, ...] | None = None,
    policy: P3AuthorityPolicy,
) -> tuple[
    P3LifecycleSegment,
    P3ModelValidationSnapshot,
    tuple[P3AdjustedEstimateInput, ...],
]:
    rows = estimates or _estimates()
    segment = build_p3_lifecycle_segment(
        segment_snapshot_id=U["segment"],
        estimates=rows,
        lifecycle_events=_events(),
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    validation = build_p3_validation_snapshot(
        validation_snapshot_id=U["validation"],
        training_dataset_snapshot_id=U["training"],
        segment=segment,
        estimates=rows,
        as_of_utc="2026-09-10T00:00:00Z",
        policy=policy,
    )
    return segment, validation, rows


def _golden() -> dict[str, object]:
    value: object = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m7_batch2_profile_is_exact_adopted_aircraft_v1(
    policy: P3AuthorityPolicy,
    profile: P3ModelExecutionProfile,
) -> None:
    assert profile.profile_id == "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL"
    assert profile.profile_version == "1.0.0"
    assert profile.profile_sha256 == policy.profile_sha256
    assert profile.model_spec_id == (
        "P3_MODEL_SPEC:P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL"
    )
    assert profile.subject_type == "AIRCRAFT"
    assert profile.minimum_total_points == 4
    assert profile.training_prefix_min_points == 3
    assert profile.training_prefix_max_points == 5
    assert profile.final_refit_max_points == 5
    assert profile.ewma_alpha == pytest.approx(1.0 / 3.0)


def test_m7_batch2_training_model_surface_match_static_golden(
    policy: P3AuthorityPolicy,
    profile: P3ModelExecutionProfile,
) -> None:
    segment, validation, rows = _substrate(policy=policy)
    training = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=rows,
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    holdout = evaluate_temporal_holdout(
        validation=validation,
        estimates=rows,
        policy=policy,
        profile=profile,
    )
    model = execute_capability_model(
        training=training,
        validation=validation,
        segment=segment,
        estimates=rows,
        trained_at_utc="2026-09-10T02:00:00Z",
        policy=policy,
        profile=profile,
    )
    surface = build_capability_surface(
        model_build=model,
        created_at_utc="2026-09-10T03:00:00Z",
        profile=profile,
    )
    golden = _golden()
    assert segment.segment_hash == golden["segment_hash"]
    assert validation.data_hash == golden["validation_snapshot_hash"]
    assert training.data_hash == golden["training_dataset_hash"]
    expected_validation = golden["validation"]
    assert isinstance(expected_validation, dict)
    assert holdout.status == expected_validation["status"]
    assert holdout.predicted_value == expected_validation["predicted_value"]
    assert holdout.observed_value == expected_validation["observed_value"]
    assert holdout.absolute_error == expected_validation["absolute_error"]
    assert holdout.training_mad == expected_validation["training_mad"]
    assert holdout.heldout_p2_half_width == expected_validation["heldout_p2_half_width"]
    assert holdout.acceptance_limit == expected_validation["acceptance_limit"]
    expected_refit = golden["final_refit"]
    assert isinstance(expected_refit, dict)
    assert model.intercept == expected_refit["intercept"]
    assert model.slope == expected_refit["slope"]
    assert model.current_value == expected_refit["current_value"]
    assert model.ewma_value == expected_refit["ewma_value"]
    assert model.stability_mad == expected_refit["stability_mad"]
    assert model.p3_uncertainty_half_width == expected_refit[
        "p3_uncertainty_half_width"
    ]
    assert model.model.model_artifact_hash == golden["model_artifact_hash"]
    assert model.model.capability_model_id == golden["capability_model_id"]
    assert model.model.model_artifact_uri == golden["model_artifact_uri"]
    assert set(model.artifact) == {
        "schema",
        "profile_id",
        "profile_version",
        "segment_snapshot_id",
        "training_dataset_snapshot_id",
        "validation_snapshot_id",
        "aircraft_id",
        "capability_type",
        "reference_condition_id",
        "unit",
        "configuration_key",
        "fit_window_estimate_ids",
        "session_order_min",
        "session_order_max",
        "intercept",
        "slope",
        "current_value",
        "ewma_value",
        "stability_mad",
        "p2_uncertainty_half_width_max",
        "p3_uncertainty_half_width",
        "validation_metrics",
        "validity_domain",
    }
    assert surface.surface.dataset_hash == golden["surface_dataset_hash"]
    assert surface.surface.surface_id == golden["surface_id"]
    assert surface.surface.dataset_uri == golden["surface_dataset_uri"]
    assert set(training.projection()) == {
        "dataset_snapshot_id",
        "snapshot_type",
        "query_or_manifest",
        "input_refs",
        "data_hash",
        "schema_version",
        "created_at",
        "frozen",
    }
    assert set(model.model.projection()) == {
        "capability_model_id",
        "model_spec_id",
        "model_spec_version",
        "subject_type",
        "subject_id",
        "capability_type",
        "training_dataset_snapshot_id",
        "plugin_name",
        "plugin_version",
        "model_artifact_uri",
        "model_artifact_hash",
        "validity_domain",
        "validation_metrics",
        "status",
        "trained_at",
        "published_at",
        "supersedes_model_id",
    }
    assert set(surface.surface.projection()) == {
        "surface_id",
        "capability_model_id",
        "surface_semantics",
        "axes",
        "dataset_uri",
        "dataset_hash",
        "uncertainty_dataset_uri",
        "validity_domain",
        "created_at",
    }
    expected_points = golden["surface_points"]
    assert isinstance(expected_points, list)
    rows = surface.dataset["rows"]
    assert isinstance(rows, list)
    for expected, actual in zip(expected_points, rows, strict=True):
        assert isinstance(expected, dict)
        assert isinstance(actual, dict)
        for key in (
            "session_order",
            "value",
            "uncertainty_lower",
            "uncertainty_upper",
        ):
            assert actual[key] == expected[key]


def test_m7_batch2_input_order_replay_is_logically_identical(
    policy: P3AuthorityPolicy,
    profile: P3ModelExecutionProfile,
) -> None:
    segment, validation, rows = _substrate(policy=policy)
    training_a = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=rows,
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    training_b = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=tuple(reversed(rows)),
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    model_a = execute_capability_model(
        training=training_a,
        validation=validation,
        segment=segment,
        estimates=rows,
        trained_at_utc="2026-09-10T02:00:00Z",
        policy=policy,
        profile=profile,
    )
    model_b = execute_capability_model(
        training=training_b,
        validation=validation,
        segment=segment,
        estimates=tuple(reversed(rows)),
        trained_at_utc="2026-09-10T02:00:00Z",
        policy=policy,
        profile=profile,
    )
    surface_a = build_capability_surface(
        model_build=model_a,
        created_at_utc="2026-09-10T03:00:00Z",
        profile=profile,
    )
    surface_b = build_capability_surface(
        model_build=model_b,
        created_at_utc="2026-09-10T03:00:00Z",
        profile=profile,
    )
    assert training_a.data_hash == training_b.data_hash
    assert model_a.artifact_bytes == model_b.artifact_bytes
    assert model_a.model.capability_model_id == model_b.model.capability_model_id
    assert surface_a.dataset_bytes == surface_b.dataset_bytes
    assert surface_a.surface.surface_id == surface_b.surface.surface_id


def test_m7_batch2_validation_failure_blocks_model_publication(
    policy: P3AuthorityPolicy,
    profile: P3ModelExecutionProfile,
) -> None:
    rows = list(_estimates())
    rows[-1] = replace(
        rows[-1],
        adjusted_value=30.0,
        uncertainty_lower=29.5,
        uncertainty_upper=30.5,
    )
    segment, validation, changed = _substrate(
        estimates=tuple(rows),
        policy=policy,
    )
    training = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=changed,
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    result = evaluate_temporal_holdout(
        validation=validation,
        estimates=changed,
        policy=policy,
        profile=profile,
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.absolute_error > result.acceptance_limit
    with pytest.raises(P3GovernanceError) as blocked:
        execute_capability_model(
            training=training,
            validation=validation,
            segment=segment,
            estimates=changed,
            trained_at_utc="2026-09-10T02:00:00Z",
            policy=policy,
            profile=profile,
        )
    assert blocked.value.code == "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED"


def test_m7_batch2_surface_is_observed_domain_only(
    policy: P3AuthorityPolicy,
    profile: P3ModelExecutionProfile,
) -> None:
    segment, validation, rows = _substrate(policy=policy)
    training = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=rows,
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    model = execute_capability_model(
        training=training,
        validation=validation,
        segment=segment,
        estimates=rows,
        trained_at_utc="2026-09-10T02:00:00Z",
        policy=policy,
        profile=profile,
    )
    surface = build_capability_surface(
        model_build=model,
        created_at_utc="2026-09-10T03:00:00Z",
        profile=profile,
    )
    inside = evaluate_surface(surface, session_order=4)
    assert inside.validity_domain_status == "IN_DOMAIN"
    assert inside.value == 13.0
    assert inside.uncertainty_lower == 12.0
    assert inside.uncertainty_upper == 14.0
    outside = evaluate_surface(surface, session_order=5)
    assert outside.validity_domain_status == "OUT_OF_DOMAIN"
    assert outside.value is None
    assert outside.uncertainty_lower is None
    assert outside.uncertainty_upper is None


def test_m7_batch2_model_and_surface_bytes_are_physically_sealed_and_hash_bound(
    tmp_path: Path,
    policy: P3AuthorityPolicy,
    profile: P3ModelExecutionProfile,
) -> None:
    segment, validation, rows = _substrate(policy=policy)
    training = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=rows,
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    model = execute_capability_model(
        training=training,
        validation=validation,
        segment=segment,
        estimates=rows,
        trained_at_utc="2026-09-10T02:00:00Z",
        policy=policy,
        profile=profile,
    )
    surface = build_capability_surface(
        model_build=model,
        created_at_utc="2026-09-10T03:00:00Z",
        profile=profile,
    )
    flow = LocalSealedObjectFlow(LocalObjectStore(tmp_path))
    staged_model = flow.stage(
        sealed_uri=model.model.model_artifact_uri,
        data=model.artifact_bytes,
        operation_id="m7-model",
    )
    stored_model = flow.seal(staged_model)
    staged_surface = flow.stage(
        sealed_uri=surface.surface.dataset_uri,
        data=surface.dataset_bytes,
        operation_id="m7-surface",
    )
    stored_surface = flow.seal(staged_surface)
    model_object = P3ManagedObject(
        object_ref_id=U["model_object"],
        managed_uri=stored_model.logical_uri,
        artifact_sha256=stored_model.artifact_sha256,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    surface_object = P3ManagedObject(
        object_ref_id=U["surface_object"],
        managed_uri=stored_surface.logical_uri,
        artifact_sha256=stored_surface.artifact_sha256,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    assert validate_managed_object(
        model_object,
        expected_uri=model.model.model_artifact_uri,
        expected_hash=model.model.model_artifact_hash,
        policy=policy,
    ) == model_object
    assert validate_managed_object(
        surface_object,
        expected_uri=surface.surface.dataset_uri,
        expected_hash=surface.surface.dataset_hash,
        policy=policy,
    ) == surface_object


def test_m7_batch2_managed_object_hash_mismatch_remains_fail_closed(
    tmp_path: Path,
    policy: P3AuthorityPolicy,
    profile: P3ModelExecutionProfile,
) -> None:
    segment, validation, rows = _substrate(policy=policy)
    training = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=rows,
        created_at_utc="2026-09-10T01:00:00Z",
        policy=policy,
        profile=profile,
    )
    model = execute_capability_model(
        training=training,
        validation=validation,
        segment=segment,
        estimates=rows,
        trained_at_utc="2026-09-10T02:00:00Z",
        policy=policy,
        profile=profile,
    )
    flow = LocalSealedObjectFlow(LocalObjectStore(tmp_path))
    stored = flow.seal(
        flow.stage(
            sealed_uri=model.model.model_artifact_uri,
            data=model.artifact_bytes,
            operation_id="m7-model-mismatch",
        )
    )
    managed = P3ManagedObject(
        object_ref_id=U["model_object"],
        managed_uri=stored.logical_uri,
        artifact_sha256=stored.artifact_sha256,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    with pytest.raises(P3GovernanceError) as mismatch:
        validate_managed_object(
            managed,
            expected_uri=model.model.model_artifact_uri,
            expected_hash="0" * 64,
            policy=policy,
        )
    assert mismatch.value.code == "FAIL_CLOSED_P3_MANAGED_OBJECT_HASH_MISMATCH"
