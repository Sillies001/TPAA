"""Engine-local canonical row access without business-domain imports."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol

FieldKind = Literal["scalar", "json", "text_array", "uuid_array"]

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CanonicalRowRepositoryError(RuntimeError):
    """Fail-closed error for canonical row access."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


class CanonicalRowRepository(Protocol):
    """Transaction-scoped engine-neutral row gateway for governed tables."""

    def insert(
        self,
        table: str,
        values: Mapping[str, object],
        *,
        field_kinds: Mapping[str, FieldKind] | None = None,
    ) -> None: ...

    def one(
        self,
        table: str,
        *,
        where: Mapping[str, object],
        columns: Sequence[str],
    ) -> dict[str, object] | None: ...

    def many(
        self,
        table: str,
        *,
        where: Mapping[str, object],
        columns: Sequence[str],
        order_by: Sequence[str] = (),
    ) -> tuple[dict[str, object], ...]: ...

    def update_exact(
        self,
        table: str,
        *,
        where: Mapping[str, object],
        values: Mapping[str, object],
        field_kinds: Mapping[str, FieldKind] | None = None,
    ) -> None: ...


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise CanonicalRowRepositoryError("CANONICAL_IDENTIFIER_INVALID", value)
    return value


def _split_table(value: str) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) != 2:
        raise CanonicalRowRepositoryError("CANONICAL_TABLE_INVALID", value)
    return _identifier(parts[0]), _identifier(parts[1])


def _json_text(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


class _CanonicalRowRepository:
    def __init__(self, connection: Any, *, postgres: bool) -> None:
        self._connection = connection
        self._postgres = postgres

    def _table(self, value: str) -> str:
        schema, relation = _split_table(value)
        if self._postgres:
            return f'"{schema}"."{relation}"'
        return f'"{schema}.{relation}"'

    @staticmethod
    def _column(value: str) -> str:
        return f'"{_identifier(value)}"'

    def _placeholder(self, kind: FieldKind) -> str:
        if not self._postgres:
            return "?"
        if kind == "json":
            return "%s::jsonb"
        if kind == "text_array":
            return "%s::text[]"
        if kind == "uuid_array":
            return "%s::uuid[]"
        return "%s"

    def _adapt(self, value: object, kind: FieldKind) -> object:
        if kind == "json":
            return _json_text(value)
        if kind in {"text_array", "uuid_array"}:
            if not isinstance(value, (tuple, list)):
                raise CanonicalRowRepositoryError(
                    "CANONICAL_ARRAY_VALUE_INVALID",
                    type(value).__name__,
                )
            return list(value) if self._postgres else _json_text(value)
        return value

    def _execute(self, sql: str, params: tuple[object, ...]) -> Any:
        try:
            if self._postgres:
                cursor = self._connection.cursor()
                cursor.execute(sql, params)
                return cursor
            return self._connection.execute(sql, params)
        except Exception as exc:
            raise CanonicalRowRepositoryError(
                "CANONICAL_ROW_EXECUTION_FAILED",
                str(exc),
            ) from exc

    @staticmethod
    def _row_dict(cursor: Any, row: object) -> dict[str, object]:
        if cursor.description is None:
            raise CanonicalRowRepositoryError(
                "CANONICAL_ROW_DESCRIPTION_MISSING",
                "cursor.description",
            )
        names = tuple(str(item[0]) for item in cursor.description)
        if isinstance(row, sqlite3.Row):
            return {name: row[name] for name in names}
        if not isinstance(row, (tuple, list)):
            raise CanonicalRowRepositoryError(
                "CANONICAL_ROW_SHAPE_INVALID",
                type(row).__name__,
            )
        values = tuple(row)
        if len(names) != len(values):
            raise CanonicalRowRepositoryError(
                "CANONICAL_ROW_SHAPE_INVALID",
                f"columns={len(names)} values={len(values)}",
            )
        return dict(zip(names, values, strict=True))

    def insert(
        self,
        table: str,
        values: Mapping[str, object],
        *,
        field_kinds: Mapping[str, FieldKind] | None = None,
    ) -> None:
        if not values:
            raise CanonicalRowRepositoryError(
                "CANONICAL_INSERT_EMPTY",
                table,
            )
        kinds = dict(field_kinds or {})
        columns = tuple(values)
        unknown_kinds = set(kinds) - set(columns)
        if unknown_kinds:
            raise CanonicalRowRepositoryError(
                "CANONICAL_FIELD_KIND_UNKNOWN",
                ",".join(sorted(unknown_kinds)),
            )
        placeholders: list[str] = []
        params: list[object] = []
        for column in columns:
            kind = kinds.get(column, "scalar")
            placeholders.append(self._placeholder(kind))
            params.append(self._adapt(values[column], kind))
        sql = (
            f"INSERT INTO {self._table(table)} ("
            + ", ".join(self._column(column) for column in columns)
            + ") VALUES ("
            + ", ".join(placeholders)
            + ")"
        )
        cursor = self._execute(sql, tuple(params))
        if self._postgres:
            cursor.close()

    def _select(
        self,
        table: str,
        *,
        where: Mapping[str, object],
        columns: Sequence[str],
        order_by: Sequence[str],
    ) -> tuple[Any, tuple[object, ...]]:
        if not columns:
            raise CanonicalRowRepositoryError(
                "CANONICAL_SELECT_COLUMNS_EMPTY",
                table,
            )
        selected = ", ".join(self._column(column) for column in columns)
        clauses: list[str] = []
        params: list[object] = []
        for column, value in where.items():
            clauses.append(f"{self._column(column)} = {self._placeholder('scalar')}")
            params.append(value)
        sql = f"SELECT {selected} FROM {self._table(table)}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if order_by:
            sql += " ORDER BY " + ", ".join(
                self._column(column) for column in order_by
            )
        return self._execute(sql, tuple(params)), tuple(params)

    def one(
        self,
        table: str,
        *,
        where: Mapping[str, object],
        columns: Sequence[str],
    ) -> dict[str, object] | None:
        cursor, _ = self._select(
            table,
            where=where,
            columns=columns,
            order_by=(),
        )
        try:
            rows = cursor.fetchmany(2)
            if not rows:
                return None
            if len(rows) != 1:
                raise CanonicalRowRepositoryError(
                    "CANONICAL_ROW_NOT_UNIQUE",
                    table,
                )
            return self._row_dict(cursor, rows[0])
        finally:
            if self._postgres:
                cursor.close()

    def many(
        self,
        table: str,
        *,
        where: Mapping[str, object],
        columns: Sequence[str],
        order_by: Sequence[str] = (),
    ) -> tuple[dict[str, object], ...]:
        cursor, _ = self._select(
            table,
            where=where,
            columns=columns,
            order_by=order_by,
        )
        try:
            rows = cursor.fetchall()
            return tuple(self._row_dict(cursor, row) for row in rows)
        finally:
            if self._postgres:
                cursor.close()

    def update_exact(
        self,
        table: str,
        *,
        where: Mapping[str, object],
        values: Mapping[str, object],
        field_kinds: Mapping[str, FieldKind] | None = None,
    ) -> None:
        if not where or not values:
            raise CanonicalRowRepositoryError(
                "CANONICAL_UPDATE_INVALID",
                table,
            )
        kinds = dict(field_kinds or {})
        params: list[object] = []
        assignments: list[str] = []
        for column, value in values.items():
            kind = kinds.get(column, "scalar")
            assignments.append(
                f"{self._column(column)} = {self._placeholder(kind)}"
            )
            params.append(self._adapt(value, kind))
        clauses: list[str] = []
        for column, value in where.items():
            clauses.append(f"{self._column(column)} = {self._placeholder('scalar')}")
            params.append(value)
        cursor = self._execute(
            f"UPDATE {self._table(table)} SET "
            + ", ".join(assignments)
            + " WHERE "
            + " AND ".join(clauses),
            tuple(params),
        )
        try:
            if cursor.rowcount != 1:
                raise CanonicalRowRepositoryError(
                    "CANONICAL_UPDATE_CARDINALITY",
                    f"{table}:rowcount={cursor.rowcount}",
                )
        finally:
            if self._postgres:
                cursor.close()


class SQLiteCanonicalRowRepository(_CanonicalRowRepository):
    """SQLite canonical row gateway inside an existing UoW."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection, postgres=False)


class PostgreSQLCanonicalRowRepository(_CanonicalRowRepository):
    """PostgreSQL canonical row gateway inside an existing UoW."""

    def __init__(self, connection: Any) -> None:
        super().__init__(connection, postgres=True)
