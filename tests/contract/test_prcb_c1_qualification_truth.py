from __future__ import annotations

from pathlib import Path

from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import bootstrap_sqlite


def test_prcb_runtime_reports_historical_1_0_and_pending_1_0_1(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    root = Path(__file__).resolve().parents[2]
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=root / "baseline" / "CB-1.4.0" / "canonical",
            object_root=tmp_path / "objects",
            desktop_database_path=database,
        )
    )
    status = runtime.application.qualification_status()
    assert status["schema"] == "TPAA_PRCB_PRODUCT_QUALIFICATION_STATUS_V1"
    assert status["historical_release"] == {
        "product_version": "1.0.0",
        "qualification": "PIQB_1_0_QUALIFIED",
        "source_revision": "0ed48a85944699e0bbac1fe76b84c88a319121c1",
        "run_number": 636,
        "actions_run_id": 37271874369,
        "required_jobs_success": 14,
        "required_jobs_total": 14,
        "protected_main": True,
    }
    assert status["target_release"] == {
        "product_version": "1.0.1",
        "qualification": "TPAA_1_0_1_NOT_YET_QUALIFIED",
        "formal_release_claimed": False,
    }
    operational = runtime.application.operational_status()
    assert operational["reason_code"] == "PRCB_RUNTIME_STATUS"
    assert operational["fields"]["formal_release_claimed"] is False


def test_prcb_production_does_not_reuse_legacy_b3_qualification_status() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src" / "tpaa_runtime" / "production.py").read_text(
        encoding="utf-8"
    )
    assert "ProductQualificationStatus" not in source
    assert "ProductOperationalStatus" not in source
    assert "PRCBQualificationStatus" in source
