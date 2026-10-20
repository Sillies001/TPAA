from __future__ import annotations

from pathlib import Path

from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
    create_desktop_production_backup,
)
from tpaa_storage import AuditLogWrite, SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.5.0" / "canonical"


def test_prcb_r8_operational_metrics_are_bounded_and_secret_safe(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.sqlite3"
    object_root = tmp_path / "objects"
    bootstrap_sqlite(database)
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=AUTHORITY,
            object_root=object_root,
            desktop_database_path=database,
        )
    )
    failed = runtime.application.submit_job(
        idempotency_key="r8-observability-failure",
        command="UNKNOWN_DOMAIN_COMMAND",
        payload={},
        actor="ROLE:ANALYST",
    )
    assert failed.record.status.value == "FAILED"
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        uow.audit_log.append(
            AuditLogWrite(
                actor_id=None,
                principal_key="ROLE:ANALYST",
                action="R8_DENIAL_PROBE",
                object_type="RUNTIME_METRICS",
                object_id="aggregate-only",
                outcome="DENY",
            )
        )
        uow.commit()

    before_backup = runtime.application.operational_status()
    assert before_backup["operational_metrics_schema"] == "TPAA_OPERATIONAL_METRICS_V1"
    assert before_backup["job_status_counts"]["FAILED"] == 1
    assert before_backup["job_active_count"] == 0
    assert before_backup["job_failure_code_counts"] == {"PRCB_C2_DOMAIN_COMMAND_UNSUPPORTED": 1}
    assert before_backup["access_denial_count"] == 1
    assert before_backup["adapter_error_count"] == 0
    assert before_backup["backup_status"]["state"] == "NEVER_VERIFIED"
    assert before_backup["database_metric_query_latency_us"] >= 1
    assert before_backup["object_scan_latency_us"] >= 1
    assert before_backup["storage_capacity_bytes"] > 0
    assert before_backup["storage_free_bytes"] >= 0

    create_desktop_production_backup(
        database=database,
        object_root=object_root,
        destination=tmp_path / "backup",
        authority_root=AUTHORITY,
    )
    after_backup = runtime.application.operational_status()
    assert after_backup["backup_status"]["state"] == "VERIFIED"
    assert after_backup["backup_status"]["age_seconds"] >= 0
    assert "manifest_path" not in after_backup["backup_status"]
    lowered = repr(after_backup).lower()
    for forbidden in (
        "authorization",
        "cookie",
        "credential",
        "password",
        "secret",
        "token",
    ):
        assert forbidden not in lowered
