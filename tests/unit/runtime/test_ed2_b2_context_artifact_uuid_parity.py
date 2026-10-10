"""Exact reuse of sealed P2 context artifacts across SQLite and PostgreSQL."""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest

from tpaa_runtime.production_downstream import (
    ProductionDownstreamError,
    _context_artifact_bytes,
    _stored_field_matches,
)


def test_ed2_b2_postgres_context_artifact_uuid_is_exactly_reusable() -> None:
    payload = b'{"schema":"P2","version":"1.0.0"}'
    stored: dict[str, dict[str, object]] = {}
    rows = Mock()
    object_store = Mock()
    object_store.put_bytes.return_value.artifact_sha256 = hashlib.sha256(
        payload
    ).hexdigest()

    def insert(table: str, values: dict[str, object], **_kwargs: Any) -> None:
        stored[table] = dict(values)

    def one(
        table: str,
        *,
        where: dict[str, object],
        columns: tuple[str, ...],
    ) -> dict[str, object] | None:
        item = stored.get(table)
        if item is None or any(
            str(item[key]) != str(value) for key, value in where.items()
        ):
            return None
        selected = {key: item[key] for key in columns}
        if table == "registry.context_artifact":
            selected["object_ref_id"] = UUID(str(selected["object_ref_id"]))
        return selected

    rows.insert.side_effect = insert
    rows.one.side_effect = one
    def create():
        return _context_artifact_bytes(
            rows,
            object_store,
            artifact_kind="P2_FEATURE_SPEC",
            logical_key="P2_FEATURE_SPEC:ED2_B2_QUALIFICATION",
            artifact_version="1.0.0",
            schema_version="TPAA_P2_FEATURE_SPEC_V1",
            data=payload,
        )

    first = create()
    again = create()
    assert first == again
    assert rows.insert.call_count == 2


def test_ed2_b2_uuid_comparison_rejects_real_identity_changes() -> None:
    identity = UUID("c93bf5d6-29f1-41fb-bb9d-7d7640b3d441")
    assert _stored_field_matches(identity, str(identity))
    assert not _stored_field_matches(
        identity, "7e9e2459-6714-48a5-bb96-18673e5fd223"
    )
    assert not _stored_field_matches("different", "expected")
    assert _stored_field_matches("same", "same")


def test_ed2_b2_context_artifact_real_conflict_is_still_rejected() -> None:
    payload = b'{"schema":"P2","version":"1.0.0"}'
    rows = Mock()
    object_store = Mock()
    object_store.put_bytes.return_value.artifact_sha256 = hashlib.sha256(
        payload
    ).hexdigest()
    # A real immutable-content conflict must remain an error.
    rows.one.side_effect = [None, {
        "artifact_kind": "P2_FEATURE_SPEC",
        "logical_key": "wrong-logical-key",
        "artifact_version": "1.0.0",
        "object_ref_id": UUID("c93bf5d6-29f1-41fb-bb9d-7d7640b3d441"),
        "artifact_sha256": hashlib.sha256(payload).hexdigest(),
        "schema_version": "TPAA_P2_FEATURE_SPEC_V1",
        "status": "ACTIVE",
    }]
    with pytest.raises(
        ProductionDownstreamError,
        match="ED2_B2_CONTEXT_ARTIFACT_IMMUTABLE_CONFLICT",
    ):
        _context_artifact_bytes(
            rows,
            object_store,
            artifact_kind="P2_FEATURE_SPEC",
            logical_key="P2_FEATURE_SPEC:ED2_B2_QUALIFICATION",
            artifact_version="1.0.0",
            schema_version="TPAA_P2_FEATURE_SPEC_V1",
            data=payload,
        )
