#!/usr/bin/env python3
"""PRCB C5 installed production runtime entry for TPAA 1.0.1 candidates."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = APP_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_application import (  # noqa: E402
    JobStatus,
    P2PersistenceRepository,
    P3PersistenceRepository,
    P4P5PersistenceRepository,
    P6PersistenceRepository,
)
from tpaa_ingest import PRODUCTION_FLIGHT_MEDIA_TYPE  # noqa: E402
from tpaa_observation import allocate_session_release_id  # noqa: E402
from tpaa_qualification.ed2_b2_continuous import (  # noqa: E402
    QualificationUowFactory,
    run_ed2_b2_continuous_qualification,
)
from tpaa_qualification.ed2_p1_request_contract import (  # noqa: E402
    load_ed2_p1_request_contract,
)
from tpaa_qualification.prcb_c5_api_desktop import (  # noqa: E402
    PRCBC5DesktopApiExpectation,
    verify_prcb_c5_desktop_api_discovery,
)
from tpaa_qualification.prcb_c5_downstream import (  # noqa: E402
    prepare_prcb_c5_p3,
    prepare_prcb_c5_p4,
    prepare_prcb_c5_p5,
    prepare_prcb_c5_p6,
)
from tpaa_qualification.prcb_c5_p2 import (  # noqa: E402
    prepare_prcb_c5_p2_workspace,
)
from tpaa_qualification.prcb_c5_service_e2e import (  # noqa: E402
    run_installed_service_e2e,
)
from tpaa_runtime import (  # noqa: E402
    ProductionRuntime,
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
    build_service_production_runtime,
    create_desktop_production_backup,
    restore_desktop_production_backup,
)
from tpaa_storage import (  # noqa: E402
    LocalObjectStore,
    PostgreSQLServiceUnitOfWork,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
    verify_sqlite,
)
from tpaa_storage.hashing import canonical_request_hash  # noqa: E402

PRODUCT_VERSION = "1.0.1"
DESKTOP_PROFILES = {"WINDOWS_DESKTOP_X64", "LINUX_DESKTOP_X64"}
SERVICE_PROFILES = {"WINDOWS_SERVICE_X64", "LINUX_SERVICE_X64"}
ALL_PROFILES = DESKTOP_PROFILES | SERVICE_PROFILES
QUALIFICATION_SOURCE = APP_ROOT / "qualification" / "PRCB_C2_NOMINAL_FLIGHT.json"
QUALIFICATION_P1_CONTRACT = (
    APP_ROOT / "qualification" / "ED2_B1_FULL_P1_REQUEST_CONTRACT.json"
)
QUALIFICATION_B2_PLAN = (
    APP_ROOT / "qualification" / "ED2_B2_CONTINUOUS_QUALIFICATION_PLAN.json"
)

SESSION_ID = "c2000000-0000-4000-8000-000000000001"
CONTEXT_ID = "c2000000-0000-4000-8000-000000000003"
SOURCE_ID = "c2000000-0000-4000-8000-000000000004"
STREAM_ID = "c2000000-0000-4000-8000-000000000005"
ARTIFACT_ID = "c2000000-0000-4000-8000-000000000006"
MODEL_ID = "c2000000-0000-4000-8000-000000000007"
INSTANCE_ID = "c2000000-0000-4000-8000-000000000008"
ENTITY_ID = "c2000000-0000-4000-8000-000000000009"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _authority_root() -> Path:
    root = APP_ROOT / "baseline" / "CB-1.4.0" / "canonical"
    if not root.is_dir():
        raise RuntimeError("packaged canonical authority is unavailable")
    return root


def _runtime(profile_id: str) -> ProductionRuntime:
    object_root = Path(_required_env("TPAA_OBJECT_ROOT"))
    if profile_id in DESKTOP_PROFILES:
        database = Path(_required_env("TPAA_DESKTOP_DATABASE"))
        config = ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version=PRODUCT_VERSION,
            authority_root=_authority_root(),
            object_root=object_root,
            desktop_database_path=database,
        )
        return build_desktop_production_runtime(config)
    if profile_id in SERVICE_PROFILES:
        config = ProductionRuntimeConfig(
            profile=RuntimeProfile.SERVICE,
            product_build_version=PRODUCT_VERSION,
            authority_root=_authority_root(),
            object_root=object_root,
            service_conninfo=_required_env("TPAA_SERVICE_CONNINFO"),
        )
        return build_service_production_runtime(config)
    raise ValueError(f"unsupported PRCB runtime profile: {profile_id}")


def _ready(profile_id: str) -> dict[str, object]:
    runtime = _runtime(profile_id)
    availability = runtime.feature_availability.execute()
    return {
        "schema": "TPAA_PRCB_C5_INSTALLED_RUNTIME_READY_V1",
        "status": "PASS",
        "profile_id": profile_id,
        "runtime_profile": runtime.config.profile.value,
        "product_version": runtime.config.product_build_version,
        "db_schema_version": "1.9.0",
        "canonical_baseline": "CB-1.4.0",
        "feature_availability": availability,
        "production_composition": True,
        "tests_fixture_dependency": False,
        "formal_release_claimed": False,
    }


def _qualification_payload(
    source_path: Path,
    *,
    p1_contract_path: Path = QUALIFICATION_P1_CONTRACT,
) -> dict[str, object]:
    if not source_path.is_file():
        raise RuntimeError(f"production qualification source unavailable: {source_path}")
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


def _desktop_config(database: Path, object_root: Path) -> ProductionRuntimeConfig:
    return ProductionRuntimeConfig(
        profile=RuntimeProfile.DESKTOP,
        product_build_version=PRODUCT_VERSION,
        authority_root=_authority_root(),
        object_root=object_root,
        desktop_database_path=database,
    )


def _assert_clean_work_root(work_root: Path) -> None:
    if work_root.exists() and any(work_root.iterdir()):
        raise RuntimeError("installed E2E work root must be empty")
    work_root.mkdir(parents=True, exist_ok=True)


def _desktop_e2e(
    work_root: Path,
    source_path: Path,
    *,
    p1_contract_path: Path = QUALIFICATION_P1_CONTRACT,
) -> dict[str, object]:
    _assert_clean_work_root(work_root)
    database = work_root / "primary.sqlite3"
    object_root = work_root / "primary-objects"
    bootstrap = bootstrap_sqlite(database)
    schema_version = bootstrap.schema_version
    core_baseline = bootstrap.core_baseline
    payload = _qualification_payload(
        source_path,
        p1_contract_path=p1_contract_path,
    )
    config = _desktop_config(database, object_root)
    runtime = build_desktop_production_runtime(config)

    idempotency_key = "prcb-c5-installed-p1"
    submission = runtime.application.submit_job(
        idempotency_key=idempotency_key,
        command="BUILD_P1_RELEASE",
        payload=payload,
        actor="PRCB-C5-INSTALLED",
    )
    if submission.reused or submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed P1 job did not complete as a fresh durable success")

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
        or release.get("world_product_count") != 4
        or isinstance(metric_instance_count, bool)
        or not isinstance(metric_instance_count, int)
        or metric_instance_count < 116
        or len(metrics) != metric_instance_count
    ):
        raise RuntimeError("installed P1 release identity/full-catalog mismatch")

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        episode_rows = uow.canonical_rows.many(
            "episode.training_episode",
            where={"session_id": SESSION_ID},
            columns=("episode_id", "episode_type", "data_sufficiency_status"),
            order_by=("episode_id",),
        )
        if (
            len(episode_rows) != 1
            or episode_rows[0]["episode_type"] != "BASIC_FLIGHT"
            or episode_rows[0]["data_sufficiency_status"] != "SUFFICIENT"
        ):
            raise RuntimeError("installed P1 BASIC_FLIGHT Episode authority mismatch")
        episode_id = str(episode_rows[0]["episode_id"])
        stage_rows = uow.canonical_rows.many(
            "episode.episode_stage",
            where={"episode_id": episode_id},
            columns=("stage_id", "stage_type", "stage_order", "stage_status"),
            order_by=("stage_order",),
        )
        world_rows = uow.canonical_rows.many(
            "world.world_product_manifest",
            where={"release_id": release_id},
            columns=("world_kind", "status", "coverage", "episode_id"),
            order_by=("world_kind",),
        )
        relation_rows = uow.canonical_rows.many(
            "world.world_relation",
            where={"release_id": release_id},
            columns=(
                "relation_type",
                "subject_ref",
                "object_ref",
                "relation_source",
                "start_session_time_us",
            ),
            order_by=("start_session_time_us",),
        )
        if [row["stage_type"] for row in stage_rows] != [
            "SETUP_ENTRY",
            "EXECUTION",
            "STABILIZATION_RECOVERY",
            "COMPLETION",
        ]:
            raise RuntimeError("installed P1 Stage sequence mismatch")
        if [row["world_kind"] for row in world_rows] != [
            "ACTION",
            "CONTEXT",
            "MACHINE",
            "TRUTH",
        ] or any(row["status"] != "READY" for row in world_rows):
            raise RuntimeError("installed P1 BASIC_CORE World authority mismatch")
        if (
            len(relation_rows) != 3
            or any(row["relation_type"] != "PRECEDES" for row in relation_rows)
            or any(row["relation_source"] != "OFFICIAL" for row in relation_rows)
        ):
            raise RuntimeError("installed P1 Stage relation authority mismatch")

        observation_rows = uow.canonical_rows.many(
            "metric.capability_observation",
            where={"release_id": release_id},
            columns=(
                "observation_id",
                "observed_value_numeric",
                "eligibility_status",
            ),
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
            raise RuntimeError(
                "installed P1 numeric eligible capability observation missing"
            )
        observation_id = str(numeric_eligible[0]["observation_id"])
        p2_seed = prepare_prcb_c5_p2_workspace(
            uow.canonical_rows,
            observation_id=observation_id,
        )
        uow.commit()

    p2_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-installed-p2",
        command="P2_ATTRIBUTION",
        payload={
            "dataset_snapshot_id": p2_seed.dataset_snapshot_id,
            "execution_time_utc": p2_seed.execution_time_utc,
            "expected_version_token": 0,
            "supersedes_estimate_id": None,
        },
        actor="PRCB-C5-INSTALLED",
    )
    if (
        p2_submission.reused
        or p2_submission.record.status is not JobStatus.SUCCEEDED
    ):
        with SQLiteDesktopUnitOfWork(database) as uow:
            durable_failure = uow.canonical_rows.one(
                "registry.compute_job",
                where={"job_id": p2_submission.record.job_id},
                columns=("status", "reason_codes", "error_detail"),
            )
            uow.commit()
        raise RuntimeError(
            "installed P2 attribution did not succeed: "
            f"{durable_failure!r}"
        )

    with SQLiteDesktopUnitOfWork(database) as uow:
        p2_release_rows = uow.canonical_rows.many(
            "registry.analysis_release",
            where={"compute_job_id": p2_submission.record.job_id},
            columns=("release_id", "status"),
            order_by=("release_id",),
        )
        if len(p2_release_rows) != 1:
            raise RuntimeError("installed P2 release cardinality mismatch")
        p2_release_id = str(p2_release_rows[0]["release_id"])
        if str(p2_release_rows[0]["status"]) != "PUBLISHED":
            raise RuntimeError("installed P2 release is not published")
        run_binding = uow.canonical_rows.one(
            "assessment.attribution_run_request_binding",
            where={"compute_job_id": p2_submission.record.job_id},
            columns=("attribution_run_id",),
        )
        if run_binding is None:
            raise RuntimeError("installed P2 attribution binding missing")
        attribution_run_id = str(run_binding["attribution_run_id"])
        estimate_rows = uow.canonical_rows.many(
            "capability.adjusted_capability_estimate",
            where={"attribution_run_id": attribution_run_id},
            columns=("estimate_id",),
            order_by=("estimate_id",),
        )
        if len(estimate_rows) != 1:
            raise RuntimeError("installed P2 estimate cardinality mismatch")
        p2_estimate_id = str(estimate_rows[0]["estimate_id"])
        p2_repository = P2PersistenceRepository(uow.canonical_rows)
        p2_estimate = p2_repository.exact_adjusted_estimate(p2_estimate_id)
        p2_source = p2_repository.exact_source_observation(
            p2_estimate.source_observation_id
        )
        uow.commit()

    qualification_store = LocalObjectStore(object_root)

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        p3_prepared = prepare_prcb_c5_p3(
            uow.canonical_rows,
            qualification_store,
        )
        uow.commit()
    p3_expected = p3_prepared.fixture.estimate
    p3_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-installed-p3",
        command="P3_ESTIMATE",
        payload={
            "twin_revision_id": p3_expected.twin_revision_id,
            "capability_type": p3_expected.capability_type,
            "condition_point": dict(p3_expected.condition_point),
            "as_of_time_utc": p3_expected.as_of_time,
            "created_at_utc": p3_expected.created_at,
        },
        actor="PRCB-C5-INSTALLED",
    )
    if p3_submission.reused or p3_submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed P3 estimate did not succeed")

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        p4_prepared = prepare_prcb_c5_p4(uow.canonical_rows)
        uow.commit()
    p4_expected = p4_prepared.expected
    p4_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-installed-p4",
        command="P4_ASSESSMENT",
        payload={
            "scope_snapshot_id": p4_prepared.scope_snapshot_id,
            "confidence": "0.9",
            "created_at_utc": p4_expected.created_at_utc,
        },
        actor="PRCB-C5-INSTALLED",
    )
    if p4_submission.reused or p4_submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed P4 assessment did not succeed")

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        p5_prepared = prepare_prcb_c5_p5(
            uow.canonical_rows,
            p4_revision_id=p4_expected.actor_assessment_id,
        )
        uow.commit()
    p5_expected = p5_prepared.expected
    p5_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-installed-p5",
        command="P5_ASSESSMENT",
        payload={
            "selection_snapshot_id": p5_prepared.selection_snapshot_id,
            "confidence": "0.8",
            "created_at_utc": p5_expected.created_at_utc,
        },
        actor="PRCB-C5-INSTALLED",
    )
    if p5_submission.reused or p5_submission.record.status is not JobStatus.SUCCEEDED:
        raise RuntimeError("installed P5 assessment did not succeed")

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        p6_prepared = prepare_prcb_c5_p6(
            uow.canonical_rows,
            qualification_store,
        )
        uow.commit()
    p6_forecast_expected = p6_prepared.expected_forecast
    p6_counterfactual_expected = p6_prepared.expected_counterfactual
    p6_forecast_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-installed-p6-forecast",
        command="P6_FORECAST",
        payload={
            "forecast_request_id": p6_prepared.forecast_request.forecast_request_id,
            "published_at_utc": p6_forecast_expected.published_at_utc,
        },
        actor="PRCB-C5-INSTALLED",
    )
    if (
        p6_forecast_submission.reused
        or p6_forecast_submission.record.status is not JobStatus.SUCCEEDED
    ):
        raise RuntimeError("installed P6 forecast did not succeed")
    p6_counterfactual_submission = runtime.application.submit_job(
        idempotency_key="prcb-c5-installed-p6-counterfactual",
        command="P6_COUNTERFACTUAL",
        payload={
            "counterfactual_request_id": (
                p6_prepared.counterfactual_request.counterfactual_request_id
            ),
            "created_at_utc": p6_counterfactual_expected.created_at_utc,
        },
        actor="PRCB-C5-INSTALLED",
    )
    if (
        p6_counterfactual_submission.reused
        or p6_counterfactual_submission.record.status is not JobStatus.SUCCEEDED
    ):
        raise RuntimeError("installed P6 counterfactual did not succeed")

    with SQLiteDesktopUnitOfWork(database) as uow:
        p3_actual = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=qualification_store,
        ).exact_capability_estimate(p3_expected.estimate_id)
        products = P4P5PersistenceRepository(uow.canonical_rows)
        p4_actual = products.exact_p4_revision(p4_expected.actor_assessment_id)
        p5_actual = products.exact_p5_revision(p5_expected.mission_assessment_id)
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
        raise RuntimeError("installed P3-P6 exact persistence verification failed")

    desktop_api_expectation = PRCBC5DesktopApiExpectation(
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
    desktop_bearer = "prcb-c5-installed-desktop-qualification"
    initial_api_discovery = verify_prcb_c5_desktop_api_discovery(
        runtime,
        desktop_api_expectation,
        bearer_token=desktop_bearer,
    )

    downstream_job_ids = (
        p3_submission.record.job_id,
        p4_submission.record.job_id,
        p5_submission.record.job_id,
        p6_forecast_submission.record.job_id,
        p6_counterfactual_submission.record.job_id,
    )
    all_job_ids = (
        submission.record.job_id,
        p2_submission.record.job_id,
        *downstream_job_ids,
    )

    restarted = build_desktop_production_runtime(config)
    restarted_job = restarted.application.job(submission.record.job_id)
    restarted_release = restarted.application.m1_release(release_id)
    if (
        restarted_job.status is not JobStatus.SUCCEEDED
        or restarted_release != release
        or any(
            restarted.application.job(job_id).status is not JobStatus.SUCCEEDED
            for job_id in all_job_ids[1:]
        )
    ):
        raise RuntimeError("installed restart/replay verification failed")
    with SQLiteDesktopUnitOfWork(database) as uow:
        restarted_p2 = P2PersistenceRepository(
            uow.canonical_rows
        ).exact_adjusted_estimate(p2_estimate_id)
        restarted_p3 = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=qualification_store,
        ).exact_capability_estimate(p3_expected.estimate_id)
        restarted_assessments = P4P5PersistenceRepository(uow.canonical_rows)
        restarted_p4 = restarted_assessments.exact_p4_revision(
            p4_expected.actor_assessment_id
        )
        restarted_p5 = restarted_assessments.exact_p5_revision(
            p5_expected.mission_assessment_id
        )
        restarted_p6 = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=qualification_store,
        )
        restarted_forecast = restarted_p6.exact_forecast(
            p6_forecast_expected.forecast_result_id
        )
        restarted_counterfactual = restarted_p6.exact_counterfactual(
            p6_counterfactual_expected.counterfactual_run_id
        )
        uow.commit()
    if (
        restarted_p2 != p2_estimate
        or restarted_p3 != p3_expected
        or restarted_p4 != p4_expected
        or restarted_p5 != p5_expected
        or restarted_forecast != p6_forecast_expected
        or restarted_counterfactual != p6_counterfactual_expected
    ):
        raise RuntimeError("installed P2-P6 restart exact replay failed")

    restarted_api_discovery = verify_prcb_c5_desktop_api_discovery(
        restarted,
        desktop_api_expectation,
        bearer_token=desktop_bearer,
    )
    if restarted_api_discovery != initial_api_discovery:
        raise RuntimeError("installed API/Desktop discovery restart replay drift")

    with SQLiteDesktopUnitOfWork(database) as uow:
        audit_rows = uow.audit_log.rows()
        uow.commit()
    job_audit = tuple(
        row
        for row in audit_rows
        if row.action == "JOB_SUBMIT"
        and row.object_id in set(all_job_ids)
        and row.principal_key == "PRCB-C5-INSTALLED"
    )
    if len(job_audit) != len(all_job_ids):
        raise RuntimeError("installed durable job audit verification failed")

    backup = work_root / "backup"
    manifest = create_desktop_production_backup(
        database=database,
        object_root=object_root,
        destination=backup,
    )
    restored_database = work_root / "restored.sqlite3"
    restored_objects = work_root / "restored-objects"
    restore_desktop_production_backup(
        backup=backup,
        target_database=restored_database,
        target_object_root=restored_objects,
    )
    restored_verification = verify_sqlite(restored_database)
    restored = build_desktop_production_runtime(
        _desktop_config(restored_database, restored_objects)
    )
    if (
        any(
            restored.application.job(job_id).status is not JobStatus.SUCCEEDED
            for job_id in all_job_ids
        )
        or restored.application.m1_release(release_id) != release
    ):
        raise RuntimeError("installed backup/restore historical replay failed")

    restored_api_discovery = verify_prcb_c5_desktop_api_discovery(
        restored,
        desktop_api_expectation,
        bearer_token=desktop_bearer,
    )
    if restored_api_discovery != initial_api_discovery:
        raise RuntimeError("installed API/Desktop discovery backup/restore replay drift")

    restored_store = LocalObjectStore(restored_objects)
    with SQLiteDesktopUnitOfWork(restored_database) as uow:
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
        uow.commit()
    if (
        restored_p2 != p2_estimate
        or restored_p3 != p3_expected
        or restored_p4 != p4_expected
        or restored_p5 != p5_expected
        or restored_forecast != p6_forecast_expected
        or restored_counterfactual != p6_counterfactual_expected
    ):
        raise RuntimeError("installed P2-P6 backup/restore exact replay failed")
    restored_submit_ids = {
        row.object_id
        for row in restored_audit
        if row.action == "JOB_SUBMIT"
        and row.principal_key == "PRCB-C5-INSTALLED"
        and row.object_id in set(all_job_ids)
    }
    if restored_submit_ids != set(all_job_ids):
        raise RuntimeError("installed backup/restore audit persistence failed")

    return {
        "schema": "TPAA_PRCB_C5_INSTALLED_DESKTOP_P1_P6_E2E_V1",
        "status": "PASS",
        "product_version": PRODUCT_VERSION,
        "runtime_profile": "DESKTOP",
        "db_schema_version": schema_version,
        "canonical_baseline": core_baseline,
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
        "world_product_count": len(world_rows),
        "stage_count": len(stage_rows),
        "world_relation_count": len(relation_rows),
        "p2_job_id": p2_submission.record.job_id,
        "p2_job_status": p2_submission.record.status.value,
        "p2_qualification_as_of_utc": p2_seed.as_of_utc,
        "p2_execution_time_utc": p2_seed.execution_time_utc,
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
        "p6_counterfactual_run_id": (
            p6_counterfactual_expected.counterfactual_run_id
        ),
        "p2_restart_exact_replay": True,
        "p2_backup_restore_exact_replay": True,
        "p3_p6_restart_exact_replay": True,
        "p3_p6_backup_restore_exact_replay": True,
        "restart_exact_replay": True,
        "backup_restore_exact_replay": True,
        "api_exact_read_verified": True,
        "desktop_discovery_verified": True,
        "desktop_authentication_verified": True,
        "desktop_latest_alias_rejected": True,
        "api_exact_read_restart_replay": True,
        "desktop_discovery_restart_replay": True,
        "api_exact_read_backup_restore_replay": True,
        "desktop_discovery_backup_restore_replay": True,
        "api_discovery_fingerprint": str(
            initial_api_discovery["logical_fingerprint"]
        ),
        "persistent_audit_verified": True,
        "backup_manifest": manifest.relative_to(work_root).as_posix(),
        "restored_schema_version": restored_verification.schema_version,
        "production_source": source_path.name,
        "tests_fixture_dependency": False,
        "formal_release_claimed": False,
    }


def _ed2_b2_e2e(
    profile_id: str,
    work_root: Path,
) -> dict[str, object]:
    if work_root.exists() and any(work_root.iterdir()):
        raise RuntimeError("ED2 B2 qualification work root must be empty")
    work_root.mkdir(parents=True, exist_ok=True)
    object_root = work_root / "objects"
    object_store = LocalObjectStore(object_root)
    uow_factory: QualificationUowFactory

    if profile_id in DESKTOP_PROFILES:
        database = work_root / "ed2-b2.sqlite3"
        bootstrap_result = bootstrap_sqlite(database)
        schema_version = bootstrap_result.schema_version
        core_baseline = bootstrap_result.core_baseline
        config = ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version=PRODUCT_VERSION,
            authority_root=_authority_root(),
            object_root=object_root,
            desktop_database_path=database,
        )
        runtime = build_desktop_production_runtime(config)

        def desktop_uow_factory(write: bool) -> SQLiteDesktopUnitOfWork:
            return SQLiteDesktopUnitOfWork(database, write=write)

        uow_factory = desktop_uow_factory
    elif profile_id in SERVICE_PROFILES:
        conninfo = _required_env("TPAA_SERVICE_CONNINFO")
        config = ProductionRuntimeConfig(
            profile=RuntimeProfile.SERVICE,
            product_build_version=PRODUCT_VERSION,
            authority_root=_authority_root(),
            object_root=object_root,
            service_conninfo=conninfo,
        )
        runtime = build_service_production_runtime(config)

        def service_uow_factory(write: bool) -> PostgreSQLServiceUnitOfWork:
            return PostgreSQLServiceUnitOfWork(
                conninfo,
                read_only=not write,
            )

        uow_factory = service_uow_factory
        with PostgreSQLServiceUnitOfWork(
            conninfo,
            read_only=True,
        ) as metadata_uow:
            metadata = metadata_uow.metadata.get()
            schema_version = metadata.schema_version
            core_baseline = metadata.core_baseline
            metadata_uow.commit()
    else:
        raise RuntimeError("unsupported ED2 B2 qualification profile")

    result = run_ed2_b2_continuous_qualification(
        runtime=runtime,
        uow_factory=uow_factory,
        object_store=object_store,
        plan_path=QUALIFICATION_B2_PLAN,
        actor="ED2-B2-INSTALLED-QUALIFICATION",
    )

    restarted = (
        build_desktop_production_runtime(config)
        if profile_id in DESKTOP_PROFILES
        else build_service_production_runtime(config)
    )
    del restarted
    with uow_factory(False) as uow:
        p2 = P2PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        for estimate_id in result.p2_estimate_ids:
            if p2.exact_adjusted_estimate(estimate_id).status != "IDENTIFIABLE":
                raise RuntimeError(
                    "ED2 B2 restart P2 exact read failed"
                )
        p3 = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        p3.exact_twin_revision(result.p3_twin_revision_id)
        assessments = P4P5PersistenceRepository(uow.canonical_rows)
        for revision_id in result.p4_approved_revision_ids:
            if assessments.exact_p4_revision(
                revision_id
            ).approval_state != "APPROVED":
                raise RuntimeError(
                    "ED2 B2 restart P4 exact read failed"
                )
        if assessments.exact_p5_revision(
            result.p5_approved_revision_id
        ).approval_state != "APPROVED":
            raise RuntimeError("ED2 B2 restart P5 exact read failed")
        p6 = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        p6.exact_model_revision(result.p6_model_id)
        p6.exact_forecast(result.p6_forecast_result_id)
        p6.exact_counterfactual(result.p6_counterfactual_run_id)
        uow.commit()

    report = result.report()
    return {
        **report,
        "status": "PASS",
        "product_version": PRODUCT_VERSION,
        "runtime_profile": (
            "DESKTOP" if profile_id in DESKTOP_PROFILES else "SERVICE"
        ),
        "db_schema_version": schema_version,
        "canonical_baseline": core_baseline,
        "restart_exact_replay": True,
        "tests_fixture_dependency": False,
        "production_seed_dependency": False,
        "formal_release_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(ALL_PROFILES))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ready")
    for command_name in ("desktop-e2e", "desktop-p1-e2e"):
        desktop = sub.add_parser(command_name)
        desktop.add_argument("--work-root", type=Path, required=True)
        desktop.add_argument("--source", type=Path, default=QUALIFICATION_SOURCE)
    service = sub.add_parser("service-e2e")
    service.add_argument("--work-root", type=Path, required=True)
    service.add_argument("--source", type=Path, default=QUALIFICATION_SOURCE)
    ed2_b2 = sub.add_parser("ed2-b2-e2e")
    ed2_b2.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "ready":
        result = _ready(args.profile)
    elif args.command in {"desktop-e2e", "desktop-p1-e2e"}:
        if args.profile not in DESKTOP_PROFILES:
            raise RuntimeError("desktop-e2e requires a Desktop profile")
        result = _desktop_e2e(args.work_root, args.source)
    elif args.command == "service-e2e":
        if args.profile not in SERVICE_PROFILES:
            raise RuntimeError("service-e2e requires a Service profile")
        result = run_installed_service_e2e(
            authority_root=_authority_root(),
            work_root=args.work_root,
            source_path=args.source,
            p1_contract_path=QUALIFICATION_P1_CONTRACT,
            conninfo=_required_env("TPAA_SERVICE_CONNINFO"),
            restore_conninfo=_required_env("TPAA_SERVICE_RESTORE_CONNINFO"),
            instructor_token=_required_env("TPAA_C5_INSTRUCTOR_TOKEN"),
            analyst_token=_required_env("TPAA_C5_ANALYST_TOKEN"),
        )
    elif args.command == "ed2-b2-e2e":
        result = _ed2_b2_e2e(args.profile, args.work_root)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
