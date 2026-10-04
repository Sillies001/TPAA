from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from tools.testing.piqb_b2_p6_resolver_fixture import (
    seed_p6_model_resolver_case,
)
from tpaa_application import (
    DurableP6ModelBuildResolver,
    P6PersistenceError,
    P6PersistenceRepository,
)
from tpaa_assessment.p6_recommendation import build_p6_recommendation
from tpaa_capability import (
    P6ApplicabilityEvidence,
    P6CapabilityTrainingRow,
    P6ContextRef,
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
    execute_p6_forecast,
)
from tpaa_context.p6_governance import canonical_hash
from tpaa_storage import LocalObjectStore, SQLiteDesktopUnitOfWork, bootstrap_sqlite

SUBJECT = "95100000-0000-4000-8000-000000000001"
P4 = "95100000-0000-4000-8000-000000000002"
CONTEXT = "95100000-0000-4000-8000-000000000003"
MODEL = "95100000-0000-4000-8000-000000000004"
OBJECT = "95100000-0000-4000-8000-000000000005"
TRAINING = "95100000-0000-4000-8000-000000000006"
VALIDATION = "95100000-0000-4000-8000-000000000007"
GAP = "95100000-0000-4000-8000-000000000008"
AS_OF = "2026-09-10T12:00:00Z"


def _dataset(snapshot_id: str, snapshot_type: str) -> P6ModelDatasetSnapshot:
    profile = P6ForecastExecutionProfile.from_canonical()
    material = {
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "profile_sha256": profile.profile_sha256,
        "snapshot_type": snapshot_type,
        "row_ids": [],
        "p3_estimate_ids": [],
        "p4_revision_ids": [],
        "as_of_utc": AS_OF,
        "frozen": True,
    }
    return P6ModelDatasetSnapshot(
        dataset_snapshot_id=snapshot_id,
        snapshot_type=snapshot_type,
        row_ids=(),
        p3_estimate_ids=(),
        p4_revision_ids=(),
        as_of_utc=AS_OF,
        data_hash=canonical_hash(material),
    )


def _model_build() -> tuple[P6ModelBuild, P6ManagedModelObject]:
    profile = P6ForecastExecutionProfile.from_canonical()
    training = _dataset(TRAINING, "P6_MODEL_TRAINING")
    validation = _dataset(VALIDATION, "P6_MODEL_VALIDATION")
    artifact = {"schema": "TPAA_PIQB_B2_P6_MODEL_TEST_V1"}
    artifact_bytes = json.dumps(
        artifact,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    applicability = P6ApplicabilityEvidence(
        applicability_evidence_id="P6_APPLICABILITY_SHA256:" + "a" * 64,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        status="APPLICABLE",
        reason_codes=(),
        eligible_p3_estimate_ids=(),
        excluded_p3_estimate_ids=(),
        domain={
            "aircraft_id": SUBJECT,
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "reference_condition_id": CONTEXT,
            "unit": "1",
            "configuration_snapshot_id": CONTEXT,
        },
        as_of_utc=AS_OF,
        data_hash="a" * 64,
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
        calibration_evidence_id="P6_UNCERTAINTY_SHA256:" + "b" * 64,
        profile_ref=profile.uncertainty_profile_ref,
        p3_input_half_width_max=0.5,
        holdout_absolute_error=0.25,
        final_refit_residual_mad=0.5,
        half_width=0.5,
        status="CALIBRATED",
        data_hash="b" * 64,
    )
    model = P6ModelRevision(
        capability_model_id=MODEL,
        model_spec_id=profile.model_spec_id,
        model_spec_version=profile.model_spec_version,
        subject_type="AIRCRAFT",
        subject_id=SUBJECT,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        training_dataset_snapshot_id=TRAINING,
        validation_dataset_snapshot_id=VALIDATION,
        plugin_name=profile.plugin_name,
        plugin_version=profile.plugin_version,
        model_artifact_uri=f"tpaa-object://p6-capability/models/{MODEL}.json",
        model_artifact_hash=artifact_hash,
        model_object_ref_id=OBJECT,
        validity_domain={
            "aircraft_id": SUBJECT,
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "reference_condition_id": CONTEXT,
            "unit": "1",
            "configuration_snapshot_id": CONTEXT,
        },
        validation_metrics={"status": "VALIDATED"},
        applicability_profile_ref=profile.applicability_profile_ref,
        uncertainty_profile_ref=profile.uncertainty_profile_ref,
        status="VALIDATED",
        trained_at="2026-09-10T10:00:00Z",
        published_at=None,
        supersedes_model_id=None,
    )
    build = P6ModelBuild(
        model=model,
        artifact=artifact,
        artifact_bytes=artifact_bytes,
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
        object_ref_id=OBJECT,
        managed_uri=model.model_artifact_uri,
        artifact_sha256=artifact_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
        sealed_at_utc="2026-09-10T10:30:00Z",
    )
    return build, managed


def _input():
    return build_p6_input_snapshot(
        factual_sources=(
            P6FactualSourceRevision(
                phase="P4",
                revision_id=P4,
                publication_status="PUBLISHED",
                knowledge_time_utc="2026-09-10T09:00:00Z",
            ),
        ),
        scenario_context_refs=(
            P6ContextRef(
                context_ref_id=CONTEXT,
                status="ACTIVE",
                knowledge_time_utc="2026-09-10T09:00:00Z",
            ),
        ),
        target_scope="SUBJECT",
        subject_or_composition_ref=SUBJECT,
        forecast_origin_utc="2026-09-10T11:00:00Z",
        as_of_utc=AS_OF,
    )


def test_p6_db18_substrate_survives_sqlite_restart(tmp_path: Path) -> None:
    database = tmp_path / "p6.db"
    object_store = LocalObjectStore(tmp_path / "objects")
    bootstrap_sqlite(database)
    snapshot = _input()
    build, managed = _model_build()
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
        capability_model_id=MODEL,
        model_profile_id=profile.profile_id,
        model_profile_version=profile.profile_version,
        training_dataset_snapshot_id=TRAINING,
        validation_dataset_snapshot_id=VALIDATION,
        assumption_profile_id="P6_ASSUMPTION:TRAINING_EVALUATION",
        assumption_profile_version="1.0.0",
    )
    counterfactual_request = build_p6_counterfactual_request_binding(
        input_snapshot=snapshot,
        base_product_refs=(P4,),
        scenario_definition_id=CONTEXT,
        interventions={
            "training_focus": {
                "type": "TRAINING_FOCUS",
                "value": "DEBRIEF_REPEAT",
            }
        },
        held_fixed_assumptions={"configuration": "UNCHANGED"},
        model_refs=(MODEL,),
        applicability_profile_ref=profile.applicability_profile_ref,
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        repo.register_input(snapshot)
        repo.register_model_build(build, managed)
        repo.register_forecast_request(forecast_request)
        repo.register_counterfactual_request(counterfactual_request)
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        assert repo.exact_input(snapshot.input_snapshot_id) == snapshot
        assert repo.exact_model_revision(MODEL) == build.model
        assert repo.exact_managed_object(MODEL) == managed
        assert repo.exact_forecast_request(
            forecast_request.forecast_request_id
        ) == forecast_request
        assert repo.exact_counterfactual_request(
            counterfactual_request.counterfactual_request_id
        ) == counterfactual_request
        with pytest.raises(P6PersistenceError) as blocked:
            repo.exact_model_build(MODEL)
        assert blocked.value.code == "P6_MODEL_BUILD_DEPENDENCY_BLOCKED"
        uow.commit()


def test_p6_substrate_idempotent_replay_is_exact(tmp_path: Path) -> None:
    database = tmp_path / "p6-replay.db"
    object_store = LocalObjectStore(tmp_path / "objects-replay")
    bootstrap_sqlite(database)
    snapshot = _input()
    build, managed = _model_build()

    for _ in range(2):
        with SQLiteDesktopUnitOfWork(database, write=True) as uow:
            repo = P6PersistenceRepository(
                uow.canonical_rows,
                object_store=object_store,
            )
            repo.register_input(snapshot)
            repo.register_model_build(build, managed)
            uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        repo = P6PersistenceRepository(uow.canonical_rows)
        assert repo.exact_input(snapshot.input_snapshot_id) == snapshot
        assert repo.exact_model_revision(MODEL) == build.model
        uow.commit()

def test_p6_results_survive_sqlite_restart_and_replay(tmp_path: Path) -> None:
    database = tmp_path / "p6-results.db"
    object_store = LocalObjectStore(tmp_path / "objects-results")
    bootstrap_sqlite(database)
    snapshot = _input()
    build, managed = _model_build()
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
        capability_model_id=MODEL,
        model_profile_id=profile.profile_id,
        model_profile_version=profile.profile_version,
        training_dataset_snapshot_id=TRAINING,
        validation_dataset_snapshot_id=VALIDATION,
        assumption_profile_id="P6_ASSUMPTION:TRAINING_EVALUATION",
        assumption_profile_version="1.0.0",
    )
    counterfactual_request = build_p6_counterfactual_request_binding(
        input_snapshot=snapshot,
        base_product_refs=(P4,),
        scenario_definition_id=CONTEXT,
        interventions={
            "training_focus": {
                "type": "TRAINING_FOCUS",
                "value": "DEBRIEF_REPEAT",
            }
        },
        held_fixed_assumptions={"configuration": "UNCHANGED"},
        model_refs=(MODEL,),
        applicability_profile_ref=profile.applicability_profile_ref,
    )
    forecast = execute_p6_forecast(
        request=forecast_request,
        input_snapshot=snapshot,
        model_build=build,
        managed_object=managed,
        published_at_utc="2026-09-10T12:30:00Z",
    )
    counterfactual = execute_p6_counterfactual(
        request=counterfactual_request,
        input_snapshot=snapshot,
        models=(build.model,),
        created_at_utc="2026-09-10T12:40:00Z",
    )
    recommendation = build_p6_recommendation(
        subject_key="SUBJECT-P6",
        subject_id=SUBJECT,
        recommendation_spec_id="P6_TRAINING_ADVISORY",
        recommendation_spec_version="1.0.0",
        source_forecast_result_ids=(forecast.forecast_result_id,),
        source_counterfactual_run_ids=(
            counterfactual.counterfactual_run_id,
        ),
        objective_constraints={
            "objective": "TRAINING_PROFICIENCY",
            "constraint": "EVALUATION_ONLY",
        },
        allowed_action_space={
            "mode": "TRAINING_SESSION",
            "options": ["DEBRIEF_REPEAT"],
        },
        rationale={"basis": "P6_PROJECTION_EVIDENCE"},
        source_gap_refs=(GAP,),
        proposed_training_items={"items": ["DEBRIEF_REVIEW"]},
        applicability_status="APPLICABLE",
        uncertainty={
            "forecast": dict(forecast.uncertainty),
            "counterfactual": dict(counterfactual.uncertainty),
        },
        created_at_utc="2026-09-10T12:50:00Z",
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        repo.register_input(snapshot)
        repo.register_model_build(build, managed)
        repo.register_forecast_request(forecast_request)
        repo.register_counterfactual_request(counterfactual_request)
        repo.register_forecast(forecast)
        repo.register_counterfactual(counterfactual)
        repo.register_recommendation(recommendation)
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        assert repo.exact_forecast(forecast.forecast_result_id) == forecast
        assert repo.exact_counterfactual(
            counterfactual.counterfactual_run_id
        ) == counterfactual
        assert repo.exact_recommendation(
            recommendation.recommendation_id
        ) == recommendation
        uow.commit()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        repo.register_forecast(forecast)
        repo.register_counterfactual(counterfactual)
        repo.register_recommendation(recommendation)
        uow.commit()




def test_p6_model_build_rehydrates_from_durable_p3_p4_rows(
    tmp_path: Path,
) -> None:
    database = tmp_path / "p6-model-resolver.db"
    object_store = LocalObjectStore(tmp_path / "objects-model-resolver")
    bootstrap_sqlite(database)

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        case = seed_p6_model_resolver_case(
            uow.canonical_rows,
            object_store,
        )
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        resolver = DurableP6ModelBuildResolver(uow.canonical_rows)
        repository = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
            model_build_resolver=resolver,
        )
        assert (
            repository.exact_model_build(
                case.build.model.capability_model_id
            )
            == case.build
        )
        uow.commit()
