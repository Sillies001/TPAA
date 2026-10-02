from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tpaa_api import create_m9_app
from tpaa_application import (
    ApplicationService,
    InMemoryM9P6Repository,
    M9ApplicationError,
    M9CounterfactualMutation,
    M9ExactQuery,
    M9ForecastMutation,
    M9ModelReleaseMutation,
    M9RecommendationApprovalMutation,
    M9RecommendationMutation,
    M9WorkspaceQuery,
    M9WorkspaceService,
)
from tpaa_capability import (
    P6ApplicabilityEvidence,
    P6CapabilityTrainingRow,
    P6FactualSourceRevision,
    P6ForecastExecutionProfile,
    P6ManagedModelObject,
    P6ModelBuild,
    P6ModelDatasetBundle,
    P6ModelDatasetSnapshot,
    P6ModelRevision,
    P6UncertaintyCalibrationEvidence,
    build_p6_counterfactual_request_binding,
    build_p6_forecast_request_binding,
    build_p6_input_snapshot,
    execute_p6_counterfactual,
)
from tpaa_context import P6GovernanceError, P6SecurityViewer
from tpaa_gui import build_m9_layered_workspace_model

U = {
    "subject": "11111111-1111-4111-8111-111111111111",
    "p4": "22222222-2222-4222-8222-222222222222",
    "model": "33333333-3333-4333-8333-333333333333",
    "training": "44444444-4444-4444-8444-444444444444",
    "validation": "55555555-5555-4555-8555-555555555555",
    "object": "66666666-6666-4666-8666-666666666666",
    "scenario": "77777777-7777-4777-8777-777777777777",
    "gap": "88888888-8888-4888-8888-888888888888",
    "instructor": "99999999-9999-4999-8999-999999999999",
    "reviewer": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "admin": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
}
H = "a" * 64
AS_OF = "2026-09-10T12:00:00Z"
ROOT = Path(__file__).resolve().parents[2]


def _viewer(
    role: str,
    actor_id: str,
    *,
    validation_only: bool = False,
    export: bool = False,
) -> P6SecurityViewer:
    return P6SecurityViewer(
        role=role,
        actor_id=actor_id,
        scope_match=True,
        validation_only=validation_only,
        privileged_identity_authorized=role == "ADMIN_AUDITOR",
        export_authorized=export,
    )


def _runtime() -> tuple[
    InMemoryM9P6Repository,
    M9WorkspaceService,
    str,
    str,
]:
    profile = P6ForecastExecutionProfile.from_canonical()
    snapshot = build_p6_input_snapshot(
        factual_sources=(
            P6FactualSourceRevision(
                phase="P4",
                revision_id=U["p4"],
                publication_status="PUBLISHED",
                knowledge_time_utc="2026-09-09T10:00:00Z",
            ),
        ),
        target_scope="SUBJECT",
        subject_or_composition_ref=U["subject"],
        forecast_origin_utc="2026-09-10T00:00:00Z",
        as_of_utc=AS_OF,
    )
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
        capability_model_id=U["model"],
        model_profile_id=profile.profile_id,
        model_profile_version=profile.profile_version,
        training_dataset_snapshot_id=U["training"],
        validation_dataset_snapshot_id=U["validation"],
        assumption_profile_id="P6_ASSUMPTION:TRAINING_EVALUATION",
        assumption_profile_version="1.0.0",
    )
    counterfactual_request = build_p6_counterfactual_request_binding(
        input_snapshot=snapshot,
        base_product_refs=(U["p4"],),
        scenario_definition_id=U["scenario"],
        interventions={
            "training_focus": {
                "type": "TRAINING_FOCUS",
                "value": "DEBRIEF_REPEAT",
            }
        },
        held_fixed_assumptions={
            "reference_condition": "UNCHANGED",
            "configuration": "UNCHANGED",
        },
        model_refs=(U["model"],),
        applicability_profile_ref=profile.applicability_profile_ref,
    )
    applicability = P6ApplicabilityEvidence(
        applicability_evidence_id="P6_APPLICABILITY_SHA256:" + H,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        status="APPLICABLE",
        reason_codes=(),
        eligible_p3_estimate_ids=(),
        excluded_p3_estimate_ids=(),
        domain={
            "aircraft_id": U["subject"],
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "reference_condition_id": U["scenario"],
            "unit": "1",
            "configuration_snapshot_id": U["scenario"],
        },
        as_of_utc=AS_OF,
        data_hash=H,
    )
    training = P6ModelDatasetSnapshot(
        dataset_snapshot_id=U["training"],
        snapshot_type="P6_MODEL_TRAINING",
        row_ids=(),
        p3_estimate_ids=(),
        p4_revision_ids=(),
        as_of_utc=AS_OF,
        data_hash=H,
    )
    validation = P6ModelDatasetSnapshot(
        dataset_snapshot_id=U["validation"],
        snapshot_type="P6_MODEL_VALIDATION",
        row_ids=(),
        p3_estimate_ids=(),
        p4_revision_ids=(),
        as_of_utc=AS_OF,
        data_hash=H,
    )
    datasets = P6ModelDatasetBundle(
        applicability=applicability,
        training=training,
        validation=validation,
        eligible_rows=(),
        training_rows=(),
        validation_row=cast(P6CapabilityTrainingRow, None),
        final_refit_rows=(),
    )
    uncertainty = P6UncertaintyCalibrationEvidence(
        calibration_evidence_id="P6_UNCERTAINTY_SHA256:" + H,
        profile_ref=profile.uncertainty_profile_ref,
        p3_input_half_width_max=0.5,
        holdout_absolute_error=0.25,
        final_refit_residual_mad=0.5,
        half_width=0.5,
        status="CALIBRATED",
        data_hash=H,
    )
    model = P6ModelRevision(
        capability_model_id=U["model"],
        model_spec_id=profile.model_spec_id,
        model_spec_version=profile.model_spec_version,
        subject_type="AIRCRAFT",
        subject_id=U["subject"],
        capability_type="KINEMATIC_ENERGY_CONTROL",
        training_dataset_snapshot_id=U["training"],
        validation_dataset_snapshot_id=U["validation"],
        plugin_name=profile.plugin_name,
        plugin_version=profile.plugin_version,
        model_artifact_uri=(
            "tpaa-object://p6-capability/models/"
            f"{U['model']}.json"
        ),
        model_artifact_hash=H,
        model_object_ref_id=U["object"],
        validity_domain={
            "aircraft_id": U["subject"],
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "reference_condition_id": U["scenario"],
            "unit": "1",
            "configuration_snapshot_id": U["scenario"],
        },
        validation_metrics={"status": "VALIDATED"},
        applicability_profile_ref=profile.applicability_profile_ref,
        uncertainty_profile_ref=profile.uncertainty_profile_ref,
        status="VALIDATED",
        trained_at="2026-09-09T12:00:00Z",
        published_at=None,
        supersedes_model_id=None,
    )
    build = P6ModelBuild(
        model=model,
        artifact={"schema": "TEST"},
        artifact_bytes=b"{}",
        datasets=datasets,
        applicability=applicability,
        uncertainty=uncertainty,
        intercept=10.0,
        slope=1.0,
        session_order_origin=1,
        target_session_order=5,
        fit_row_ids=(),
    )
    managed = P6ManagedModelObject(
        object_ref_id=U["object"],
        managed_uri=model.model_artifact_uri,
        artifact_sha256=H,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
        sealed_at_utc="2026-09-09T12:30:00Z",
    )
    repo = InMemoryM9P6Repository()
    repo.register_input(snapshot)
    repo.register_forecast_request(forecast_request)
    repo.register_counterfactual_request(counterfactual_request)
    repo.register_model_build(build, managed)
    service = M9WorkspaceService(repo)
    return (
        repo,
        service,
        forecast_request.forecast_request_id,
        counterfactual_request.counterfactual_request_id,
    )


def _candidate_products() -> tuple[
    InMemoryM9P6Repository,
    M9WorkspaceService,
    str,
    str,
    str,
]:
    repo, service, forecast_request_id, counterfactual_request_id = _runtime()
    instructor = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    forecast_result = service.run_forecast(
        M9ForecastMutation(
            request_id="req-forecast-1",
            forecast_request_id=forecast_request_id,
            published_at_utc="2026-09-10T13:00:00Z",
            viewer=instructor,
        )
    )
    counterfactual_result = service.run_counterfactual(
        M9CounterfactualMutation(
            request_id="req-counterfactual-1",
            counterfactual_request_id=counterfactual_request_id,
            created_at_utc="2026-09-10T13:10:00Z",
            viewer=instructor,
        )
    )
    recommendation_result = service.create_recommendation(
        M9RecommendationMutation(
            request_id="req-recommendation-1",
            subject_id=U["subject"],
            recommendation_spec_id="P6_TRAINING_ADVISORY",
            recommendation_spec_version="1.0.0",
            source_forecast_result_ids=(
                cast(str, forecast_result["forecast_result_id"]),
            ),
            source_counterfactual_run_ids=(
                cast(str, counterfactual_result["counterfactual_run_id"]),
            ),
            objective_constraints={
                "objective": "TRAINING_PROFICIENCY",
                "constraint": "EVALUATION_ONLY",
            },
            allowed_action_space={
                "mode": "TRAINING_SESSION",
                "options": ["DEBRIEF_REPEAT", "SIMULATOR_PRACTICE"],
            },
            rationale={"basis": "P6_PROJECTION_EVIDENCE"},
            source_gap_refs=(U["gap"],),
            proposed_training_items={
                "items": ["DEBRIEF_REVIEW", "SIMULATOR_PRACTICE"]
            },
            created_at_utc="2026-09-10T13:20:00Z",
            viewer=instructor,
        )
    )
    return (
        repo,
        service,
        cast(str, forecast_result["forecast_result_id"]),
        cast(str, counterfactual_result["counterfactual_run_id"]),
        cast(str, recommendation_result["recommendation_id"]),
    )


def test_m9_batch3_exact_projection_graph_is_deterministic_and_non_causal() -> None:
    _, service_a, forecast_a, counterfactual_a, recommendation_a = (
        _candidate_products()
    )
    _, service_b, forecast_b, counterfactual_b, recommendation_b = (
        _candidate_products()
    )
    assert forecast_a == forecast_b
    assert counterfactual_a == counterfactual_b
    assert recommendation_a == recommendation_b
    viewer = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    counterfactual = service_a.counterfactual(
        M9ExactQuery(counterfactual_a, viewer)
    )
    assert counterfactual["causal_claim_level"] == (
        "SCENARIO_PROJECTION_NON_CAUSAL"
    )
    assert counterfactual["identifiability_status"] == (
        "SCENARIO_ONLY_NON_CAUSAL"
    )
    assert counterfactual["projection_class"] == (
        "P6_COUNTERFACTUAL_PROJECTION"
    )
    assert counterfactual["uncertainty"]["numeric_effect"] is None


def test_m9_batch3_recommendation_is_advisory_and_approval_is_separated() -> None:
    _, service, _, _, recommendation_id = _candidate_products()
    instructor = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    reviewer = _viewer("MODEL_REVIEWER", U["reviewer"], validation_only=True)
    with pytest.raises(M9ApplicationError):
        service.approve_recommendation(
            M9RecommendationApprovalMutation(
                recommendation_id=recommendation_id,
                request_id="req-reviewer-denied",
                target_state="IN_REVIEW",
                reason="review",
                created_at_utc="2026-09-10T13:30:00Z",
                viewer=reviewer,
            )
        )
    in_review = service.approve_recommendation(
        M9RecommendationApprovalMutation(
            recommendation_id=recommendation_id,
            request_id="req-rec-review",
            target_state="IN_REVIEW",
            reason="training review",
            created_at_utc="2026-09-10T13:30:00Z",
            viewer=instructor,
        )
    )
    approved = service.approve_recommendation(
        M9RecommendationApprovalMutation(
            recommendation_id=cast(str, in_review["recommendation_id"]),
            request_id="req-rec-approve",
            target_state="APPROVED",
            reason="training approval",
            created_at_utc="2026-09-10T13:40:00Z",
            viewer=instructor,
        )
    )
    released = service.approve_recommendation(
        M9RecommendationApprovalMutation(
            recommendation_id=cast(str, approved["recommendation_id"]),
            request_id="req-rec-release",
            target_state="RELEASED",
            reason="training advisory release",
            created_at_utc="2026-09-10T13:50:00Z",
            viewer=instructor,
        )
    )
    projection = service.recommendation(
        M9ExactQuery(cast(str, released["recommendation_id"]), instructor)
    )
    assert projection["projection_class"] == "P6_TRAINING_ADVISORY"
    assert projection["approval_state"] == "RELEASED"
    assert projection["release_state"] == "CANDIDATE_NOT_ADMITTED"
    assert "subject_id" in projection


def test_m9_batch3_model_release_is_model_reviewer_only_and_idempotent() -> None:
    _, service, _, _ = _runtime()
    instructor = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    reviewer = _viewer("MODEL_REVIEWER", U["reviewer"], validation_only=True)
    with pytest.raises(M9ApplicationError):
        service.release_model(
            M9ModelReleaseMutation(
                capability_model_id=U["model"],
                request_id="req-model-denied",
                published_at_utc="2026-09-10T13:00:00Z",
                viewer=instructor,
            )
        )
    command = M9ModelReleaseMutation(
        capability_model_id=U["model"],
        request_id="req-model-release",
        published_at_utc="2026-09-10T13:00:00Z",
        viewer=reviewer,
    )
    first = service.release_model(command)
    second = service.release_model(command)
    assert first["status"] == "PUBLISHED"
    assert second == first
    published_repo, published_service, request_id, _ = _runtime()
    published_service.release_model(command)
    forecast = published_service.run_forecast(
        M9ForecastMutation(
            request_id="req-published-model-forecast",
            forecast_request_id=request_id,
            published_at_utc="2026-09-10T14:00:00Z",
            viewer=_viewer("INSTRUCTOR_EVALUATOR", U["instructor"]),
        )
    )
    assert forecast["applicability_status"] == "APPLICABLE"
    assert published_repo.exact_model_build(U["model"]).model.status == "PUBLISHED"


def test_m9_batch3_command_and_causal_upgrades_fail_closed() -> None:
    repo, service, _, counterfactual_request_id = _runtime()
    request = repo.exact_counterfactual_request(counterfactual_request_id)
    snapshot = repo.exact_input(request.input_snapshot_id)
    models = tuple(
        repo.exact_model_build(model_id).model
        for model_id in request.model_refs
    )
    with pytest.raises(P6GovernanceError) as causal:
        execute_p6_counterfactual(
            request=request,
            input_snapshot=snapshot,
            models=models,
            created_at_utc="2026-09-10T13:00:00Z",
            causal_claim_level="CAUSAL_EFFECT",
        )
    assert causal.value.code == "FAIL_CLOSED_P6_CAUSAL_CLAIM_NOT_AUTHORIZED"

    _, command_service, forecast_id, counterfactual_id, _ = (
        _candidate_products()
    )
    instructor = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    with pytest.raises(M9ApplicationError) as command:
        command_service.create_recommendation(
            M9RecommendationMutation(
                request_id="req-command-upgrade",
                subject_id=U["subject"],
                recommendation_spec_id="P6_TRAINING_ADVISORY",
                recommendation_spec_version="1.0.0",
                source_forecast_result_ids=(forecast_id,),
                source_counterfactual_run_ids=(counterfactual_id,),
                objective_constraints={"objective": "TRAINING"},
                allowed_action_space={"mode": "TACTICAL_COMMAND"},
                rationale={"basis": "projection"},
                source_gap_refs=(),
                proposed_training_items={"items": ["TRAINING"]},
                created_at_utc="2026-09-10T13:30:00Z",
                viewer=instructor,
            )
        )
    assert command.value.code == "FAIL_CLOSED_P6_RECOMMENDATION_COMMAND_UPGRADE"


def test_m9_batch3_workspace_and_gui_keep_fact_and_projection_separate() -> None:
    _, service, forecast_id, counterfactual_id, recommendation_id = (
        _candidate_products()
    )
    viewer = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    payload = service.workspace(
        M9WorkspaceQuery(
            forecast_result_id=forecast_id,
            counterfactual_run_id=counterfactual_id,
            recommendation_id=recommendation_id,
            viewer=viewer,
        )
    )
    model = build_m9_layered_workspace_model(
        payload,
        expected_forecast_result_id=forecast_id,
        expected_counterfactual_run_id=counterfactual_id,
        expected_recommendation_id=recommendation_id,
    )
    assert model.factual_layer == "P1_P5_FACTUAL_HISTORY"
    assert model.business_recompute is False
    assert model.persistence_access is False
    assert model.projection_to_fact_upgrade is False
    assert model.forecast.projection_class == "P6_FORECAST_PROJECTION"
    assert model.forecast.assumptions["assumption_profile_version"] == "1.0.0"
    assert model.counterfactual.assumptions["held_fixed"]
    assert model.counterfactual.projection_class == (
        "P6_COUNTERFACTUAL_PROJECTION"
    )
    assert model.recommendation.projection_class == "P6_TRAINING_ADVISORY"


def test_m9_batch3_pre_exit_export_and_admin_business_approval_fail_closed() -> None:
    _, service, forecast_id, counterfactual_id, recommendation_id = (
        _candidate_products()
    )
    admin = _viewer("ADMIN_AUDITOR", U["admin"], export=True)
    with pytest.raises(M9ApplicationError) as export:
        service.export_exact(
            M9WorkspaceQuery(
                forecast_result_id=forecast_id,
                counterfactual_run_id=counterfactual_id,
                recommendation_id=recommendation_id,
                viewer=admin,
            )
        )
    assert export.value.code == "M9_P6_NOT_ADMITTED"
    with pytest.raises(M9ApplicationError):
        service.approve_recommendation(
            M9RecommendationApprovalMutation(
                recommendation_id=recommendation_id,
                request_id="req-admin-approval",
                target_state="IN_REVIEW",
                reason="admin privilege must not imply business approval",
                created_at_utc="2026-09-10T13:30:00Z",
                viewer=admin,
            )
        )


class _UnusedStorageStatus:
    def execute(self):
        raise AssertionError("storage status is not part of M9 API contract test")


def test_m9_batch3_api_uses_exact_ids_and_application_service_only() -> None:
    repo, workspace, forecast_id, counterfactual_id, recommendation_id = (
        _candidate_products()
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorageStatus(),
        m9_workspace=workspace,
    )
    viewer = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    client = TestClient(
        create_m9_app(
            application,
            principal_resolver=lambda request: viewer,
        )
    )
    forecast_request_id = repo.exact_forecast(
        forecast_id
    ).forecast_request_id
    counterfactual_request_id = repo.exact_counterfactual(
        counterfactual_id
    ).counterfactual_request_id
    request_response = client.get(
        f"/m9/forecast-requests/{forecast_request_id}"
    )
    assert request_response.status_code == 200
    assert request_response.json()["forecast_request_id"] == forecast_request_id
    cf_request_response = client.get(
        f"/m9/counterfactual-requests/{counterfactual_request_id}"
    )
    assert cf_request_response.status_code == 200
    response = client.get(f"/m9/forecasts/{forecast_id}")
    assert response.status_code == 200
    assert response.json()["forecast_result_id"] == forecast_id
    alias = client.get("/m9/forecasts/LATEST")
    assert alias.status_code == 404
    workspace_response = client.get(
        f"/m9/workspace/forecast/{forecast_id}"
        f"/counterfactual/{counterfactual_id}"
        f"/recommendation/{recommendation_id}"
    )
    assert workspace_response.status_code == 200
    body = workspace_response.json()
    assert body["presentation_contract"] == {
        "business_recompute": False,
        "persistence_access": False,
        "projection_to_fact_upgrade": False,
    }


def test_m9_batch3_security_audit_excludes_sensitive_payloads() -> None:
    _, service, forecast_id, _, _ = _candidate_products()
    viewer = _viewer("INSTRUCTOR_EVALUATOR", U["instructor"])
    service.forecast(M9ExactQuery(forecast_id, viewer))
    events = service.security_events()
    assert events
    serialized = repr(events)
    for forbidden in (
        "training_snapshot_payload",
        "model_artifact_uri",
        "restricted_recommendation_body",
    ):
        assert forbidden not in serialized



def test_m9_batch3_p1_p5_authority_hashes_and_db_schema_remain_immutable() -> None:
    baseline = ROOT / "baseline" / "CB-1.4.0"
    lock = json.loads(
        (baseline / "BASELINE_LOCK.json").read_text(encoding="utf-8")
    )
    assert lock["baseline"]["db_schema"] == "1.6.0"
    entries = {
        row["file"]: row["sha256"]
        for row in lock["artifacts"]
    }
    assert entries["P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json"] == (
        "749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77"
    )
    assert entries["P4_P5_ROLE_PRIVACY_PROFILE.json"] == (
        "99a526cead816010373cdd81cd889d33fa359b5d0b74d87743e51d0f649f1113"
    )
    assert entries["P6_PREDICTION_COUNTERFACTUAL_AUTHORITY.json"] == (
        "a138c97e6c9891f767ee25de8841e2bc9ca899ddf6d09b98b9e4bae73d9be79e"
    )
