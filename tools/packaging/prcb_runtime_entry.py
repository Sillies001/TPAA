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

from tpaa_application import JobStatus, P2PersistenceRepository  # noqa: E402
from tpaa_ingest import PRODUCTION_FLIGHT_MEDIA_TYPE  # noqa: E402
from tpaa_observation import allocate_session_release_id  # noqa: E402
from tpaa_qualification import prepare_prcb_c5_p2_workspace  # noqa: E402
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


def _qualification_payload(source_path: Path) -> dict[str, object]:
    if not source_path.is_file():
        raise RuntimeError(f"production qualification source unavailable: {source_path}")
    source_json = source_path.read_text(encoding="utf-8")
    return {
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
        "metric_profile": {
            "profile_id": "PRCB_C5_P1_PROFILE_V1",
            "min_coverage": "0.8",
            "max_gap_us": 200000,
            "derivative_window_s": "0.3",
            "sustain_duration_s": "0.5",
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


def _desktop_p1_e2e(work_root: Path, source_path: Path) -> dict[str, object]:
    _assert_clean_work_root(work_root)
    database = work_root / "primary.sqlite3"
    object_root = work_root / "primary-objects"
    bootstrap = bootstrap_sqlite(database)
    payload = _qualification_payload(source_path)
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
    if release.get("release_id") != release_id or len(metrics) != 5:
        raise RuntimeError("installed P1 release identity/metric count mismatch")

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
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
        p2_estimate = P2PersistenceRepository(
            uow.canonical_rows
        ).exact_adjusted_estimate(p2_estimate_id)
        uow.commit()

    restarted = build_desktop_production_runtime(config)
    restarted_job = restarted.application.job(submission.record.job_id)
    restarted_release = restarted.application.m1_release(release_id)
    if (
        restarted_job.status is not JobStatus.SUCCEEDED
        or restarted_release != release
        or restarted.application.job(p2_submission.record.job_id).status
        is not JobStatus.SUCCEEDED
    ):
        raise RuntimeError("installed restart/replay verification failed")
    with SQLiteDesktopUnitOfWork(database) as uow:
        restarted_p2 = P2PersistenceRepository(
            uow.canonical_rows
        ).exact_adjusted_estimate(p2_estimate_id)
        uow.commit()
    if restarted_p2 != p2_estimate:
        raise RuntimeError("installed P2 restart exact replay failed")

    with SQLiteDesktopUnitOfWork(database) as uow:
        audit_rows = uow.audit_log.rows()
        uow.commit()
    job_audit = tuple(
        row
        for row in audit_rows
        if row.action == "JOB_SUBMIT"
        and row.object_id
        in {submission.record.job_id, p2_submission.record.job_id}
        and row.principal_key == "PRCB-C5-INSTALLED"
    )
    if len(job_audit) != 2:
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
        restored.application.job(submission.record.job_id).status
        is not JobStatus.SUCCEEDED
        or restored.application.job(p2_submission.record.job_id).status
        is not JobStatus.SUCCEEDED
        or restored.application.m1_release(release_id) != release
    ):
        raise RuntimeError("installed backup/restore historical replay failed")

    with SQLiteDesktopUnitOfWork(restored_database) as uow:
        restored_p2 = P2PersistenceRepository(
            uow.canonical_rows
        ).exact_adjusted_estimate(p2_estimate_id)
        restored_audit = uow.audit_log.rows()
        uow.commit()
    if restored_p2 != p2_estimate:
        raise RuntimeError("installed P2 backup/restore exact replay failed")
    restored_submit_ids = {
        row.object_id
        for row in restored_audit
        if row.action == "JOB_SUBMIT"
        and row.principal_key == "PRCB-C5-INSTALLED"
        and row.object_id
        in {submission.record.job_id, p2_submission.record.job_id}
    }
    if restored_submit_ids != {
        submission.record.job_id,
        p2_submission.record.job_id,
    }:
        raise RuntimeError("installed backup/restore audit persistence failed")

    return {
        "schema": "TPAA_PRCB_C5_INSTALLED_DESKTOP_P1_P2_E2E_V1",
        "status": "PASS",
        "product_version": PRODUCT_VERSION,
        "runtime_profile": "DESKTOP",
        "db_schema_version": bootstrap.schema_version,
        "canonical_baseline": bootstrap.core_baseline,
        "job_id": submission.record.job_id,
        "job_status": submission.record.status.value,
        "release_id": release_id,
        "metric_count": len(metrics),
        "p2_job_id": p2_submission.record.job_id,
        "p2_job_status": p2_submission.record.status.value,
        "p2_qualification_as_of_utc": p2_seed.as_of_utc,
        "p2_execution_time_utc": p2_seed.execution_time_utc,
        "p2_release_id": p2_release_id,
        "p2_estimate_id": p2_estimate_id,
        "p2_estimate_status": p2_estimate.status,
        "p2_restart_exact_replay": True,
        "p2_backup_restore_exact_replay": True,
        "restart_exact_replay": True,
        "backup_restore_exact_replay": True,
        "persistent_audit_verified": True,
        "backup_manifest": manifest.relative_to(work_root).as_posix(),
        "restored_schema_version": restored_verification.schema_version,
        "production_source": source_path.name,
        "tests_fixture_dependency": False,
        "formal_release_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(ALL_PROFILES))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ready")
    desktop = sub.add_parser("desktop-p1-e2e")
    desktop.add_argument("--work-root", type=Path, required=True)
    desktop.add_argument("--source", type=Path, default=QUALIFICATION_SOURCE)
    args = parser.parse_args()

    if args.command == "ready":
        result = _ready(args.profile)
    elif args.command == "desktop-p1-e2e":
        if args.profile not in DESKTOP_PROFILES:
            raise RuntimeError("desktop-p1-e2e requires a Desktop profile")
        result = _desktop_p1_e2e(args.work_root, args.source)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
