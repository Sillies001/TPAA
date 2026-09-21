from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tpaa_storage.bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    BootstrapError,
    bootstrap_sqlite,
    verify_sqlite,
)


def test_clean_file_bootstrap_and_verify(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    created = bootstrap_sqlite(database)
    verified = verify_sqlite(database)

    assert created == verified
    assert created.schema_version == "1.6.0"
    assert created.core_baseline == "CB-1.4.0"
    assert created.table_count == 77
    assert created.journal_mode == "wal"
    assert len(created.authority_sha256) == 64
    assert len(created.baseline_lock_sha256) == 64
    assert len(created.physical_schema_sha256) == 64


def test_rebootstrap_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    with pytest.raises(BootstrapError, match="TARGET_NOT_EMPTY"):
        bootstrap_sqlite(database)


def test_missing_table_fails_readiness(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    connection.execute('DROP TABLE "debrief.annotation"')
    connection.commit()
    connection.close()

    with pytest.raises(BootstrapError, match="TABLE_INVENTORY_MISMATCH"):
        verify_sqlite(database)


def test_manifest_tamper_fails_readiness(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    connection.execute(
        f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET schema_version = ? WHERE singleton = 1',
        ("9.9.9",),
    )
    connection.commit()
    connection.close()

    with pytest.raises(BootstrapError, match="BOOTSTRAP_MANIFEST_MISMATCH"):
        verify_sqlite(database)


def test_ddl_tamper_fails_readiness(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    connection.execute('ALTER TABLE "debrief.annotation" ADD COLUMN rogue TEXT')
    connection.commit()
    connection.close()

    with pytest.raises(BootstrapError, match="TABLE_DDL_MISMATCH"):
        verify_sqlite(database)


def test_unified_developer_cli_bootstrap_and_verify(tmp_path: Path) -> None:
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    cli = repo_root / "tools" / "dev" / "tpaa_dev.py"
    database = tmp_path / "tpaa.sqlite3"
    created = subprocess.run(
        [sys.executable, str(cli), "db-bootstrap", str(database)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stderr
    verified = subprocess.run(
        [sys.executable, str(cli), "db-verify", str(database)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert '"schema_version": "1.6.0"' in verified.stdout


def test_verify_missing_database_does_not_create_file(tmp_path: Path) -> None:
    database = tmp_path / "missing.sqlite3"
    with pytest.raises(BootstrapError, match="TARGET_DB_MISSING"):
        verify_sqlite(database)
    assert not database.exists()


def test_unexpected_explicit_index_fails_readiness(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    connection.execute('CREATE INDEX rogue_idx ON "debrief.annotation" (annotation_id)')
    connection.commit()
    connection.close()

    with pytest.raises(BootstrapError, match="UNEXPECTED_SCHEMA_OBJECT"):
        verify_sqlite(database)


def test_verify_does_not_repair_non_wal_database(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
    assert mode is not None and str(mode[0]).lower() == "delete"
    connection.close()

    with pytest.raises(BootstrapError, match="SQLITE_JOURNAL_MODE_MISMATCH"):
        verify_sqlite(database)
    connection = sqlite3.connect(database)
    persisted = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    connection.close()
    assert persisted == "delete"
