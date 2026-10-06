from __future__ import annotations

from pathlib import Path

from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_prcb_c3_durable_job_submit_persists_actor_audit_in_same_db(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=AUTHORITY,
            object_root=tmp_path / "objects",
            desktop_database_path=database,
        )
    )
    submission = runtime.application.submit_job(
        idempotency_key="prcb-c3-audit-unknown",
        command="UNKNOWN_DOMAIN_COMMAND",
        payload={},
        actor="ROLE:ANALYST",
    )
    assert submission.record.status.value == "FAILED"

    with SQLiteDesktopUnitOfWork(database) as uow:
        rows = uow.audit_log.rows()
        uow.commit()
    matches = [
        row
        for row in rows
        if row.action == "JOB_SUBMIT"
        and row.object_id == submission.record.job_id
    ]
    assert len(matches) == 1
    assert matches[0].principal_key == "ROLE:ANALYST"
    assert matches[0].request_id == "prcb-c3-audit-unknown"
    assert matches[0].details == {"status": "QUEUED"}
