from __future__ import annotations

import sqlite3

import pytest

from tpaa_storage import bootstrap as bootstrap_module
from tpaa_storage.bootstrap import EXPECTED_DB_SCHEMA_VERSION, BootstrapError


def test_authority_is_exact_schema_1_6_0_and_all_tables_agree() -> None:
    authority = bootstrap_module._load_authority()
    assert authority.schema_version == EXPECTED_DB_SCHEMA_VERSION
    assert authority.core_baseline == "CB-1.4.0"
    assert len(authority.tables) == 77
    assert all(
        table["schema_version"] == EXPECTED_DB_SCHEMA_VERSION
        for table in authority.tables.values()
    )


def test_sqlite_projection_is_deterministic_and_complete() -> None:
    authority = bootstrap_module._load_authority()
    first = bootstrap_module._sqlite_create_statements(authority)
    second = bootstrap_module._sqlite_create_statements(authority)
    assert first == second
    assert len(first) == len(authority.tables) == 77
    assert len(set(first)) == 77
    assert all(statement.startswith('CREATE TABLE "') for statement in first)


def test_bootstrap_rolls_back_all_tables_when_a_statement_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    authority = bootstrap_module._load_authority()
    original = bootstrap_module._sqlite_create_statements

    def broken(authority_arg: bootstrap_module._SchemaAuthority) -> tuple[str, ...]:
        statements = list(original(authority_arg))
        statements[5] = "CREATE TABLE broken ("
        return tuple(statements)

    monkeypatch.setattr(bootstrap_module, "_sqlite_create_statements", broken)
    connection = sqlite3.connect(":memory:")
    with pytest.raises(sqlite3.DatabaseError):
        bootstrap_module._bootstrap_connection(connection, authority=authority, file_backed=False)
    assert bootstrap_module._user_tables(connection) == ()
    connection.close()


def test_bootstrap_rejects_non_empty_target() -> None:
    authority = bootstrap_module._load_authority()
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE foreign_table (id INTEGER)")
    with pytest.raises(BootstrapError, match="TARGET_NOT_EMPTY"):
        bootstrap_module._bootstrap_connection(connection, authority=authority, file_backed=False)
    connection.close()
