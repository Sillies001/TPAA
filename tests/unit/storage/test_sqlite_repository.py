from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tpaa_storage.bootstrap import bootstrap_sqlite, verify_sqlite
from tpaa_storage.ports import BaselineMetadataRepository, RepositoryUnitOfWork
from tpaa_storage.sqlite_repository import (
    SQLiteBaselineMetadataRepository,
    SQLiteDesktopUnitOfWork,
    SQLiteRepositoryError,
    sqlite_repository_smoke,
)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "desktop.sqlite3"
    bootstrap_sqlite(path)
    return path


def test_sqlite_uow_and_metadata_repository_satisfy_engine_neutral_ports(tmp_path: Path) -> None:
    path = _database(tmp_path)
    uow = SQLiteDesktopUnitOfWork(path)
    with uow:
        assert isinstance(uow, RepositoryUnitOfWork)
        assert isinstance(uow.metadata, BaselineMetadataRepository)
        assert isinstance(uow.metadata, SQLiteBaselineMetadataRepository)
        metadata = uow.metadata.get()
        assert metadata.engine_profile == "sqlite-desktop"
        assert metadata.schema_version == "1.6.0"
        assert metadata.core_baseline == "CB-1.4.0"
        uow.commit()


def test_read_uow_is_query_only(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with SQLiteDesktopUnitOfWork(path) as uow:
        with pytest.raises(SQLiteRepositoryError) as captured:
            uow._diagnostic_execute(
                'UPDATE "_tpaa_bootstrap_manifest" SET engine_profile = engine_profile WHERE singleton = 1'
            )
        assert captured.value.reason == "DIAGNOSTIC_SQL_FAILED"


def test_write_uow_requires_explicit_commit_and_uncommitted_exit_rolls_back(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with SQLiteDesktopUnitOfWork(path, write=True) as uow:
        uow._diagnostic_execute(
            'UPDATE "_tpaa_bootstrap_manifest" SET engine_profile = ? WHERE singleton = 1',
            ("probe",),
        )
        assert uow.metadata.get().engine_profile == "probe"
    assert verify_sqlite(path).engine_profile == "sqlite-desktop"


def test_exception_rolls_back_write_uow(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with pytest.raises(RuntimeError, match="injected"):
        with SQLiteDesktopUnitOfWork(path, write=True) as uow:
            uow._diagnostic_execute(
                'UPDATE "_tpaa_bootstrap_manifest" SET engine_profile = ? WHERE singleton = 1',
                ("probe",),
            )
            raise RuntimeError("injected")
    assert verify_sqlite(path).engine_profile == "sqlite-desktop"


def test_second_writer_is_rejected_deterministically(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with SQLiteDesktopUnitOfWork(path, write=True):
        with pytest.raises(SQLiteRepositoryError) as captured:
            with SQLiteDesktopUnitOfWork(path, write=True):
                pass
        assert captured.value.reason == "SINGLE_WRITER_BUSY"


def test_runtime_requires_existing_verified_wal_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(SQLiteRepositoryError) as captured:
        with SQLiteDesktopUnitOfWork(missing):
            pass
    assert captured.value.reason == "DATABASE_NOT_READY"
    assert not missing.exists()

    path = _database(tmp_path)
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0].lower() == "delete"
    finally:
        connection.close()
    with pytest.raises(SQLiteRepositoryError) as captured:
        with SQLiteDesktopUnitOfWork(path):
            pass
    assert captured.value.reason == "DATABASE_NOT_READY"


def test_full_sqlite_repository_smoke_preserves_verified_database(tmp_path: Path) -> None:
    path = _database(tmp_path)
    before = verify_sqlite(path)
    result = sqlite_repository_smoke(path)
    after = verify_sqlite(path)
    assert result["wal"] == "PASS"
    assert result["single_writer"] == "PASS"
    assert result["write_commit"] == "PASS"
    assert result["uncommitted_exit_rollback"] == "PASS"
    assert result["exception_rollback"] == "PASS"
    assert before == after


def test_begin_immediate_holds_sqlite_database_writer_lock(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with SQLiteDesktopUnitOfWork(path, write=True):
        competing = sqlite3.connect(path, isolation_level=None, timeout=0.0)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                competing.execute("BEGIN IMMEDIATE")
        finally:
            competing.close()


def test_commit_finalizes_uow_and_cannot_be_reused(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with SQLiteDesktopUnitOfWork(path, write=True) as uow:
        uow._diagnostic_execute(
            'UPDATE "_tpaa_bootstrap_manifest" SET engine_profile = engine_profile WHERE singleton = 1'
        )
        uow.commit()
        assert uow.active is False
        with pytest.raises(SQLiteRepositoryError) as captured:
            uow.commit()
        assert captured.value.reason == "UOW_NOT_ACTIVE"
    assert verify_sqlite(path).engine_profile == "sqlite-desktop"
