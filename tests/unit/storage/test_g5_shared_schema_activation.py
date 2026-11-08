from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tpaa_storage.bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    BootstrapError,
    bootstrap_sqlite,
    postgres_verify_script,
    verify_sqlite,
)

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "baseline" / "CB-1.9.0" / "canonical"
G5 = ROOT / "baseline" / "CB-1.10.0" / "canonical"


def _manifest(path: Path) -> tuple[object, ...]:
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            f'SELECT * FROM "{BOOTSTRAP_MANIFEST_TABLE}" WHERE singleton=1'
        ).fetchone()
    assert row is not None
    return tuple(row)


def test_g4_database_is_reused_by_g5_without_manifest_mutation(tmp_path: Path) -> None:
    database = tmp_path / "shared.sqlite3"
    bootstrap_sqlite(database, authority_root=G4)
    before = _manifest(database)
    verification = verify_sqlite(database, authority_root=G5)
    after = _manifest(database)
    assert verification.schema_version == "1.10.0"
    assert before == after


def test_unrelated_schema_lock_and_schema_drift_remain_rejected(tmp_path: Path) -> None:
    database = tmp_path / "shared.sqlite3"
    bootstrap_sqlite(database, authority_root=G4)
    with sqlite3.connect(database) as connection:
        connection.execute(
            f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET baseline_lock_sha256=? WHERE singleton=1',
            ("0" * 64,),
        )
    with pytest.raises(BootstrapError, match="BOOTSTRAP_MANIFEST_MISMATCH"):
        verify_sqlite(database, authority_root=G5)

    database2 = tmp_path / "drift.sqlite3"
    bootstrap_sqlite(database2, authority_root=G4)
    with sqlite3.connect(database2) as connection:
        connection.execute("CREATE TABLE unexpected_g5_drift(id INTEGER)")
    with pytest.raises(BootstrapError, match="TABLE_INVENTORY_MISMATCH"):
        verify_sqlite(database2, authority_root=G5)


def test_postgres_g5_verifier_accepts_only_explicit_lineage_locks() -> None:
    sql = postgres_verify_script(authority_root=G5)
    assert "baseline_lock_sha256 NOT IN" in sql
    assert "a4864b36ef571b3582c97606ca33a3bd633e0561f776ad4383c9ff6a14dac3d0" in sql
    assert "2b83df248d92137aafde2b0f3934051218929e843afccd9bfd6b3aa63c8582a1" in sql
