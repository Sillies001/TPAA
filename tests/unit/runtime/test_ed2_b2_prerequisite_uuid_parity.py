"""SQLite/PostgreSQL UUID decoding parity in immutable P1 prerequisites."""

from __future__ import annotations

from unittest.mock import Mock
from uuid import UUID

import pytest

from tpaa_runtime import durable_jobs
from tpaa_runtime.production_worker import ProductionPrerequisiteRow

_DEFINITION_ID = "c93bf5d6-29f1-41fb-bb9d-7d7640b3d441"


def _definition_prerequisite() -> ProductionPrerequisiteRow:
    return ProductionPrerequisiteRow(
        table="metric.metric_definition",
        values={
            "metric_definition_id": _DEFINITION_ID,
            "metric_code": "P1-TEST-001",
            "definition_hash": "expected-definition-hash",
        },
        field_kinds={},
    )


def test_ed2_b2_postgres_uuid_object_matches_exact_string_identity() -> None:
    uow = Mock()
    uow.canonical_rows.one.return_value = {
        "metric_definition_id": UUID(_DEFINITION_ID),
        "metric_code": "P1-TEST-001",
        "definition_hash": "expected-definition-hash",
    }
    durable_jobs._persist_or_verify_prerequisite(uow, _definition_prerequisite())
    uow.canonical_rows.insert.assert_not_called()
    assert durable_jobs._logical_prerequisite_value(
        UUID(_DEFINITION_ID), field_kind="scalar"
    ) == _DEFINITION_ID


def test_ed2_b2_sqlite_string_identity_is_unchanged() -> None:
    uow = Mock()
    uow.canonical_rows.one.return_value = dict(
        _definition_prerequisite().values
    )
    durable_jobs._persist_or_verify_prerequisite(uow, _definition_prerequisite())
    uow.canonical_rows.insert.assert_not_called()


def test_ed2_b2_real_definition_hash_drift_still_fails_closed() -> None:
    uow = Mock()
    uow.canonical_rows.one.return_value = {
        "metric_definition_id": UUID(_DEFINITION_ID),
        "metric_code": "P1-TEST-001",
        "definition_hash": "different-definition-hash",
    }
    with pytest.raises(
        durable_jobs.ProductionJobExecutionError,
        match="ED2_P1_PREREQUISITE_IDENTITY_DRIFT.*fields=definition_hash",
    ):
        durable_jobs._persist_or_verify_prerequisite(uow, _definition_prerequisite())
    uow.canonical_rows.insert.assert_not_called()


def test_ed2_b2_distinct_postgres_uuid_still_fails_closed() -> None:
    uow = Mock()
    uow.canonical_rows.one.return_value = {
        **_definition_prerequisite().values,
        "metric_definition_id": UUID("7e9e2459-6714-48a5-bb96-18673e5fd223"),
    }
    with pytest.raises(
        durable_jobs.ProductionJobExecutionError,
        match="ED2_P1_PREREQUISITE_IDENTITY_DRIFT.*fields=metric_definition_id",
    ):
        durable_jobs._persist_or_verify_prerequisite(uow, _definition_prerequisite())
