"""SQLite Desktop Repository skeleton for M0-STO-002.

This module implements the ADR-M0-004 synchronous sqlite3 adapter boundary.
It never bootstraps, migrates, repairs, or redefines the Canonical schema.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    SQLITE_ENGINE_PROFILE,
    BootstrapError,
    verify_sqlite,
)
from .core_publication_ledger import SQLiteCorePublicationLedger
from .ports import RepositoryBaselineMetadata


class SQLiteRepositoryError(RuntimeError):
    """Deterministic fail-closed error for the SQLite Repository adapter."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"SQLITE_REPOSITORY_FAIL reason={reason} detail={detail}")


_WRITER_LOCKS_GUARD = threading.Lock()
_WRITER_LOCKS: dict[str, threading.Lock] = {}


def _writer_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _WRITER_LOCKS_GUARD:
        return _WRITER_LOCKS.setdefault(key, threading.Lock())


def _open_existing(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SQLiteRepositoryError("TARGET_DB_MISSING", f"path={path}")
    uri = path.resolve().as_uri() + "?mode=rw"
    try:
        connection = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=0.0)
    except sqlite3.DatabaseError as exc:
        raise SQLiteRepositoryError("SQLITE_CONNECT_ERROR", str(exc)) from exc
    connection.row_factory = sqlite3.Row
    return connection


def _configure_runtime_connection(connection: sqlite3.Connection, *, read_only: bool) -> None:
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        if foreign_keys is None or int(foreign_keys[0]) != 1:
            raise SQLiteRepositoryError(
                "SQLITE_FOREIGN_KEYS_DISABLED", "PRAGMA foreign_keys did not enable"
            )
        journal = connection.execute("PRAGMA journal_mode").fetchone()
        journal_mode = str(journal[0]).lower() if journal is not None else ""
        if journal_mode != "wal":
            raise SQLiteRepositoryError(
                "SQLITE_WAL_REQUIRED", f"expected=wal actual={journal_mode!r}"
            )
        connection.execute(f"PRAGMA query_only = {'ON' if read_only else 'OFF'}")
    except sqlite3.DatabaseError as exc:
        raise SQLiteRepositoryError("SQLITE_CONFIGURATION_ERROR", str(exc)) from exc


class SQLiteBaselineMetadataRepository:
    """Read-only bootstrap provenance repository inside an active SQLite UoW."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self) -> RepositoryBaselineMetadata:
        try:
            row = self._connection.execute(
                f'''SELECT engine_profile, schema_version, core_baseline,
                           authority_artifact_id, authority_sha256,
                           baseline_lock_sha256, physical_schema_sha256
                    FROM "{BOOTSTRAP_MANIFEST_TABLE}" WHERE singleton = 1'''
            ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise SQLiteRepositoryError("METADATA_READ_ERROR", str(exc)) from exc
        if row is None:
            raise SQLiteRepositoryError("BOOTSTRAP_MANIFEST_MISSING", "singleton row is absent")
        return RepositoryBaselineMetadata(
            engine_profile=str(row[0]),
            schema_version=str(row[1]),
            core_baseline=str(row[2]),
            authority_artifact_id=str(row[3]),
            authority_sha256=str(row[4]),
            baseline_lock_sha256=str(row[5]),
            physical_schema_sha256=str(row[6]),
        )


class SQLiteDesktopUnitOfWork:
    """One-connection explicit SQLite Desktop transaction boundary."""

    def __init__(self, database: str | Path, *, write: bool = False) -> None:
        self._path = Path(database)
        self._write = write
        self._connection: sqlite3.Connection | None = None
        self._writer_lease: threading.Lock | None = None
        self._finalized = False
        self.metadata: SQLiteBaselineMetadataRepository
        self.publication: SQLiteCorePublicationLedger

    @property
    def write(self) -> bool:
        return self._write

    @property
    def active(self) -> bool:
        return self._connection is not None and not self._finalized

    def __enter__(self) -> SQLiteDesktopUnitOfWork:
        if self._connection is not None:
            raise SQLiteRepositoryError("UOW_REENTRY", "Unit of Work is already entered")
        try:
            verification = verify_sqlite(self._path)
        except BootstrapError as exc:
            raise SQLiteRepositoryError("DATABASE_NOT_READY", str(exc)) from exc
        if verification.engine_profile != SQLITE_ENGINE_PROFILE:
            raise SQLiteRepositoryError(
                "ENGINE_PROFILE_MISMATCH",
                f"expected={SQLITE_ENGINE_PROFILE} actual={verification.engine_profile}",
            )

        if self._write:
            lease = _writer_lock(self._path)
            if not lease.acquire(blocking=False):
                raise SQLiteRepositoryError(
                    "SINGLE_WRITER_BUSY", f"database={self._path.resolve()}"
                )
            self._writer_lease = lease

        connection: sqlite3.Connection | None = None
        try:
            connection = _open_existing(self._path)
            _configure_runtime_connection(connection, read_only=not self._write)
            connection.execute("BEGIN IMMEDIATE" if self._write else "BEGIN")
            self._connection = connection
            self._finalized = False
            self.metadata = SQLiteBaselineMetadataRepository(connection)
            self.publication = SQLiteCorePublicationLedger(connection)
            return self
        except Exception:
            if connection is not None:
                connection.close()
            self._release_writer_lease()
            raise

    def _require_active(self) -> sqlite3.Connection:
        if self._connection is None or self._finalized:
            raise SQLiteRepositoryError("UOW_NOT_ACTIVE", "no active transaction")
        return self._connection

    def commit(self) -> None:
        connection = self._require_active()
        try:
            connection.execute("COMMIT")
        except sqlite3.DatabaseError as exc:
            raise SQLiteRepositoryError("COMMIT_FAILED", str(exc)) from exc
        self._finalized = True

    def rollback(self) -> None:
        connection = self._require_active()
        try:
            connection.execute("ROLLBACK")
        except sqlite3.DatabaseError as exc:
            raise SQLiteRepositoryError("ROLLBACK_FAILED", str(exc)) from exc
        self._finalized = True

    def _diagnostic_execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """Internal M0 readiness hook; SQL never crosses an engine-neutral port."""
        connection = self._require_active()
        try:
            return connection.execute(sql, parameters)
        except sqlite3.DatabaseError as exc:
            raise SQLiteRepositoryError("DIAGNOSTIC_SQL_FAILED", str(exc)) from exc

    def _release_writer_lease(self) -> None:
        if self._writer_lease is not None:
            self._writer_lease.release()
            self._writer_lease = None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        connection = self._connection
        try:
            if connection is not None and not self._finalized:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.DatabaseError as rollback_exc:
                    raise SQLiteRepositoryError("ROLLBACK_FAILED", str(rollback_exc)) from rollback_exc
                finally:
                    self._finalized = True
        finally:
            if connection is not None:
                connection.close()
            self._connection = None
            self._release_writer_lease()


def sqlite_repository_smoke(database: str | Path) -> dict[str, Any]:
    """Run deterministic M0-STO-002 read/write/UoW/single-writer diagnostics."""

    path = Path(database)
    try:
        before = verify_sqlite(path)
    except BootstrapError as exc:
        raise SQLiteRepositoryError("DATABASE_NOT_READY", str(exc)) from exc

    with SQLiteDesktopUnitOfWork(path) as uow:
        metadata = uow.metadata.get()
        uow.commit()

    with SQLiteDesktopUnitOfWork(path, write=True) as uow:
        cursor = uow._diagnostic_execute(
            f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" '
            "SET physical_schema_sha256 = physical_schema_sha256 WHERE singleton = ?",
            (1,),
        )
        if cursor.rowcount != 1:
            raise SQLiteRepositoryError("WRITE_SMOKE_ROWCOUNT", f"actual={cursor.rowcount}")
        uow.commit()

    rollback_probe = "__TPAA_M0_STO_002_ROLLBACK_PROBE__"
    with SQLiteDesktopUnitOfWork(path, write=True) as uow:
        uow._diagnostic_execute(
            f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET engine_profile = ? WHERE singleton = 1',
            (rollback_probe,),
        )
        observed = uow.metadata.get()
        if observed.engine_profile != rollback_probe:
            raise SQLiteRepositoryError("ROLLBACK_PROBE_WRITE_MISSING", observed.engine_profile)
        # no commit: __exit__ must roll back
    try:
        verify_sqlite(path)
    except BootstrapError as exc:
        raise SQLiteRepositoryError("ROLLBACK_VERIFY_FAILED", str(exc)) from exc

    try:
        with SQLiteDesktopUnitOfWork(path, write=True) as uow:
            uow._diagnostic_execute(
                f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET engine_profile = ? WHERE singleton = 1',
                ("__TPAA_M0_STO_002_EXCEPTION_PROBE__",),
            )
            raise RuntimeError("M0-STO-002 injected transaction failure")
    except RuntimeError as exc:
        if str(exc) != "M0-STO-002 injected transaction failure":
            raise
    try:
        verify_sqlite(path)
    except BootstrapError as exc:
        raise SQLiteRepositoryError("EXCEPTION_ROLLBACK_VERIFY_FAILED", str(exc)) from exc

    with SQLiteDesktopUnitOfWork(path, write=True):
        try:
            with SQLiteDesktopUnitOfWork(path, write=True):
                raise AssertionError("second writer unexpectedly entered")
        except SQLiteRepositoryError as exc:
            if exc.reason != "SINGLE_WRITER_BUSY":
                raise

    try:
        after = verify_sqlite(path)
    except BootstrapError as exc:
        raise SQLiteRepositoryError("FINAL_VERIFY_FAILED", str(exc)) from exc
    if before != after:
        raise SQLiteRepositoryError("SMOKE_CHANGED_DATABASE", f"before={before!r} after={after!r}")

    return {
        "engine_profile": metadata.engine_profile,
        "schema_version": metadata.schema_version,
        "core_baseline": metadata.core_baseline,
        "wal": "PASS",
        "foreign_keys": "PASS",
        "read_transaction": "PASS",
        "write_commit": "PASS",
        "uncommitted_exit_rollback": "PASS",
        "exception_rollback": "PASS",
        "single_writer": "PASS",
        "metadata": asdict(metadata),
    }
