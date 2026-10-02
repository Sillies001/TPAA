from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from tpaa_assessment import P4AssessmentRevision
from tpaa_capability import (
    P3CapabilityEstimate,
    P6CapabilityTrainingRow,
    P6FactualSourceRevision,
    P6ForecastExecutionProfile,
    P6ManagedModelObject,
    assess_p6_training_applicability,
    build_p6_forecast_request_binding,
    build_p6_input_snapshot,
    execute_p6_forecast,
    execute_p6_model_training,
    materialize_p6_model_datasets,
    validate_p6_managed_model_object,
)
from tpaa_context.p6_governance import P6GovernanceError
from tpaa_longitudinal import InMemoryP6ReplayRepository
from tpaa_storage.object_seal import LocalSealedObjectFlow
from tpaa_storage.object_store import LocalObjectStore

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "fixtures" / "m9" / "p6_model_forecast_golden.json"

AIRCRAFT = str(UUID(int=100, version=4))
TWIN = str(UUID(int=101, version=4))
REFERENCE = str(UUID(int=102, version=4))
CONFIG = str(UUID(int=103, version=4))
PROFILE_SHA = "6a064762b4edde3448b25e5b74384708745793acc863a8adfbfad40fc7651394"


def _uuid(seed: int) -> str:
    return str(UUID(int=seed, version=4))


def _estimate(
    index: int,
    *,
    value: float | None = None,
    validity_status: str = "IN_DOMAIN",
) -> P3CapabilityEstimate:
    numeric = 9.0 + index if value is None and validity_status == "IN_DOMAIN" else value
    if numeric is None:
        lower: float | None = None
        upper: float | None = None
    else:
        lower = numeric - 0.5
        upper = numeric + 0.5
    return P3CapabilityEstimate(
        estimate_id=_uuid(1000 + index),
        twin_revision_id=TWIN,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        condition_point={
            "session_order": index,
            "reference_condition_id": REFERENCE,
        },
        value=numeric,
        unit="1",
        uncertainty={
            "lower": lower,
            "upper": upper,
            "surface_id": _uuid(9000),
            "surface_dataset_hash": "b" * 64,
        },
        validity_domain_status=validity_status,
        claim_level="REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        as_of_time=f"2026-09-{index:02d}T12:00:00Z",
        created_at=f"2026-09-{index:02d}T12:00:00Z",
    )


def _p4(
    estimate: P3CapabilityEstimate,
    index: int,
    *,
    approval_state: str = "APPROVED",
    created_at_utc: str | None = None,
) -> P4AssessmentRevision:
    lower_raw = estimate.uncertainty.get("lower")
    upper_raw = estimate.uncertainty.get("upper")
    lower = None if lower_raw is None else float(lower_raw)
    upper = None if upper_raw is None else float(upper_raw)
    created = created_at_utc or f"2026-09-{index:02d}T13:00:00Z"
    return P4AssessmentRevision(
        actor_assessment_id=_uuid(2000 + index),
        subject_context_id=_uuid(6000 + index),
        subject_key=f"SUBJECT-{index}",
        actor_id=_uuid(7000),
        role_code="PILOT",
        seat_code="FRONT",
        function_code=None,
        session_id=_uuid(3000 + index),
        episode_id=_uuid(4000 + index),
        aircraft_id=AIRCRAFT,
        twin_revision_id=TWIN,
        p3_estimate_id=estimate.estimate_id,
        assessment_spec_id="P4_ASSESSMENT_SPEC:TRAINING",
        assessment_spec_version="1.0.0",
        role_model_version="1.0.0",
        world_refs=(),
        machine_evidence_ids=(),
        instructor_annotation_ids=(),
        score=None,
        grade=None,
        status=approval_state,
        confidence=0.9,
        evidence_set_id=_uuid(8000 + index),
        created_at_utc=created,
        supersedes_id=None,
        approval_state=approval_state,
        p3_claim_level=estimate.claim_level,
        p3_validity_status=estimate.validity_domain_status,
        p3_as_of_utc=estimate.as_of_time,
        uncertainty_lower=lower,
        uncertainty_upper=upper,
        logical_content_hash=f"{index:x}" * 64,
    )


def _row(
    index: int,
    *,
    value: float | None = None,
    validity_status: str = "IN_DOMAIN",
) -> P6CapabilityTrainingRow:
    estimate = _estimate(
        index,
        value=value,
        validity_status=validity_status,
    )
    return P6CapabilityTrainingRow(
        estimate=estimate,
        p4_revision=_p4(estimate, index),
        aircraft_id=AIRCRAFT,
        configuration_snapshot_id=CONFIG,
        session_order_assignment_id=_uuid(5000 + index),
        session_order=index,
    )


def _rows(count: int = 4) -> tuple[P6CapabilityTrainingRow, ...]:
    return tuple(_row(index) for index in range(1, count + 1))


def _golden() -> dict[str, object]:
    raw: object = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def _model(
    rows: tuple[P6CapabilityTrainingRow, ...],
    *,
    as_of_utc: str = "2026-09-04T18:00:00Z",
    trained_at_utc: str = "2026-09-04T19:00:00Z",
    supersedes_model_id: str | None = None,
):
    return execute_p6_model_training(
        rows,
        as_of_utc=as_of_utc,
        trained_at_utc=trained_at_utc,
        supersedes_model_id=supersedes_model_id,
    )


def _managed(build, *, sealed_at_utc: str = "2026-09-04T19:30:00Z"):
    return P6ManagedModelObject(
        object_ref_id=build.model.model_object_ref_id,
        managed_uri=build.model.model_artifact_uri,
        artifact_sha256=build.model.model_artifact_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
        sealed_at_utc=sealed_at_utc,
    )


def _snapshot_and_request(
    build,
    *,
    availability_status: str = "AVAILABLE",
    reason_codes: tuple[str, ...] = (),
    target_code: str | None = None,
    horizon_spec: dict[str, object] | None = None,
):
    last_row = build.datasets.final_refit_rows[-1]
    snapshot = build_p6_input_snapshot(
        factual_sources=(
            P6FactualSourceRevision(
                phase="P4",
                revision_id=last_row.p4_revision.actor_assessment_id,
                publication_status="PUBLISHED",
                knowledge_time_utc=last_row.p4_revision.created_at_utc,
            ),
        ),
        target_scope="SUBJECT",
        subject_or_composition_ref=AIRCRAFT,
        forecast_origin_utc="2026-09-04T20:00:00Z",
        as_of_utc="2026-09-05T00:00:00Z",
        availability_status=availability_status,
        reason_codes=reason_codes,
    )
    profile = P6ForecastExecutionProfile.from_canonical()
    request = build_p6_forecast_request_binding(
        input_snapshot=snapshot,
        forecast_spec_id="P6_P3_CAPABILITY_NEXT_SESSION",
        forecast_spec_version="1.0.0",
        target_code=target_code or profile.target_code,
        horizon_spec=horizon_spec
        or {
            "type": "NEXT_SESSION_ORDER",
            "steps": 1,
            "target_session_order": build.target_session_order,
        },
        capability_model_id=build.model.capability_model_id,
        model_profile_id=profile.profile_id,
        model_profile_version=profile.profile_version,
        training_dataset_snapshot_id=build.model.training_dataset_snapshot_id,
        validation_dataset_snapshot_id=build.model.validation_dataset_snapshot_id,
        assumption_profile_id="P6_ASSUMPTION_PROFILE:TRAINING_CONTINUITY",
        assumption_profile_version="1.0.0",
    )
    return snapshot, request


def _forecast(build, managed):
    snapshot, request = _snapshot_and_request(build)
    result = execute_p6_forecast(
        request=request,
        input_snapshot=snapshot,
        model_build=build,
        managed_object=managed,
        published_at_utc="2026-09-05T00:10:00Z",
    )
    return snapshot, request, result


def test_m9_batch2_profile_and_linear_case_match_static_golden() -> None:
    golden = _golden()
    profile = P6ForecastExecutionProfile.from_canonical()
    assert profile.profile_sha256 == PROFILE_SHA == golden["profile_sha256"]
    rows = _rows()
    applicability = assess_p6_training_applicability(
        rows,
        as_of_utc="2026-09-04T18:00:00Z",
        profile=profile,
    )
    assert applicability.status == "APPLICABLE"
    assert (
        applicability.applicability_evidence_id
        == golden["applicability_evidence_id"]
    )
    build = _model(rows)
    assert build.datasets.training.dataset_snapshot_id == (
        golden["training_dataset_snapshot_id"]
    )
    assert build.datasets.training.data_hash == golden["training_dataset_hash"]
    assert build.datasets.validation.dataset_snapshot_id == (
        golden["validation_dataset_snapshot_id"]
    )
    assert build.datasets.validation.data_hash == golden["validation_dataset_hash"]
    assert build.uncertainty.calibration_evidence_id == (
        golden["calibration_evidence_id"]
    )
    assert build.model.model_artifact_hash == golden["model_artifact_hash"]
    assert build.model.capability_model_id == golden["capability_model_id"]
    assert build.model.model_object_ref_id == golden["model_object_ref_id"]
    expected_model = golden["model"]
    assert isinstance(expected_model, dict)
    assert build.intercept == expected_model["intercept"]
    assert build.slope == expected_model["slope"]
    assert build.uncertainty.half_width == expected_model["uncertainty_half_width"]
    assert build.target_session_order == expected_model["target_session_order"]
    snapshot, request, result = _forecast(build, _managed(build))
    assert snapshot.input_snapshot_id == golden["input_snapshot_id"]
    assert request.forecast_request_id == golden["forecast_request_id"]
    assert result.forecast_run_id == golden["forecast_run_id"]
    assert result.forecast_result_id == golden["forecast_result_id"]
    assert result.logical_content_hash == golden["forecast_logical_content_hash"]
    expected_forecast = golden["forecast"]
    assert isinstance(expected_forecast, dict)
    assert result.applicability_status == expected_forecast["applicability_status"]
    assert result.distribution["point"] == expected_forecast["point"]
    assert result.distribution["lower"] == expected_forecast["lower"]
    assert result.distribution["upper"] == expected_forecast["upper"]
    assert result.threshold_probabilities == expected_forecast[
        "threshold_probabilities"
    ]


def test_m9_batch2_input_order_is_deterministic_for_model_and_projection() -> None:
    rows = _rows()
    first = _model(rows)
    second = _model(tuple(reversed(rows)))
    assert first.datasets.training.data_hash == second.datasets.training.data_hash
    assert first.datasets.validation.data_hash == second.datasets.validation.data_hash
    assert first.artifact_bytes == second.artifact_bytes
    assert first.model.capability_model_id == second.model.capability_model_id
    _, request_a, forecast_a = _forecast(first, _managed(first))
    _, request_b, forecast_b = _forecast(second, _managed(second))
    assert request_a.forecast_request_id == request_b.forecast_request_id
    assert forecast_a.forecast_result_id == forecast_b.forecast_result_id
    assert forecast_a.logical_content_hash == forecast_b.logical_content_hash


def test_m9_batch2_training_and_validation_snapshots_are_exact_and_disjoint() -> None:
    datasets = materialize_p6_model_datasets(
        _rows(),
        as_of_utc="2026-09-04T18:00:00Z",
    )
    assert datasets.training.frozen is True
    assert datasets.validation.frozen is True
    assert datasets.training.snapshot_type == "P6_MODEL_TRAINING"
    assert datasets.validation.snapshot_type == "P6_MODEL_VALIDATION"
    assert len(datasets.training.p3_estimate_ids) == 3
    assert len(datasets.validation.p3_estimate_ids) == 1
    assert not (
        set(datasets.training.p3_estimate_ids)
        & set(datasets.validation.p3_estimate_ids)
    )


def test_m9_batch2_model_artifact_requires_exact_sealed_active_object(
    tmp_path: Path,
) -> None:
    build = _model(_rows())
    flow = LocalSealedObjectFlow(LocalObjectStore(tmp_path))
    stored = flow.seal(
        flow.stage(
            sealed_uri=build.model.model_artifact_uri,
            data=build.artifact_bytes,
            operation_id="m9-p6-model",
        )
    )
    managed = P6ManagedModelObject(
        object_ref_id=build.model.model_object_ref_id,
        managed_uri=stored.logical_uri,
        artifact_sha256=stored.artifact_sha256,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
        sealed_at_utc="2026-09-04T19:30:00Z",
    )
    assert validate_p6_managed_model_object(
        build.model,
        managed,
        as_of_utc="2026-09-05T00:00:00Z",
    ) == managed
    with pytest.raises(P6GovernanceError) as mismatch:
        validate_p6_managed_model_object(
            build.model,
            replace(managed, artifact_sha256="0" * 64),
            as_of_utc="2026-09-05T00:00:00Z",
        )
    assert mismatch.value.code == "FAIL_CLOSED_P6_MODEL_HASH_MISMATCH"


def test_m9_batch2_out_of_domain_row_is_excluded_never_zero_filled() -> None:
    rows = list(_rows())
    out_estimate = replace(
        rows[-1].estimate,
        value=None,
        validity_domain_status="OUT_OF_DOMAIN",
        uncertainty={
            "lower": None,
            "upper": None,
            "surface_id": _uuid(9000),
            "surface_dataset_hash": "b" * 64,
        },
    )
    rows[-1] = replace(
        rows[-1],
        estimate=out_estimate,
        p4_revision=replace(
            rows[-1].p4_revision,
            p3_validity_status="OUT_OF_DOMAIN",
            uncertainty_lower=None,
            uncertainty_upper=None,
        ),
    )
    applicability = assess_p6_training_applicability(
        tuple(rows),
        as_of_utc="2026-09-04T18:00:00Z",
    )
    assert applicability.status == "INSUFFICIENT_EVIDENCE"
    assert out_estimate.estimate_id in applicability.excluded_p3_estimate_ids
    with pytest.raises(P6GovernanceError) as blocked:
        materialize_p6_model_datasets(
            tuple(rows),
            as_of_utc="2026-09-04T18:00:00Z",
        )
    assert blocked.value.code == "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED"


def test_m9_batch2_missing_uncertainty_and_future_context_fail_closed() -> None:
    rows = list(_rows())
    bad_estimate = replace(
        rows[-1].estimate,
        uncertainty={
            "lower": None,
            "upper": None,
            "surface_id": _uuid(9000),
            "surface_dataset_hash": "b" * 64,
        },
    )
    bad_uncertainty_row = replace(
        rows[-1],
        estimate=bad_estimate,
        p4_revision=replace(
            rows[-1].p4_revision,
            uncertainty_lower=None,
            uncertainty_upper=None,
        ),
    )
    with pytest.raises(P6GovernanceError) as uncertainty:
        assess_p6_training_applicability(
            (*rows[:-1], bad_uncertainty_row),
            as_of_utc="2026-09-04T18:00:00Z",
        )
    assert uncertainty.value.code == "FAIL_CLOSED_P6_UNCERTAINTY_REQUIRED"

    future_row = replace(
        rows[-1],
        p4_revision=replace(
            rows[-1].p4_revision,
            created_at_utc="2026-09-05T13:00:00Z",
        ),
    )
    with pytest.raises(P6GovernanceError) as future:
        assess_p6_training_applicability(
            (*rows[:-1], future_row),
            as_of_utc="2026-09-04T18:00:00Z",
        )
    assert future.value.code == "FAIL_CLOSED_P6_FUTURE_INFORMATION"


def test_m9_batch2_unavailable_and_wrong_horizon_never_emit_numeric_zero() -> None:
    build = _model(_rows())
    managed = _managed(build)
    snapshot, request = _snapshot_and_request(
        build,
        availability_status="OUT_OF_DOMAIN",
        reason_codes=("SOURCE_DOMAIN_DRIFT",),
    )
    unavailable = execute_p6_forecast(
        request=request,
        input_snapshot=snapshot,
        model_build=build,
        managed_object=managed,
        published_at_utc="2026-09-05T00:10:00Z",
    )
    assert unavailable.applicability_status == "OUT_OF_DOMAIN"
    assert unavailable.distribution["point"] is None
    assert unavailable.uncertainty["half_width"] is None
    assert unavailable.threshold_probabilities == {}

    snapshot2, request2 = _snapshot_and_request(
        build,
        horizon_spec={
            "type": "NEXT_SESSION_ORDER",
            "steps": 2,
            "target_session_order": 6,
        },
    )
    horizon = execute_p6_forecast(
        request=request2,
        input_snapshot=snapshot2,
        model_build=build,
        managed_object=managed,
        published_at_utc="2026-09-05T00:10:00Z",
    )
    assert horizon.applicability_status == "OUT_OF_DOMAIN"
    assert horizon.distribution["point"] is None


def test_m9_batch2_source_change_creates_new_superseding_model_revision() -> None:
    first = _model(_rows())
    second = _model(
        _rows(5),
        as_of_utc="2026-09-05T18:00:00Z",
        trained_at_utc="2026-09-05T19:00:00Z",
        supersedes_model_id=first.model.capability_model_id,
    )
    assert second.model.capability_model_id != first.model.capability_model_id
    assert second.model.supersedes_model_id == first.model.capability_model_id
    assert second.model.training_dataset_snapshot_id != (
        first.model.training_dataset_snapshot_id
    )
    assert second.model.validation_dataset_snapshot_id != (
        first.model.validation_dataset_snapshot_id
    )


def test_m9_batch2_replay_validation_never_rewrites_original_forecast() -> None:
    build = _model(_rows())
    _, _, forecast = _forecast(build, _managed(build))
    repository = InMemoryP6ReplayRepository()
    repository.add_model(build.model)
    repository.add_forecast(forecast)
    replayed = repository.replay_forecast(
        forecast.forecast_result_id,
        as_of_utc="2026-09-05T01:00:00Z",
    )
    assert replayed == forecast
    original_hash = forecast.logical_content_hash
    with pytest.raises(P6GovernanceError) as future:
        repository.replay_forecast(
            forecast.forecast_result_id,
            as_of_utc="2026-09-04T23:00:00Z",
        )
    assert future.value.code == "FAIL_CLOSED_P6_FUTURE_INFORMATION"

    observed = _estimate(5, value=14.25)
    validation = repository.validate_observed_outcome(
        forecast.forecast_result_id,
        observed,
        validated_at_utc="2026-09-06T00:00:00Z",
    )
    assert validation.projected_value == 14.0
    assert validation.observed_value == 14.25
    assert validation.absolute_error == pytest.approx(0.25)
    assert validation.forecast_logical_content_hash == original_hash
    assert repository.replay_forecast(
        forecast.forecast_result_id,
        as_of_utc="2026-09-06T00:00:00Z",
    ).logical_content_hash == original_hash
    assert repository.validate_observed_outcome(
        forecast.forecast_result_id,
        observed,
        validated_at_utc="2026-09-06T00:00:00Z",
    ) == validation
    assert repository.get_validation(validation.validation_id) == validation
