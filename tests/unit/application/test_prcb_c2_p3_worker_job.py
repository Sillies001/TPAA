from __future__ import annotations

from pathlib import Path

from tools.testing.piqb_b2_p3_fixture import REFERENCE, build_fixture, seed_upstream
from tpaa_application import JobStatus, P3PersistenceRepository
from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import LocalObjectStore, SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_prcb_c2_p3_estimate_runs_in_durable_governed_worker(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    object_root = tmp_path / "objects"
    object_store = LocalObjectStore(object_root)
    bootstrap_sqlite(database)
    fixture = build_fixture()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        seed_upstream(uow.canonical_rows)
        repository = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        repository.register_component(
            segment=fixture.segment,
            validation=fixture.validation,
            training=fixture.training,
            model_build=fixture.model_build,
            surface_build=fixture.surface_build,
            model_object=fixture.model_object,
            surface_object=fixture.surface_object,
        )
        repository.register_twin(
            fixture.twin,
            components=(fixture.component,),
        )
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
        idempotency_key="prcb-c2-p3-estimate",
        command="P3_ESTIMATE",
        payload={
            "twin_revision_id": fixture.twin.twin_revision_id,
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "condition_point": {
                "session_order": 4,
                "reference_condition_id": REFERENCE,
            },
            "as_of_time_utc": "2026-09-10T00:00:00Z",
            "created_at_utc": "2026-09-10T04:00:00Z",
        },
        actor="PRCB-C2-TEST",
    )
    if submission.record.status is not JobStatus.SUCCEEDED:
        with SQLiteDesktopUnitOfWork(database) as uow:
            durable = uow.canonical_rows.one(
                "registry.compute_job",
                where={"job_id": submission.record.job_id},
                columns=("reason_codes", "error_detail"),
            )
            uow.commit()
        raise AssertionError(f"P3 estimate job failed: {durable!r}")

    with SQLiteDesktopUnitOfWork(database) as uow:
        persisted = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        ).exact_capability_estimate(fixture.estimate.estimate_id)
        assert persisted == fixture.estimate
        uow.commit()

    restarted = build_desktop_production_runtime(runtime.config)
    assert restarted.application.job(
        submission.record.job_id
    ).status is JobStatus.SUCCEEDED
