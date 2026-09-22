"""PostgreSQL Service Repository skeleton for M0-STO-003.

The adapter implements the synchronous Psycopg 3 boundary frozen by ADR-M0-004.
It opens only an existing M0-STO-001-verified database and never bootstraps,
migrates, repairs, or redefines the Canonical schema.
"""

from __future__ import annotations

from dataclasses import asdict
from importlib import import_module
from typing import Any, Callable

from .bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    CORE_MODEL_ARTIFACT_ID,
    POSTGRES_ENGINE_PROFILE,
    _load_authority,
    _postgres_catalog_hash_query,
    _postgres_create_statements,
    _postgres_expected_tables,
    _schema_fingerprint,
)
from .ports import RepositoryBaselineMetadata


class PostgreSQLRepositoryError(RuntimeError):
    """Deterministic fail-closed error for the PostgreSQL Repository adapter."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"POSTGRES_REPOSITORY_FAIL reason={reason} detail={detail}")


ConnectionFactory = Callable[[str], Any]


def _default_connect(conninfo: str) -> Any:
    """Import Psycopg only at the concrete adapter edge."""

    try:
        psycopg = import_module("psycopg")
    except ModuleNotFoundError as exc:
        raise PostgreSQLRepositoryError(
            "PSYCOPG_DEPENDENCY_MISSING",
            "M0-STO-003 requires governed dependency psycopg[binary]==3.3.6",
        ) from exc
    try:
        return psycopg.connect(conninfo, autocommit=False)
    except Exception as exc:  # psycopg exception hierarchy is intentionally adapter-local
        raise PostgreSQLRepositoryError("POSTGRES_CONNECT_ERROR", str(exc)) from exc


def _manifest_name() -> str:
    return f'"public"."{BOOTSTRAP_MANIFEST_TABLE}"'


class PostgreSQLBaselineMetadataRepository:
    """Read bootstrap provenance through the engine-neutral Repository port."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def get(self) -> RepositoryBaselineMetadata:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    f'''SELECT engine_profile, schema_version, core_baseline,
                               authority_artifact_id, authority_sha256,
                               baseline_lock_sha256, physical_schema_sha256
                        FROM {_manifest_name()} WHERE singleton = 1'''
                )
                row = cursor.fetchone()
        except Exception as exc:
            raise PostgreSQLRepositoryError("METADATA_READ_FAILED", str(exc)) from exc
        if row is None:
            raise PostgreSQLRepositoryError("BOOTSTRAP_MANIFEST_MISSING", "singleton row is absent")
        return RepositoryBaselineMetadata(
            engine_profile=str(row[0]),
            schema_version=str(row[1]),
            core_baseline=str(row[2]),
            authority_artifact_id=str(row[3]),
            authority_sha256=str(row[4]),
            baseline_lock_sha256=str(row[5]),
            physical_schema_sha256=str(row[6]),
        )


def _verify_ready(connection: Any) -> RepositoryBaselineMetadata:
    """Verify M0-STO-001 schema/provenance using the live PostgreSQL catalog."""

    authority = _load_authority()
    expected_tables = set(_postgres_expected_tables(authority))
    expected_manifest = {
        "engine_profile": POSTGRES_ENGINE_PROFILE,
        "schema_version": authority.schema_version,
        "core_baseline": authority.core_baseline,
        "authority_artifact_id": CORE_MODEL_ARTIFACT_ID,
        "authority_sha256": authority.authority_sha256,
        "baseline_lock_sha256": authority.baseline_lock_sha256,
    }
    repository = PostgreSQLBaselineMetadataRepository(connection)
    metadata = repository.get()
    actual_manifest = {
        "engine_profile": metadata.engine_profile,
        "schema_version": metadata.schema_version,
        "core_baseline": metadata.core_baseline,
        "authority_artifact_id": metadata.authority_artifact_id,
        "authority_sha256": metadata.authority_sha256,
        "baseline_lock_sha256": metadata.baseline_lock_sha256,
    }
    if actual_manifest != expected_manifest:
        raise PostgreSQLRepositoryError(
            "BOOTSTRAP_MANIFEST_MISMATCH",
            f"expected={expected_manifest!r} actual={actual_manifest!r}",
        )
    expected_projection_hash = _schema_fingerprint(_postgres_create_statements(authority))
    if metadata.physical_schema_sha256 != expected_projection_hash:
        raise PostgreSQLRepositoryError(
            "PROJECTION_HASH_MISMATCH",
            f"expected={expected_projection_hash} actual={metadata.physical_schema_sha256}",
        )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT n.nspname || '.' || c.relname
                   FROM pg_catalog.pg_class AS c
                   JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                   WHERE c.relkind = 'r'
                     AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                   ORDER BY 1"""
            )
            actual_tables = {str(row[0]) for row in cursor.fetchall()}
            cursor.execute(_postgres_catalog_hash_query())
            hash_row = cursor.fetchone()
            cursor.execute(
                f"SELECT catalog_schema_sha256 FROM {_manifest_name()} WHERE singleton = 1"
            )
            expected_catalog_row = cursor.fetchone()
    except Exception as exc:
        raise PostgreSQLRepositoryError("SCHEMA_VERIFY_QUERY_FAILED", str(exc)) from exc

    if actual_tables != expected_tables:
        missing = sorted(set(expected_tables) - actual_tables)
        extra = sorted(actual_tables - set(expected_tables))
        raise PostgreSQLRepositoryError(
            "TABLE_INVENTORY_MISMATCH", f"missing={missing} extra={extra}"
        )
    actual_catalog_hash = None if hash_row is None else str(hash_row[0])
    expected_catalog_hash = None if expected_catalog_row is None else str(expected_catalog_row[0])
    if not expected_catalog_hash or actual_catalog_hash != expected_catalog_hash:
        raise PostgreSQLRepositoryError(
            "PHYSICAL_SCHEMA_MISMATCH",
            f"expected={expected_catalog_hash!r} actual={actual_catalog_hash!r}",
        )
    return metadata


class PostgreSQLServiceUnitOfWork:
    """Synchronous Psycopg Unit of Work implementing the shared Repository port."""

    def __init__(
        self,
        conninfo: str,
        *,
        read_only: bool = False,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._conninfo = conninfo
        self._read_only = read_only
        self._connection_factory = connection_factory or _default_connect
        self._connection: Any | None = None
        self._finalized = True
        self.metadata: PostgreSQLBaselineMetadataRepository

    @property
    def active(self) -> bool:
        return self._connection is not None and not self._finalized

    def __enter__(self) -> PostgreSQLServiceUnitOfWork:
        if self._connection is not None:
            raise PostgreSQLRepositoryError("UOW_ALREADY_ACTIVE", "unit of work already entered")
        connection = self._connection_factory(self._conninfo)
        try:
            if getattr(connection, "autocommit", False):
                raise PostgreSQLRepositoryError("AUTOCOMMIT_FORBIDDEN", "connection.autocommit must be false")
            if self._read_only:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
            _verify_ready(connection)
            self._connection = connection
            self._finalized = False
            self.metadata = PostgreSQLBaselineMetadataRepository(connection)
            return self
        except Exception:
            try:
                connection.rollback()
            finally:
                connection.close()
            raise

    def _require_active(self) -> Any:
        if self._connection is None or self._finalized:
            raise PostgreSQLRepositoryError("UOW_NOT_ACTIVE", "no active transaction")
        return self._connection

    def commit(self) -> None:
        connection = self._require_active()
        try:
            connection.commit()
        except Exception as exc:
            raise PostgreSQLRepositoryError("COMMIT_FAILED", str(exc)) from exc
        self._finalized = True

    def rollback(self) -> None:
        connection = self._require_active()
        try:
            connection.rollback()
        except Exception as exc:
            raise PostgreSQLRepositoryError("ROLLBACK_FAILED", str(exc)) from exc
        self._finalized = True

    def _diagnostic_execute(self, sql: str, parameters: tuple[object, ...] = ()) -> Any:
        """Internal M0 conformance hook; SQL never crosses an engine-neutral port."""
        connection = self._require_active()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, parameters)
            return cursor
        except Exception as exc:
            raise PostgreSQLRepositoryError("DIAGNOSTIC_SQL_FAILED", str(exc)) from exc

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        connection = self._connection
        try:
            if connection is not None and not self._finalized:
                try:
                    connection.rollback()
                except Exception as rollback_exc:
                    raise PostgreSQLRepositoryError("ROLLBACK_FAILED", str(rollback_exc)) from rollback_exc
                finally:
                    self._finalized = True
        finally:
            if connection is not None:
                connection.close()
            self._connection = None


def postgres_repository_smoke(conninfo: str) -> dict[str, Any]:
    """Run deterministic real-server M0-STO-003 Repository/UoW diagnostics."""

    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        metadata = uow.metadata.get()
        uow.commit()

    rollback_probe = "__TPAA_M0_STO_003_ROLLBACK_PROBE__"
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        uow._diagnostic_execute(
            f"UPDATE {_manifest_name()} SET engine_profile = %s WHERE singleton = %s",
            (rollback_probe, 1),
        )
        if uow.metadata.get().engine_profile != rollback_probe:
            raise PostgreSQLRepositoryError("ROLLBACK_PROBE_WRITE_MISSING", rollback_probe)
        # no commit: exit must roll back

    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        after_rollback = uow.metadata.get()
        if after_rollback.engine_profile != POSTGRES_ENGINE_PROFILE:
            raise PostgreSQLRepositoryError(
                "UNCOMMITTED_EXIT_ROLLBACK_FAILED", after_rollback.engine_profile
            )
        uow.commit()

    try:
        with PostgreSQLServiceUnitOfWork(conninfo) as uow:
            uow._diagnostic_execute(
                f"UPDATE {_manifest_name()} SET engine_profile = %s WHERE singleton = 1",
                ("__TPAA_M0_STO_003_EXCEPTION_PROBE__",),
            )
            raise RuntimeError("M0-STO-003 injected transaction failure")
    except RuntimeError as exc:
        if str(exc) != "M0-STO-003 injected transaction failure":
            raise

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        cursor = uow._diagnostic_execute(
            f"UPDATE {_manifest_name()} SET physical_schema_sha256 = physical_schema_sha256 "
            "WHERE singleton = %s",
            (1,),
        )
        if cursor.rowcount != 1:
            raise PostgreSQLRepositoryError("WRITE_SMOKE_ROWCOUNT", f"actual={cursor.rowcount}")
        uow.commit()

    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        final = uow.metadata.get()
        uow.commit()
    if final != metadata:
        raise PostgreSQLRepositoryError("SMOKE_CHANGED_DATABASE", f"before={metadata!r} after={final!r}")

    return {
        "engine_profile": metadata.engine_profile,
        "schema_version": metadata.schema_version,
        "core_baseline": metadata.core_baseline,
        "read_transaction": "PASS",
        "write_commit": "PASS",
        "uncommitted_exit_rollback": "PASS",
        "exception_rollback": "PASS",
        "metadata": asdict(metadata),
    }
