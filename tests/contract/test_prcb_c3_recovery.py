from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c3_production_recovery_is_profile_specific_and_secret_safe() -> None:
    source = (ROOT / "src" / "tpaa_runtime" / "recovery.py").read_text(
        encoding="utf-8"
    )
    assert "TPAA_PRCB_C3_PRODUCTION_BACKUP_V1" in source
    assert "create_desktop_production_backup" in source
    assert "restore_desktop_production_backup" in source
    assert "create_service_production_backup" in source
    assert "restore_service_production_backup" in source
    assert '"pg_dump"' in source
    assert '"pg_restore"' in source
    assert '"PGPASSWORD"' in source
    assert "--no-password" in source
    assert "password=super-secret" not in source
    assert "verify_sqlite" in source
    assert "PostgreSQLServiceUnitOfWork" in source
