"""PRCB C5 installed Service/PostgreSQL P1-P6 production-chain qualification."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tpaa_application import (
    JobStatus,
    P2PersistenceRepository,
    P3PersistenceRepository,
    P4P5PersistenceRepository,
    P6PersistenceRepository,
)
from tpaa_ingest import PRODUCTION_FLIGHT_MEDIA_TYPE
from tpaa_observation import allocate_session_release_id
from tpaa_qualification.ed2_p1_request_contract import (
    load_ed2_p1_request_contract,
)
from tpaa_runtime import (
    ProductionPrincipalBinding,
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_service_production_runtime,
    create_service_production_backup,
    restore_service_production_backup,
)
from tpaa_storage import LocalObjectStore, PostgreSQLServiceUnitOfWork
from tpaa_storage.hashing import canonical_request_hash

from .prcb_c5_api_desktop import PRCBC5DesktopApiExpectation
from .prcb_c5_api_service import verify_prcb_c5_service_api
from .prcb_c5_downstream import (
    prepare_prcb_c5_p3,
    prepare_prcb_c5_p4,
    prepare_prcb_c5_p5,
    prepare_prcb_c5_p6,
)
from .prcb_c5_p2 import prepare_prcb_c5_p2_workspace

PRODUCT_VERSION = "1.0.1"
SESSION_ID = "c2000000-0000-4000-8000-000000000001"
CONTEXT_ID = "c2000000-0000-4000-8000-000000000003"
SOURCE_ID = "c2000000-0000-4000-8000-000000000004"
STREAM_ID = "c2000000-0000-4000-8000-000000000005"
ARTIFACT_ID = "c2000000-0000-4000-8000-000000000006"
MODEL_ID = "c2000000-0000-4000-8000-000000000007"
INSTANCE_ID = "c2000000-0000-4000-8000-000000000008"
ENTITY_ID = "c2000000-0000-4000-8000-000000000009"
_JOB_ACTOR = "PRCB-C5-SERVICE-INSTALLED"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _assert_clean_work_root(work_root: Path) -> None:
    if work_root.exists() and any(work_root.iterdir()):
        raise RuntimeError("installed Service E2E work root must be empty")
    work_root.mkdir(parents=True, exist_ok=True)


def _service_config(
    *,
    authority_root: Path,
    conninfo: str,
    object_root: Path,
    instructor_token: str,
    analyst_token: str,
) -> ProductionRuntimeConfig:
    return ProductionRuntimeConfig(
        profile=RuntimeProfile.SERVICE,
        product_build_version=PRODUCT_VERSION,
        authority_root=authority_root,
        object_root=object_root,
        service_conninfo=conninfo,
        service_principals=(
            ProductionPrincipalBinding(
                credential_sha256=_sha256_text(instructor_token),
                role="INSTRUCTOR_EVALUATOR",
                actor_id=None,
                scope_match=True,
            ),
            ProductionPrincipalBinding(
                credential_sha256=_sha256_text(analyst_token),
                role="ANALYST",
                actor_id=None,
                scope_match=True,
            ),
        ),
    )


def _qualification_payload(
    source_path: Path,
    *,
    p1_contract_path: Path,
) -> dict[str, object]:
    if not source_path.is_file():
        raise RuntimeError(
            f"production qualification source unavailable: {source_path}"
        )
    source_json = source_path.read_text(encoding="utf-8")
    payload: dict[str, object] = {
        "source_json": source_json,
        "source_import": {
            "source_family": "FLIGHT",
            "source_id": SOURCE_ID,
            "session_id": SESSION_ID,
            "platform_id": None,
            "producer_system": "PRCB_C5_INSTALLED_QUALIFICATION",
            "schema_name": "TPAA_PRODUCTION_FLIGHT_SOURCE_V1",
            "schema_version": "1.0.0",
            "time_basis": "SOURCE_US",
            "nominal_rate_hz": "10.0",
            "source_quality": "1.0",
            "source_stream_id": STREAM_ID,
            "stream_code": "FLIGHT_PRIMARY",
            "ordinal_basis": "SOURCE_SEQUENCE",
            "stream_status": "ACTIVE",
            "artifact_id": ARTIFACT_ID,
            "source_artifact_sequence": 0,
            "uri_kind": "EXTERNAL_FILE",
            "availability_status": "AVAILABLE",
            "last_verified_at": "2026-10-05T00:00:00Z",
            "mtime_source": None,
            "source_ref": "qualification://PRCB_C2_NOMINAL_FLIGHT",
            "media_type": PRODUCTION_FLIGHT_MEDIA_TYPE,
            "classification_label": "UNCLASSIFIED",
            "session_code": "PRCB-C5-INSTALLED",
            "session_type": "SIM",
        },
        "evaluation_context": {
            "context_id": CONTEXT_ID,
            "session_id": SESSION_ID,
            "context_version": "PRCB-C5-CONTEXT-1.0.0",
            "revision_no": 1,
            "rule_set_version": "PRCB-C5-RULES-1.0.0",
            "metric_profile_version": "PRCB_C5_P1_PROFILE_V1",
            "status": "ACTIVE",
        },
        "publication_identity": {
            "aircraft_model_id": MODEL_ID,
            "aircraft_instance_id": INSTANCE_ID,
            "subject_entity_id": ENTITY_ID,
            "capability_dimension": "AIRCRAFT_FLIGHT",
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "aircraft_type_code": "PRCB-C5-TYPE",
            "aircraft_model_name": "PRCB C5 Installed Qualification Aircraft",
            "aircraft_internal_code": "PRCB-C5-AIRCRAFT",
            "entity_alias": "PRCB-C5-SUBJECT",
        },
        "expected_version_token": 0,
        "parent_release_id": None,
    }
    payload.update(load_ed2_p1_request_contract(p1_contract_path))
    return payload


def run_installed_service_e2e(
    *,
    authority_root: Path,
    work_root: Path,
    source_path: Path,
    p1_contract_path: Path,
    conninfo: str,
    restore_conninfo: str,
    instructor_token: str,
    analyst_token: str,
) -> dict[str, object]:
    """Execute the real installed Service chain over live PostgreSQL."""

    _assert_clean_work_root(work_root)
    object_root = work_root / "primary-objects"
    payload = _qualification_payload(
        source_path,
        p1_contract_path=p1_contract_path,
    )
    config = _service_config(
        authority_root=authority_root,
        conninfo=conninfo,
        object_root=object_root,
        instructor_token=instructor_token,
        analyst_token=analyst_token,
    )
    runtime = build_service_production_runtime(config)
    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        metadata = uow.metadata.get()
        uow.commit()

    submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-service-installed-p1",
        command="BUILD_P1_RELEASE",
        payload=payload,
        actor=_JOB_ACTOR,
    )
    if submission.reused or submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed Service P1 job did not complete as fresh success")

    request_hash = canonical_request_hash(
        {"job_type": "BUILD_P1_RELEASE", "payload": payload}
    )
    release_id = allocate_session_release_id(
        session_id=SESSION_ID,
        request_hash=request_hash,
    )
    release = runtime.application.m1_release(release_id)
    metrics = runtime.application.m1_metrics(release_id)
    metric_instance_count = release.get("metric_instance_count")
    if (
        release.get("release_id") != release_id
        or release.get("catalog_definition_count") != 116
        or release.get("metric_code_count") != 116
        or isinstance(metric_instance_count, bool)
        or not isinstance(metric_instance_count, int)
        or metric_instance_count < 116
        or len(metrics) != metric_instance_count
    ):
        raise RuntimeError(
            "installed Service P1 release identity/full-catalog mismatch"
        )

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        observation_rows = uow.canonical_rows.many(
            "metric.capability_observation",
            where={"release_id": release_id},
            columns=("observation_id", "observed_value_numeric", "eligibility_status"),
            order_by=("observation_id",),
        )
        numeric_eligible = [
            row
            for row in observation_rows
            if row["eligibility_status"] == "ELIGIBLE"
            and isinstance(row["observed_value_numeric"], (int, float))
            and not isinstance(row["observed_value_numeric"], bool)
        ]
        if not numeric_eligible:
            raise RuntimeError("installed Service P1 numeric observation missing")
        p2_seed = prepare_prcb_c5_p2_workspace(
            uow.canonical_rows,
            observation_id=str(numeric_eligible[0]["observation_id"]),
        )
        uow.commit()

    p2_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-service-installed-p2",
        command="P2_ATTRIBUTION",
        payload={
            "dataset_snapshot_id": p2_seed.dataset_snapshot_id,
            "execution_time_utc": p2_seed.execution_time_utc,
            "expected_version_token": 0,
            "supersedes_estimate_id": None,
        },
        actor=_JOB_ACTOR,
    )
    if p2_submission.reused or p2_submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed Service P2 attribution did not succeed")

    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        release_rows = uow.canonical_rows.many(
            "registry.analysis_release",
            where={"compute_job_id": p2_submission.record.job_id},
            columns=("release_id", "status"),
            order_by=("release_id",),
        )
        if len(release_rows) != 1 or release_rows[0]["status"] != "PUBLISHED":
            raise RuntimeError(
                "installed Service P2 release cardinality/status mismatch"
            )
        p2_release_id = str(release_rows[0]["release_id"])
        binding = uow.canonical_rows.one(
            "assessment.attribution_run_request_binding",
            where={"compute_job_id": p2_submission.record.job_id},
            columns=("attribution_run_id",),
        )
        if binding is None:
            raise RuntimeError("installed Service P2 attribution binding missing")
        estimate_rows = uow.canonical_rows.many(
            "capability.adjusted_capability_estimate",
            where={"attribution_run_id": str(binding["attribution_run_id"])},
            columns=("estimate_id",),
            order_by=("estimate_id",),
        )
        if len(estimate_rows) != 1:
            raise RuntimeError("installed Service P2 estimate cardinality mismatch")
        p2_estimate_id = str(estimate_rows[0]["estimate_id"])
        p2_repository = P2PersistenceRepository(uow.canonical_rows)
        p2_estimate = p2_repository.exact_adjusted_estimate(p2_estimate_id)
        p2_source = p2_repository.exact_source_observation(
            p2_estimate.source_observation_id
        )
        uow.commit()

    qualification_store = LocalObjectStore(object_root)
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        p3_prepared = prepare_prcb_c5_p3(uow.canonical_rows, qualification_store)
        uow.commit()
    p3_expected = p3_prepared.fixture.estimate
    p3_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-service-installed-p3",
        command="P3_ESTIMATE",
        payload={
            "twin_revision_id": p3_expected.twin_revision_id,
            "capability_type": p3_expected.capability_type,
            "condition_point": dict(p3_expected.condition_point),
            "as_of_time_utc": p3_expected.as_of_time,
            "created_at_utc": p3_expected.created_at,
        },
        actor=_JOB_ACTOR,
    )
    if p3_submission.reused or p3_submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed Service P3 estimate did not succeed")

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        p4_prepared = prepare_prcb_c5_p4(uow.canonical_rows)
        uow.commit()
    p4_expected = p4_prepared.expected
    p4_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-service-installed-p4",
        command="P4_ASSESSMENT",
        payload={
            "scope_snapshot_id": p4_prepared.scope_snapshot_id,
            "confidence": "0.9",
            "created_at_utc": p4_expected.created_at_utc,
        },
        actor=_JOB_ACTOR,
    )
    if p4_submission.reused or p4_submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed Service P4 assessment did not succeed")

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        p5_prepared = prepare_prcb_c5_p5(
            uow.canonical_rows,
            p4_revision_id=p4_expected.actor_assessment_id,
        )
        uow.commit()
    p5_expected = p5_prepared.expected
    p5_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-service-installed-p5",
        command="P5_ASSESSMENT",
        payload={
            "selection_snapshot_id": p5_prepared.selection_snapshot_id,
            "confidence": "0.8",
            "created_at_utc": p5_expected.created_at_utc,
        },
        actor=_JOB_ACTOR,
    )
    if p5_submission.reused or p5_submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed Service P5 assessment did not succeed")

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        p6_prepared = prepare_prcb_c5_p6(
            uow.canonical_rows,
            qualification_store,
        )
        uow.commit()
    p6_forecast_expected = p6_prepared.expected_forecast
    p6_counterfactual_expected = p6_prepared.expected_counterfactual
    p6_forecast_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-service-installed-p6-forecast",
        command="P6_FORECAST",
        payload={
            "forecast_request_id": p6_prepared.forecast_request.forecast_request_id,
            "published_at_utc": p6_forecast_expected.published_at_utc,
        },
        actor=_JOB_ACTOR,
    )
    if (
        p6_forecast_submission.reused
        or p6_forecast_submission.record.status is not JobStatus.SUCCEEDED
    ):
        raise RuntimeError("installed Service P6 forecast did not succeed")
    p6_counterfactual_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-service-installed-p6-counterfactual",
        command="P6_COUNTERFACTUAL",
        payload={
            "counterfactual_request_id": (
                p6_prepared.counterfactual_request.counterfactual_request_id
            ),
            "created_at_utc": p6_counterfactual_expected.created_at_utc,
        },
        actor=_JOB_ACTOR,
    )
    if (
        p6_counterfactual_submission.reused
        or p6_counterfactual_submission.record.status is not JobStatus.SUCCEEDED
    ):
        raise RuntimeError("installed Service P6 counterfactual did not succeed")

    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        p3_actual = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=qualification_store,
        ).exact_capability_estimate(p3_expected.estimate_id)
        assessments = P4P5PersistenceRepository(uow.canonical_rows)
        p4_actual = assessments.exact_p4_revision(p4_expected.actor_assessment_id)
        p5_actual = assessments.exact_p5_revision(p5_expected.mission_assessment_id)
        p6_products = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=qualification_store,
        )
        p6_forecast_actual = p6_products.exact_forecast(
            p6_forecast_expected.forecast_result_id
        )
        p6_counterfactual_actual = p6_products.exact_counterfactual(
            p6_counterfactual_expected.counterfactual_run_id
        )
        uow.commit()
    if (
        p3_actual != p3_expected
        or p4_actual != p4_expected
        or p5_actual != p5_expected
        or p6_forecast_actual != p6_forecast_expected
        or p6_counterfactual_actual != p6_counterfactual_expected
    ):
        raise RuntimeError("installed Service P3-P6 exact persistence mismatch")

    expectation = PRCBC5DesktopApiExpectation(
        session_id=SESSION_ID,
        p1_release_id=release_id,
        p2_release_id=p2_release_id,
        p2_estimate_id=p2_estimate_id,
        p3_twin_revision_id=p3_expected.twin_revision_id,
        p3_estimate_id=p3_expected.estimate_id,
        p4_revision_id=p4_expected.actor_assessment_id,
        p5_revision_id=p5_expected.mission_assessment_id,
        p6_model_id=p6_prepared.seed.build.model.capability_model_id,
        p6_forecast_result_id=p6_forecast_expected.forecast_result_id,
        p6_counterfactual_run_id=p6_counterfactual_expected.counterfactual_run_id,
    )
    initial_api = verify_prcb_c5_service_api(
        runtime,
        expectation,
        instructor_token=instructor_token,
        analyst_token=analyst_token,
    )

    all_job_ids = (
        submission.record.job_id,
        p2_submission.record.job_id,
        p3_submission.record.job_id,
        p4_submission.record.job_id,
        p5_submission.record.job_id,
        p6_forecast_submission.record.job_id,
        p6_counterfactual_submission.record.job_id,
    )
    restarted = build_service_production_runtime(config)
    if (
        any(
            restarted.application.job(job_id).status is not JobStatus.SUCCEEDED
            for job_id in all_job_ids
        )
        or restarted.application.m1_release(release_id) != release
    ):
        raise RuntimeError("installed Service restart exact replay failed")
    restarted_api = verify_prcb_c5_service_api(
        restarted,
        expectation,
        instructor_token=instructor_token,
        analyst_token=analyst_token,
    )
    if restarted_api != initial_api:
        raise RuntimeError("installed Service API restart replay drift")

    expected_security = {
        ("ROLE:INSTRUCTOR_EVALUATOR", "P4_READ"),
        ("ROLE:INSTRUCTOR_EVALUATOR", "P5_READ"),
        ("ROLE:ANALYST", "P4_READ"),
        ("ROLE:ANALYST", "MODEL_READ"),
        ("ROLE:ANALYST", "FORECAST_READ"),
        ("ROLE:ANALYST", "COUNTERFACTUAL_READ"),
    }
    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        audit_rows = uow.audit_log.rows()
        uow.commit()
    submit_ids = {
        row.object_id
        for row in audit_rows
        if row.action == "JOB_SUBMIT"
        and row.principal_key == _JOB_ACTOR
        and row.object_id in set(all_job_ids)
    }
    observed_security = {(row.principal_key, row.action) for row in audit_rows}
    if (
        submit_ids != set(all_job_ids)
        or not expected_security.issubset(observed_security)
    ):
        raise RuntimeError("installed Service persistent audit verification failed")

    backup = work_root / "backup"
    manifest = create_service_production_backup(
        conninfo=conninfo,
        object_root=object_root,
        destination=backup,
    )
    restored_objects = work_root / "restored-objects"
    restore_service_production_backup(
        backup=backup,
        target_conninfo=restore_conninfo,
        target_object_root=restored_objects,
    )
    restored_config = _service_config(
        authority_root=authority_root,
        conninfo=restore_conninfo,
        object_root=restored_objects,
        instructor_token=instructor_token,
        analyst_token=analyst_token,
    )
    restored = build_service_production_runtime(restored_config)
    if (
        any(
            restored.application.job(job_id).status is not JobStatus.SUCCEEDED
            for job_id in all_job_ids
        )
        or restored.application.m1_release(release_id) != release
    ):
        raise RuntimeError("installed Service backup/restore historical replay failed")
    restored_api = verify_prcb_c5_service_api(
        restored,
        expectation,
        instructor_token=instructor_token,
        analyst_token=analyst_token,
    )
    if restored_api != initial_api:
        raise RuntimeError("installed Service API backup/restore replay drift")

    restored_store = LocalObjectStore(restored_objects)
    with PostgreSQLServiceUnitOfWork(restore_conninfo, read_only=True) as uow:
        restored_p2 = P2PersistenceRepository(
            uow.canonical_rows
        ).exact_adjusted_estimate(p2_estimate_id)
        restored_p3 = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=restored_store,
        ).exact_capability_estimate(p3_expected.estimate_id)
        restored_assessments = P4P5PersistenceRepository(uow.canonical_rows)
        restored_p4 = restored_assessments.exact_p4_revision(
            p4_expected.actor_assessment_id
        )
        restored_p5 = restored_assessments.exact_p5_revision(
            p5_expected.mission_assessment_id
        )
        restored_p6 = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=restored_store,
        )
        restored_forecast = restored_p6.exact_forecast(
            p6_forecast_expected.forecast_result_id
        )
        restored_counterfactual = restored_p6.exact_counterfactual(
            p6_counterfactual_expected.counterfactual_run_id
        )
        restored_audit = uow.audit_log.rows()
        restored_metadata = uow.metadata.get()
        uow.commit()
    if (
        restored_p2 != p2_estimate
        or restored_p3 != p3_expected
        or restored_p4 != p4_expected
        or restored_p5 != p5_expected
        or restored_forecast != p6_forecast_expected
        or restored_counterfactual != p6_counterfactual_expected
    ):
        raise RuntimeError("installed Service P2-P6 backup/restore exact replay failed")
    restored_submit_ids = {
        row.object_id
        for row in restored_audit
        if row.action == "JOB_SUBMIT"
        and row.principal_key == _JOB_ACTOR
        and row.object_id in set(all_job_ids)
    }
    restored_security = {(row.principal_key, row.action) for row in restored_audit}
    if (
        restored_submit_ids != set(all_job_ids)
        or not expected_security.issubset(restored_security)
    ):
        raise RuntimeError("installed Service backup/restore audit persistence failed")

    return {
        "schema": "TPAA_PRCB_C5_INSTALLED_SERVICE_P1_P6_E2E_V1",
        "status": "PASS",
        "product_version": PRODUCT_VERSION,
        "runtime_profile": "SERVICE",
        "db_schema_version": metadata.schema_version,
        "canonical_baseline": metadata.core_baseline,
        "job_id": submission.record.job_id,
        "job_status": submission.record.status.value,
        "release_id": release_id,
        "metric_count": len(metrics),
        "catalog_definition_count": release["catalog_definition_count"],
        "metric_code_count": release["metric_code_count"],
        "capability_observation_count": release[
            "capability_observation_count"
        ],
        "system_observation_count": release["system_observation_count"],
        "evidence_only_metric_instance_count": release[
            "evidence_only_metric_instance_count"
        ],
        "p2_job_id": p2_submission.record.job_id,
        "p2_job_status": p2_submission.record.status.value,
        "p2_release_id": p2_release_id,
        "p2_estimate_id": p2_estimate_id,
        "p2_estimate_status": p2_estimate.status,
        "p2_source_observation_id": p2_estimate.source_observation_id,
        "p2_source_knowledge_time_utc": p2_source.knowledge_time_utc,
        "p2_reason_codes": list(p2_estimate.reason_codes),
        "p2_claim_level": p2_estimate.claim_level,
        "p2_adjusted_value": p2_estimate.adjusted_value,
        "p2_unit": p2_estimate.unit,
        "p3_job_id": p3_submission.record.job_id,
        "p3_job_status": p3_submission.record.status.value,
        "p3_estimate_id": p3_expected.estimate_id,
        "p4_job_id": p4_submission.record.job_id,
        "p4_job_status": p4_submission.record.status.value,
        "p4_revision_id": p4_expected.actor_assessment_id,
        "p5_job_id": p5_submission.record.job_id,
        "p5_job_status": p5_submission.record.status.value,
        "p5_revision_id": p5_expected.mission_assessment_id,
        "p6_forecast_job_id": p6_forecast_submission.record.job_id,
        "p6_forecast_job_status": p6_forecast_submission.record.status.value,
        "p6_forecast_result_id": p6_forecast_expected.forecast_result_id,
        "p6_counterfactual_job_id": p6_counterfactual_submission.record.job_id,
        "p6_counterfactual_job_status": (
            p6_counterfactual_submission.record.status.value
        ),
        "p6_counterfactual_run_id": p6_counterfactual_expected.counterfactual_run_id,
        "restart_exact_replay": True,
        "backup_restore_exact_replay": True,
        "api_exact_read_verified": True,
        "service_authentication_verified": True,
        "service_rbac_verified": True,
        "service_latest_alias_rejected": True,
        "api_exact_read_restart_replay": True,
        "api_exact_read_backup_restore_replay": True,
        "api_service_fingerprint": str(initial_api["logical_fingerprint"]),
        "persistent_audit_verified": True,
        "security_audit_verified": True,
        "backup_manifest": manifest.relative_to(work_root).as_posix(),
        "restored_schema_version": restored_metadata.schema_version,
        "production_source": source_path.name,
        "tests_fixture_dependency": False,
        "model_reviewer_service_role_configured": False,
        "formal_release_claimed": False,
    }
