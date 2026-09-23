from __future__ import annotations

from collections.abc import Mapping

import pytest

from tpaa_storage.bootstrap import (
    BootstrapError,
    _postgres_create_statements,
    _postgres_table_order,
    _SchemaAuthority,
    _table_dependencies,
    postgres_create_statements,
)


def _authority(tables: Mapping[str, Mapping[str, object]]) -> _SchemaAuthority:
    return _SchemaAuthority(
        schema_version="1.6.0",
        core_baseline="CB-1.4.0",
        authority_sha256="a" * 64,
        baseline_lock_sha256="b" * 64,
        tables=tables,
    )


def _table(*field_sql: str) -> Mapping[str, object]:
    fields = []
    for sql in field_sql:
        parts = sql.split()
        fields.append({"name": parts[0], "type": parts[1], "sql": sql})
    return {"schema_version": "1.6.0", "fields": fields}


def test_postgres_projection_covers_frozen_authority_deterministically() -> None:
    first = postgres_create_statements()
    second = postgres_create_statements()

    assert first == second
    assert len(first) == 88  # 11 schemas + 77 Canonical tables
    assert sum(statement.startswith("CREATE SCHEMA") for statement in first) == 11
    assert sum(statement.startswith("CREATE TABLE") for statement in first) == 77
    assert any('CREATE TABLE "registry"."analysis_release"' in statement for statement in first)
    assert any("jsonb_typeof(" in statement for statement in first)


def test_frozen_authority_fk_graph_is_complete_and_acyclic() -> None:
    from tpaa_storage.bootstrap import _load_authority

    authority = _load_authority()
    dependencies = _table_dependencies(authority)
    order = _postgres_table_order(authority)

    assert len(authority.tables) == 77
    assert sum(len(targets) for targets in dependencies.values()) == 125
    assert len(order) == 77
    assert set(order) == set(authority.tables)
    positions = {table_name: index for index, table_name in enumerate(order)}
    for table_name, targets in dependencies.items():
        for target in targets:
            assert positions[target] < positions[table_name]


def test_postgres_order_uses_lexical_tie_breaking() -> None:
    authority = _authority(
        {
            "zeta.child": _table("id uuid PRIMARY KEY", "a_id uuid REFERENCES alpha.parent(id)"),
            "alpha.parent": _table("id uuid PRIMARY KEY"),
            "beta.free": _table("id uuid PRIMARY KEY"),
        }
    )

    assert _postgres_table_order(authority) == (
        "alpha.parent",
        "beta.free",
        "zeta.child",
    )


def test_postgres_projection_fails_closed_on_missing_reference() -> None:
    authority = _authority(
        {
            "alpha.child": _table(
                "id uuid PRIMARY KEY",
                "parent_id uuid REFERENCES alpha.missing(id)",
            )
        }
    )

    with pytest.raises(BootstrapError, match="REFERENCE_TARGET_MISSING"):
        _postgres_create_statements(authority)


def test_postgres_projection_fails_closed_on_reference_cycle() -> None:
    authority = _authority(
        {
            "alpha.a": _table("id uuid PRIMARY KEY", "b_id uuid REFERENCES alpha.b(id)"),
            "alpha.b": _table("id uuid PRIMARY KEY", "a_id uuid REFERENCES alpha.a(id)"),
        }
    )

    with pytest.raises(BootstrapError, match="REFERENCE_CYCLE"):
        _postgres_create_statements(authority)


def test_postgres_projection_preserves_native_types_and_strips_human_comments() -> None:
    authority = _authority(
        {
            "metric.sample": _table(
                "id uuid PRIMARY KEY",
                "payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='array')",
                "tags text[] NULL, -- human note",
            )
        }
    )

    statements = _postgres_create_statements(authority)
    table_statement = next(
        statement for statement in statements if statement.startswith("CREATE TABLE")
    )

    assert "payload jsonb" in table_statement
    assert "jsonb_typeof(payload)='array'" in table_statement
    assert "tags text[] NULL" in table_statement
    assert "human note" not in table_statement
