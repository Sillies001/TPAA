from __future__ import annotations

from pathlib import Path

from tools.testing.piqb_b2_p6_resolver_fixture import (
    AIRCRAFT,
    seed_p6_model_resolver_case,
)
from tpaa_application import JobStatus, P6PersistenceRepository
from tpaa_capability import (
    P6ContextRef,
    P6FactualSourceRevision,
    P6ForecastExecutionProfile,
    build_p6_forecast_request_binding,
    build_p6_input_snapshot,
)
from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import LocalObjectStore, SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
P4 = "95200000-0000-4000-8000-000000000002"
CONTEXT = "95200000-0000-4000-8000-000000000003"


def test_prcb_c2_product_persistence_and_job_success_share_one_transaction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    object_root = tmp_path / "objects"
    object_store = LocalObjectStore(object_root)
    bootstrap_sqlite(database)

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        fixture = seed_p6_model_resolver_case(uow.canonical_rows, object_store)
        snapshot = build_p6_input_snapshot(
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
            subject_or_composition_ref=AIRCRAFT,
            forecast_origin_utc="2026-09-10T13:00:00Z",
            as_of_utc="2026-09-10T13:00:00Z",
        )
        profile = P6ForecastExecutionProfile.from_canonical()
        request = build_p6_forecast_request_binding(
            input_snapshot=snapshot,
            forecast_spec_id="P6_FORECAST:P3_CAPABILITY_NEXT_SESSION",
            forecast_spec_version="1.0.0",
            target_code=profile.target_code,
            horizon_spec={
                "type": profile.horizon_type,
                "steps": profile.horizon_steps,
                "target_session_order": 5,
            },
            capability_model_id=fixture.build.model.capability_model_id,
            model_profile_id=profile.profile_id,
            model_profile_version=profile.profile_version,
            training_dataset_snapshot_id=fixture.build.model.training_dataset_snapshot_id,
            validation_dataset_snapshot_id=fixture.build.model.validation_dataset_snapshot_id,
            assumption_profile_id="P6_ASSUMPTION:TRAINING_EVALUATION",
            assumption_profile_version="1.0.0",
        )
        repository = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        repository.register_input(snapshot)
        repository.register_forecast_request(request)
        uow.commit()

    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=AUTHORITY,
            object_root=object_root,
            desktop_database_path=database,
        )
    )
    submission = runtime.application.submit_job(
        idempotency_key="prcb-c2-atomic-forecast",
        command="P6_FORECAST",
        payload={
            "forecast_request_id": request.forecast_request_id,
            "published_at_utc": "2026-09-10T13:30:00Z",
        },
        actor="PRCB-C2-TEST",
    )
    assert submission.record.status is JobStatus.SUCCEEDED

    with SQLiteDesktopUnitOfWork(database) as uow:
        job = uow.canonical_rows.one(
            "registry.compute_job",
            where={"job_id": submission.record.job_id},
            columns=("status",),
        )
        assert job is not None
        assert job["status"] == "SUCCEEDED"
        persisted = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        ).exact_forecast_request(request.forecast_request_id)
        assert persisted == request
        uow.commit()
