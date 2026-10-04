from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from tpaa_application import DurableJobControl
from tpaa_storage import (
    ComputeJobRepository,
    LocalObjectStore,
    LocalSealedObjectFlow,
    SQLiteCanonicalRowRepository,
    bootstrap_sqlite,
    recover_staging_orphans,
)


def _now() -> datetime:
    return datetime(2026, 10, 4, tzinfo=UTC)


def test_active_compute_jobs_protect_staging_then_cancelled_job_is_reclaimed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "jobs.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    repository = ComputeJobRepository(SQLiteCanonicalRowRepository(connection))
    control = DurableJobControl(repository, clock=_now)
    submission = control.submit(
        job_key="B3-STAGING-001",
        job_type="ECHO",
        payload={"arguments": ["alpha"]},
    )

    store = LocalObjectStore(tmp_path / "objects")
    flow = LocalSealedObjectFlow(store)
    staged = flow.stage(
        sealed_uri="tpaa-parquet://session/dataset/part-000.parquet",
        data=b"parquet-staging-bytes",
        operation_id=submission.record.job_id,
    )
    sealed = store.put_bytes(
        "tpaa-parquet://session/registered/keep.parquet",
        b"registered-sealed-bytes",
    )

    protected = recover_staging_orphans(
        store,
        scheme="tpaa-parquet",
        active_operation_ids=repository.active_job_ids(),
        dry_run=False,
    )
    assert protected.scanned == 1
    assert protected.orphaned == ()
    assert store.verify(staged.staging)
    assert store.verify(sealed)

    control.cancel(
        submission.record.job_id,
        reason_code="USER_CANCELLED",
    )
    reclaimed = recover_staging_orphans(
        store,
        scheme="tpaa-parquet",
        active_operation_ids=repository.active_job_ids(),
        dry_run=False,
    )
    assert reclaimed.orphaned == (staged.staging.logical_uri,)
    assert reclaimed.removed == (staged.staging.logical_uri,)
    assert store.verify(sealed)
    connection.close()
