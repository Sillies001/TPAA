from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

import pytest

from tpaa_assessment import (
    P1ObservationInput,
    P2ArtifactBinding,
    P2AttributionExecution,
    P2AttributionSpec,
    P2AuthorityPolicy,
    P2CohortRow,
    P2CohortSnapshot,
    P2ExecutionProfile,
    P2FactorFeatureSet,
    P2GovernanceError,
    P2InputBundle,
    P2ReferenceCondition,
    build_p2_input_bundle,
    execute_p2_attribution,
    materialize_factor_feature_set,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "tests" / "fixtures" / "m6" / "p2_attribution_golden.json"
AS_OF = "2026-09-10T00:00:00Z"
KNOWLEDGE = "2026-09-01T00:00:00Z"
H = "a" * 64

type Point = tuple[str, str, dict[str, float], float]


@dataclass(frozen=True, slots=True)
class _Case:
    profile: P2ExecutionProfile
    bundle: P2InputBundle
    target_feature_set: P2FactorFeatureSet
    rows: tuple[P2CohortRow, ...]
    reference_values: dict[str, float]
    feature_spec: P2ArtifactBinding


def _u(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"urn:tpaa:test:m6:p2:{name}"))


def _golden() -> dict[str, object]:
    value: object = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _section(name: str) -> dict[str, object]:
    section = _golden()[name]
    assert isinstance(section, dict)
    return cast(dict[str, object], section)


def _observation(
    *,
    label: str,
    subject_label: str,
    observed_value: float,
    capability_type: str = "KINEMATIC_ENERGY_CONTROL",
    episode_label: str | None = None,
    knowledge_time_utc: str = KNOWLEDGE,
) -> P1ObservationInput:
    return P1ObservationInput(
        observation_id=_u(f"observation:{label}"),
        release_id=_u(f"release:{label}"),
        release_status="PUBLISHED",
        release_sealed=True,
        episode_id=_u(f"episode:{episode_label or label}"),
        subject_entity_id=_u(f"subject:{subject_label}"),
        aircraft_id=_u(f"aircraft:{label}"),
        aircraft_model_id=_u("aircraft-model"),
        aircraft_configuration_snapshot_id=_u("aircraft-config"),
        context_id=_u(f"context:{label}"),
        capability_type=capability_type,
        metric_semantic_id="metric.test.p2.reference-adjustment",
        metric_semantic_version=1,
        comparison_key_hash=H,
        evidence_set_id=_u(f"p1-evidence:{label}"),
        observed_value=observed_value,
        unit="1",
        coverage=1.0,
        confidence=0.9,
        eligibility_status="ELIGIBLE",
        knowledge_time_utc=knowledge_time_utc,
    )


def _bindings(
    profile: P2ExecutionProfile,
) -> tuple[P2ArtifactBinding, P2ReferenceCondition, P2AttributionSpec]:
    policy = P2AuthorityPolicy.from_canonical()
    feature = P2ArtifactBinding(
        context_artifact_id=_u("feature-spec-artifact"),
        object_ref_id=_u("feature-spec-object"),
        artifact_kind=policy.feature_artifact_kind,
        logical_key="P2_FACTOR_FEATURE_SPEC:QUALIFICATION_V1",
        artifact_version="1.0.0",
        schema_version=policy.feature_schema_version,
        artifact_sha256="b" * 64,
        status="ACTIVE",
        sealed=True,
    )
    reference_id = _u("reference-condition")
    reference = P2ReferenceCondition(
        reference_condition_id=reference_id,
        binding=P2ArtifactBinding(
            context_artifact_id=reference_id,
            object_ref_id=_u("reference-object"),
            artifact_kind=policy.reference_artifact_kind,
            logical_key="P2_REFERENCE_CONDITION:QUALIFICATION_V1",
            artifact_version="1.0.0",
            schema_version=policy.reference_schema_version,
            artifact_sha256="c" * 64,
            status="ACTIVE",
            sealed=True,
        ),
    )
    spec = P2AttributionSpec(
        attribution_spec_id=profile.attribution_spec_id,
        attribution_spec_version=profile.attribution_spec_version,
        model_plugin=profile.model_plugin,
        model_plugin_version=profile.model_plugin_version,
        uncertainty_method=profile.uncertainty_method,
        uncertainty_level=profile.uncertainty_level,
        binding=P2ArtifactBinding(
            context_artifact_id=_u("attribution-spec-artifact"),
            object_ref_id=_u("attribution-spec-object"),
            artifact_kind=policy.attribution_artifact_kind,
            logical_key=profile.attribution_spec_id,
            artifact_version=profile.attribution_spec_version,
            schema_version=policy.attribution_schema_version,
            artifact_sha256="d" * 64,
            status="ACTIVE",
            sealed=True,
        ),
    )
    return feature, reference, spec


def _feature(
    *,
    observation: P1ObservationInput,
    feature_spec: P2ArtifactBinding,
    reference: P2ReferenceCondition,
    order: tuple[str, ...],
    values: dict[str, float | None],
    profile: P2ExecutionProfile,
) -> P2FactorFeatureSet:
    return materialize_factor_feature_set(
        source=observation,
        feature_spec=feature_spec,
        factor_order=order,
        factor_values=values,
        world_refs=(_u(f"world:{observation.observation_id}"),),
        confidence=0.9,
        created_at=AS_OF,
        reference_condition_id=reference.reference_condition_id,
        profile=profile,
    )


def _case(
    *,
    points: tuple[Point, ...],
    factor_order: tuple[str, ...],
    target_values: dict[str, float],
    target_observed: float,
    reference_values: dict[str, float],
) -> _Case:
    profile = P2ExecutionProfile.from_canonical()
    feature_spec, reference, attribution_spec = _bindings(profile)
    target = _observation(
        label="target",
        subject_label="target",
        observed_value=target_observed,
    )
    target_feature = _feature(
        observation=target,
        feature_spec=feature_spec,
        reference=reference,
        order=factor_order,
        values=target_values,
        profile=profile,
    )
    rows: list[P2CohortRow] = []
    for label, subject, values, observed in points:
        observation = _observation(
            label=label,
            subject_label=subject,
            observed_value=observed,
        )
        rows.append(
            P2CohortRow(
                observation=observation,
                feature_set=_feature(
                    observation=observation,
                    feature_spec=feature_spec,
                    reference=reference,
                    order=factor_order,
                    values=values,
                    profile=profile,
                ),
            )
        )
    observation_ids = tuple(sorted(row.observation.observation_id for row in rows))
    episode_ids = tuple(sorted({row.observation.episode_id for row in rows}))
    subject_ids = tuple(sorted({row.observation.subject_entity_id for row in rows}))
    data_hash = hashlib.sha256("|".join(observation_ids).encode("ascii")).hexdigest()
    cohort = P2CohortSnapshot(
        dataset_snapshot_id=_u(f"cohort:{data_hash}"),
        snapshot_type=P2AuthorityPolicy.from_canonical().cohort_snapshot_type,
        data_hash=data_hash,
        schema_version="1.6.0",
        frozen=True,
        cohort_spec_id="P2_COHORT_QUALIFICATION_V1",
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
        raw_record_count=len(rows),
        observation_count=len(rows),
        independent_subject_count=len(subject_ids),
        effective_evidence_count=float(len(subject_ids)),
        observation_ids=observation_ids,
        episode_ids=episode_ids,
        subject_ids=subject_ids,
    )
    bundle = build_p2_input_bundle(
        target=target,
        feature_spec=feature_spec,
        reference_condition=reference,
        cohort=cohort,
        attribution_spec=attribution_spec,
        as_of_utc=AS_OF,
    )
    return _Case(
        profile=profile,
        bundle=bundle,
        target_feature_set=target_feature,
        rows=tuple(rows),
        reference_values=reference_values,
        feature_spec=feature_spec,
    )


def _single_points() -> tuple[Point, ...]:
    return tuple(
        (
            f"row-{index}",
            f"subject-{index}",
            {"x": float(index)},
            10.0 + 2.0 * float(index),
        )
        for index in range(1, 6)
    )


def _single_case() -> _Case:
    return _case(
        points=_single_points(),
        factor_order=("x",),
        target_values={"x": 3.0},
        target_observed=17.0,
        reference_values={"x": 2.0},
    )


def _execute(
    case: _Case,
    *,
    rows: tuple[P2CohortRow, ...] | None = None,
    reference_values: dict[str, float] | None = None,
    target_feature_set: P2FactorFeatureSet | None = None,
    factor_effect_semantics: str | None = None,
) -> P2AttributionExecution:
    return execute_p2_attribution(
        bundle=case.bundle,
        target_feature_set=target_feature_set or case.target_feature_set,
        cohort_rows=rows or case.rows,
        reference_factor_values=reference_values or case.reference_values,
        p2_release_id=_u("p2-release"),
        evidence_set_id=_u("p2-evidence"),
        execution_time_utc=AS_OF,
        created_by="M6-TST-003",
        factor_effect_semantics=factor_effect_semantics,
        profile=case.profile,
    )


def _assert_not_identifiable(result: P2AttributionExecution, reason: str) -> None:
    assert result.attribution_run.status == "NOT_IDENTIFIABLE"
    assert result.attribution_run.model_artifact_hash is None
    assert result.model_artifact_json is None
    assert result.adjusted_estimate.status == "NOT_IDENTIFIABLE"
    assert result.adjusted_estimate.adjusted_value is None
    assert result.adjusted_estimate.residual is None
    assert result.adjusted_estimate.uncertainty_lower is None
    assert result.adjusted_estimate.uncertainty_upper is None
    assert result.adjusted_estimate.factor_effects == ()
    assert result.adjusted_estimate.reason_codes == (reason,)


def test_m6_cap_001_feature_materialization_is_deterministic_and_persistent_shape() -> None:
    case = _single_case()
    first = case.target_feature_set
    second = _feature(
        observation=case.bundle.target,
        feature_spec=case.feature_spec,
        reference=case.bundle.reference_condition,
        order=("x",),
        values={"x": 3.0},
        profile=case.profile,
    )
    assert first.factor_feature_set_id == second.factor_feature_set_id
    assert first.input_hash == second.input_hash
    assert first.coverage == 1.0
    assert first.missing_mapping() == {"x": False}
    assert set(first.as_record()) == {
        "factor_feature_set_id",
        "feature_spec_id",
        "feature_spec_version",
        "source_observation_id",
        "reference_condition_id",
        "feature_values",
        "missing_mask",
        "world_refs",
        "coverage",
        "confidence",
        "input_hash",
        "created_at",
    }

    missing = materialize_factor_feature_set(
        source=case.bundle.target,
        feature_spec=case.feature_spec,
        factor_order=("x", "z"),
        factor_values={"x": 3.0, "z": None},
        world_refs=(),
        confidence=0.8,
        created_at=AS_OF,
        reference_condition_id=case.bundle.reference_condition.reference_condition_id,
        profile=case.profile,
    )
    assert missing.coverage == 0.5
    assert missing.missing_mapping() == {"x": False, "z": True}
    assert missing.feature_mapping()["z"] is None


def test_m6_tst_003_single_factor_golden_vector() -> None:
    expected = _section("nominal_single_factor")
    case = _single_case()
    original_observed = case.bundle.target.observed_value
    result = _execute(case)
    estimate = result.adjusted_estimate

    assert estimate.status == expected["expected_status"]
    assert estimate.adjusted_value == float(cast(int, expected["expected_adjusted_value"]))
    assert estimate.residual == float(cast(int, expected["expected_residual"]))
    assert estimate.factor_effect_mapping() == {"x": -2.0}
    assert estimate.uncertainty_lower == 15.0
    assert estimate.uncertainty_upper == 15.0
    assert estimate.claim_level == expected["expected_claim_level"]
    assert estimate.reason_codes == ()
    assert case.bundle.target.observed_value == original_observed
    assert result.attribution_run.model_artifact_hash is not None
    assert len(result.attribution_run.model_artifact_hash) == 64
    assert result.model_artifact_json is not None
    run_record = result.attribution_run.as_record()
    estimate_record = estimate.as_record()
    assert run_record["status"] == "IDENTIFIABLE"
    assert set(run_record) == {
        "attribution_run_id",
        "attribution_spec_id",
        "attribution_spec_version",
        "model_plugin",
        "model_plugin_version",
        "training_dataset_snapshot_id",
        "reference_condition_id",
        "status",
        "diagnostics",
        "model_artifact_uri",
        "model_artifact_hash",
        "started_at",
        "completed_at",
        "created_by",
    }
    assert estimate_record["source_observation_id"] == case.bundle.target.observation_id
    assert set(estimate_record) == {
        "estimate_id",
        "source_observation_id",
        "attribution_run_id",
        "aircraft_id",
        "capability_type",
        "reference_condition_id",
        "adjusted_value",
        "unit",
        "uncertainty_lower",
        "uncertainty_upper",
        "residual",
        "factor_effects",
        "claim_level",
        "status",
        "evidence_set_id",
        "estimate_time",
        "created_at",
        "supersedes_estimate_id",
    }
    artifact = json.loads(cast(str, result.model_artifact_json))
    assert isinstance(artifact, dict)
    required_artifact_fields = {
        "profile_id",
        "profile_version",
        "attribution_spec_id",
        "attribution_spec_version",
        "model_plugin",
        "model_plugin_version",
        "factor_order",
        "cohort_snapshot_id",
        "cohort_data_hash",
        "reference_condition_id",
        "reference_artifact_sha256",
        "feature_spec_id",
        "feature_spec_version",
        "feature_spec_sha256",
        "as_of_utc",
        "scaling",
        "coefficients",
        "diagnostics",
        "jackknife_adjusted_values",
    }
    assert required_artifact_fields <= set(artifact)


def test_m6_tst_003_two_factor_subject_balanced_golden_vector() -> None:
    expected = _section("nominal_two_factor")
    points: tuple[Point, ...] = (
        ("a", "a", {"x": 1.0, "z": 1.0}, 10.0),
        ("b", "b", {"x": 2.0, "z": 1.0}, 12.0),
        ("c", "c", {"x": 1.0, "z": 2.0}, 13.0),
        ("d", "d", {"x": 2.0, "z": 3.0}, 18.0),
        ("e", "e", {"x": 3.0, "z": 2.0}, 17.0),
        ("f", "f", {"x": 4.0, "z": 4.0}, 25.0),
    )
    case = _case(
        points=points,
        factor_order=("x", "z"),
        target_values={"x": 2.0, "z": 2.0},
        target_observed=16.0,
        reference_values={"x": 1.0, "z": 2.0},
    )
    result = _execute(case)
    estimate = result.adjusted_estimate
    assert estimate.status == expected["expected_status"]
    assert estimate.adjusted_value == float(cast(int, expected["expected_adjusted_value"]))
    assert estimate.residual == float(cast(int, expected["expected_residual"]))
    assert estimate.factor_effect_mapping() == {"x": -2.0, "z": 0.0}
    assert estimate.uncertainty_lower == float(
        cast(int, expected["expected_uncertainty_lower"])
    )
    assert estimate.uncertainty_upper == float(
        cast(int, expected["expected_uncertainty_upper"])
    )


def test_m6_tst_003_row_permutation_has_exact_replay_identity() -> None:
    case = _single_case()
    first = _execute(case)
    second = _execute(case, rows=tuple(reversed(case.rows)))
    assert first.attribution_run.run_request_hash == second.attribution_run.run_request_hash
    assert first.attribution_run.model_artifact_hash == second.attribution_run.model_artifact_hash
    assert first.attribution_run.attribution_run_id == second.attribution_run.attribution_run_id
    assert first.adjusted_estimate.estimate_id == second.adjusted_estimate.estimate_id
    assert first.adjusted_estimate.logical_hash == second.adjusted_estimate.logical_hash


def test_m6_tst_003_repeated_rows_do_not_increase_subject_weight() -> None:
    base = _single_case()
    duplicate_points = _single_points() + (
        ("row-duplicate", "subject-1", {"x": 1.0}, 12.0),
    )
    duplicated = _case(
        points=duplicate_points,
        factor_order=("x",),
        target_values={"x": 3.0},
        target_observed=17.0,
        reference_values={"x": 2.0},
    )
    base_result = _execute(base)
    duplicate_result = _execute(duplicated)
    assert duplicate_result.adjusted_estimate.adjusted_value == (
        base_result.adjusted_estimate.adjusted_value
    )
    assert duplicate_result.adjusted_estimate.residual == (
        base_result.adjusted_estimate.residual
    )
    assert duplicate_result.adjusted_estimate.factor_effects == (
        base_result.adjusted_estimate.factor_effects
    )


def test_m6_cap_001_tampered_feature_set_hash_is_rejected() -> None:
    case = _single_case()
    tampered = replace(case.target_feature_set, input_hash="e" * 64)
    with pytest.raises(P2GovernanceError) as caught:
        _execute(case, target_feature_set=tampered)
    assert caught.value.code == "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED"


def test_m6_tst_002_missing_factor_and_low_coverage_fail_closed() -> None:
    case = _single_case()
    target = materialize_factor_feature_set(
        source=case.bundle.target,
        feature_spec=case.feature_spec,
        factor_order=("x",),
        factor_values={"x": None},
        world_refs=(),
        confidence=0.9,
        created_at=AS_OF,
        reference_condition_id=case.bundle.reference_condition.reference_condition_id,
        profile=case.profile,
    )
    result = _execute(case, target_feature_set=target)
    _assert_not_identifiable(
        result,
        cast(str, _section("not_identifiable")["missing_factor"]),
    )


def test_m6_tst_002_non_comparable_cohort_fails_closed() -> None:
    case = _single_case()
    first = case.rows[0]
    changed = replace(
        first,
        observation=replace(first.observation, capability_type="OTHER_CAPABILITY"),
    )
    rows = (changed,) + case.rows[1:]
    result = _execute(case, rows=rows)
    _assert_not_identifiable(
        result,
        cast(str, _section("not_identifiable")["non_comparable"]),
    )


def test_m6_tst_002_insufficient_independent_evidence_fails_closed() -> None:
    points = _single_points()[:3]
    case = _case(
        points=points,
        factor_order=("x",),
        target_values={"x": 2.0},
        target_observed=15.0,
        reference_values={"x": 2.0},
    )
    result = _execute(case)
    _assert_not_identifiable(
        result,
        cast(str, _section("not_identifiable")["insufficient_subjects"]),
    )


def test_m6_tst_003_rank_deficient_model_fails_closed() -> None:
    points: tuple[Point, ...] = tuple(
        (
            f"rank-{index}",
            f"rank-{index}",
            {"x": float(index), "z": 2.0 * float(index)},
            10.0 + 2.0 * float(index),
        )
        for index in range(1, 6)
    )
    case = _case(
        points=points,
        factor_order=("x", "z"),
        target_values={"x": 3.0, "z": 6.0},
        target_observed=16.0,
        reference_values={"x": 2.0, "z": 4.0},
    )
    result = _execute(case)
    _assert_not_identifiable(
        result,
        cast(str, _section("not_identifiable")["rank_deficient"]),
    )


def test_m6_tst_003_reference_out_of_support_fails_closed() -> None:
    case = _single_case()
    result = _execute(case, reference_values={"x": 6.0})
    _assert_not_identifiable(
        result,
        cast(str, _section("not_identifiable")["reference_out_of_support"]),
    )


def test_m6_tst_003_jackknife_fold_failure_fails_closed() -> None:
    points: tuple[Point, ...] = (
        ("j1", "j1", {"x": 0.0}, 10.0),
        ("j2", "j2", {"x": 0.0}, 10.0),
        ("j3", "j3", {"x": 0.0}, 10.0),
        ("j4", "j4", {"x": 1.0}, 12.0),
    )
    case = _case(
        points=points,
        factor_order=("x",),
        target_values={"x": 0.0},
        target_observed=10.0,
        reference_values={"x": 0.0},
    )
    result = _execute(case)
    _assert_not_identifiable(
        result,
        cast(str, _section("not_identifiable")["jackknife_fold_failure"]),
    )


def test_m6_tst_002_retrospective_future_information_is_rejected() -> None:
    case = _single_case()
    first = case.rows[0]
    changed = replace(
        first,
        observation=replace(
            first.observation,
            knowledge_time_utc="2026-09-11T00:00:00Z",
        ),
    )
    with pytest.raises(P2GovernanceError) as caught:
        _execute(case, rows=(changed,) + case.rows[1:])
    assert caught.value.code == "FAIL_CLOSED_P2_FUTURE_INFORMATION"


def test_m6_tst_003_same_episode_leakage_is_rejected() -> None:
    case = _single_case()
    first = case.rows[0]
    changed_observation = replace(
        first.observation,
        episode_id=case.bundle.target.episode_id,
    )
    changed = replace(first, observation=changed_observation)
    rows = (changed,) + case.rows[1:]
    snapshot = replace(
        case.bundle.cohort,
        episode_ids=tuple(sorted({row.observation.episode_id for row in rows})),
    )
    bypassed = replace(case, bundle=replace(case.bundle, cohort=snapshot))
    with pytest.raises(P2GovernanceError) as caught:
        _execute(bypassed, rows=rows)
    assert caught.value.code == "FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE"


def test_m6_tst_003_unsupported_causal_label_is_rejected() -> None:
    case = _single_case()
    with pytest.raises(P2GovernanceError) as caught:
        _execute(case, factor_effect_semantics="CAUSAL")
    assert caught.value.code == "FAIL_CLOSED_P2_CAUSAL_EVIDENCE_REQUIRED"


def test_m6_cap_004_not_identifiable_never_fabricates_adjusted_value() -> None:
    case = _case(
        points=_single_points()[:3],
        factor_order=("x",),
        target_values={"x": 2.0},
        target_observed=15.0,
        reference_values={"x": 2.0},
    )
    result = _execute(case)
    estimate = result.adjusted_estimate
    assert estimate.adjusted_value is None
    assert estimate.uncertainty_lower is None
    assert estimate.uncertainty_upper is None
    assert estimate.factor_effects == ()
    assert estimate.reason_codes
    assert case.bundle.target.observed_value == 15.0


def test_m6_cap_002_run_provenance_binds_exact_snapshot_reference_and_profile() -> None:
    case = _single_case()
    result = _execute(case)
    run = result.attribution_run
    assert run.training_dataset_snapshot_id == case.bundle.cohort.dataset_snapshot_id
    assert run.reference_condition_id == case.bundle.reference_condition.reference_condition_id
    assert run.attribution_spec_id == case.profile.attribution_spec_id
    assert run.attribution_spec_version == case.profile.attribution_spec_version
    assert run.model_plugin == case.profile.model_plugin
    assert run.model_plugin_version == case.profile.model_plugin_version
    assert run.model_artifact_uri is None
    assert run.model_artifact_hash is not None
    diagnostics = run.diagnostics()
    assert diagnostics["factor_effect_semantics"] == "MODEL_CONDITIONED_ASSOCIATION"
    assert diagnostics["claim_level"] == "ASSOCIATION_ONLY"
    assert diagnostics["reason_codes"] == []
