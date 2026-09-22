from __future__ import annotations

import inspect

from tpaa_storage.ports import RepositoryUnitOfWork
from tpaa_storage.postgres_repository import PostgreSQLServiceUnitOfWork
from tpaa_storage.sqlite_repository import SQLiteDesktopUnitOfWork


def test_sqlite_and_postgres_uow_implement_shared_transaction_members() -> None:
    required = {"__enter__", "__exit__", "commit", "rollback"}
    port_members = set(RepositoryUnitOfWork.__dict__)
    assert required.issubset(port_members)
    for adapter in (SQLiteDesktopUnitOfWork, PostgreSQLServiceUnitOfWork):
        assert required.issubset(set(adapter.__dict__))
        assert hasattr(adapter, "active")


def test_driver_specific_constructor_inputs_stay_on_concrete_adapters() -> None:
    port_signature = inspect.signature(RepositoryUnitOfWork.__enter__)
    assert tuple(port_signature.parameters) == ("self",)

    sqlite_signature = inspect.signature(SQLiteDesktopUnitOfWork)
    postgres_signature = inspect.signature(PostgreSQLServiceUnitOfWork)
    assert "database" in sqlite_signature.parameters
    assert "conninfo" in postgres_signature.parameters


def test_repository_port_source_contains_no_database_driver_or_dialect_names() -> None:
    source = inspect.getsource(RepositoryUnitOfWork).lower()
    for forbidden in ("sqlite", "postgres", "psycopg", "dsn", "dialect", "sqlalchemy", "asyncpg"):
        assert forbidden not in source
