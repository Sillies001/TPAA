from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pytest

import tpaa_storage.postgres_repository as module
from tpaa_storage.ports import BaselineMetadataRepository, RepositoryUnitOfWork
from tpaa_storage.postgres_repository import (
    PostgreSQLBaselineMetadataRepository,
    PostgreSQLRepositoryError,
    PostgreSQLServiceUnitOfWork,
)


@dataclass
class FakeCursor:
    connection: FakeConnection
    rows: list[tuple[object, ...]] | None = None
    rowcount: int = -1

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.connection.executed.append((sql, params))
        if "SELECT catalog_schema_sha256" in sql:
            self.rows = [(self.connection.catalog_hash,)]
        elif "_tpaa_bootstrap_manifest" in sql and "catalog_schema_sha256" not in sql:
            self.rows = [self.connection.manifest]
        elif "FROM pg_catalog.pg_class AS c" in sql:
            self.rows = [(name,) for name in sorted(self.connection.tables)]
        elif sql == "CATALOG_HASH" or "SELECT encode(sha256" in sql:
            self.rows = [(self.connection.catalog_hash,)]
        elif sql.startswith("UPDATE"):
            self.rowcount = 1
            if params and isinstance(params[0], str) and "engine_profile = %s" in sql:
                self.connection.manifest = (params[0], *self.connection.manifest[1:])

    def fetchone(self) -> tuple[object, ...] | None:
        return None if not self.rows else self.rows[0]

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self.rows or [])


class FakeConnection:
    def __init__(self, manifest: tuple[object, ...], tables: Iterable[str], catalog_hash: str) -> None:
        self.autocommit = False
        self.manifest = manifest
        self.tables = set(tables)
        self.catalog_hash = catalog_hash
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1
        # restore engine profile if a smoke probe changed it
        if self.manifest[0] != module.POSTGRES_ENGINE_PROFILE:
            self.manifest = (module.POSTGRES_ENGINE_PROFILE, *self.manifest[1:])

    def close(self) -> None:
        self.closes += 1


def _ready() -> tuple[FakeConnection, tuple[object, ...]]:
    authority = module._load_authority()
    physical_hash = module._schema_fingerprint(module._postgres_create_statements(authority))
    catalog_hash = "catalog"
    manifest = (
        module.POSTGRES_ENGINE_PROFILE,
        authority.schema_version,
        authority.core_baseline,
        module.CORE_MODEL_ARTIFACT_ID,
        authority.authority_sha256,
        authority.baseline_lock_sha256,
        physical_hash,
    )
    tables = module._postgres_expected_tables(authority)
    return FakeConnection(manifest, tables, catalog_hash), manifest


def test_postgres_uow_and_metadata_repository_satisfy_engine_neutral_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, _ = _ready()
    monkeypatch.setattr(module, "_postgres_catalog_hash_query", lambda: "CATALOG_HASH")
    connection.catalog_hash = "catalog"
    uow = PostgreSQLServiceUnitOfWork("ignored", connection_factory=lambda _: connection)
    with uow:
        assert isinstance(uow, RepositoryUnitOfWork)
        assert isinstance(uow.metadata, BaselineMetadataRepository)
        assert isinstance(uow.metadata, PostgreSQLBaselineMetadataRepository)
        assert uow.metadata.get().engine_profile == "postgresql-service"
        uow.commit()
    assert connection.commits == 1
    assert connection.closes == 1


def test_uncommitted_and_exception_exit_roll_back(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, _ = _ready()
    monkeypatch.setattr(module, "_postgres_catalog_hash_query", lambda: "CATALOG_HASH")
    with PostgreSQLServiceUnitOfWork("ignored", connection_factory=lambda _: connection):
        pass
    assert connection.rollbacks == 1

    second, _ = _ready()
    with pytest.raises(RuntimeError, match="injected"):
        with PostgreSQLServiceUnitOfWork("ignored", connection_factory=lambda _: second):
            raise RuntimeError("injected")
    assert second.rollbacks == 1


def test_read_only_transaction_is_set_before_repository_use(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, _ = _ready()
    monkeypatch.setattr(module, "_postgres_catalog_hash_query", lambda: "CATALOG_HASH")
    with PostgreSQLServiceUnitOfWork(
        "ignored", read_only=True, connection_factory=lambda _: connection
    ) as uow:
        uow.commit()
    assert connection.executed[0][0] == "SET TRANSACTION READ ONLY"


def test_autocommit_connection_is_rejected() -> None:
    connection, _ = _ready()
    connection.autocommit = True
    with pytest.raises(PostgreSQLRepositoryError) as captured:
        with PostgreSQLServiceUnitOfWork("ignored", connection_factory=lambda _: connection):
            pass
    assert captured.value.reason == "AUTOCOMMIT_FORBIDDEN"
    assert connection.closes == 1


def test_missing_table_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, _ = _ready()
    connection.tables.remove("debrief.annotation")
    monkeypatch.setattr(module, "_postgres_catalog_hash_query", lambda: "CATALOG_HASH")
    with pytest.raises(PostgreSQLRepositoryError) as captured:
        with PostgreSQLServiceUnitOfWork("ignored", connection_factory=lambda _: connection):
            pass
    assert captured.value.reason == "TABLE_INVENTORY_MISMATCH"


def test_missing_psycopg_dependency_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_: str) -> Any:
        raise ModuleNotFoundError("psycopg")

    monkeypatch.setattr(module, "import_module", missing)
    with pytest.raises(PostgreSQLRepositoryError) as captured:
        module._default_connect("postgresql://ignored")
    assert captured.value.reason == "PSYCOPG_DEPENDENCY_MISSING"
