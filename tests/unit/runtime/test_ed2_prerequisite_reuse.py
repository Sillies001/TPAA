from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_runtime.durable_jobs import (
    ProductionJobExecutionError,
    _persist_or_verify_prerequisite,
)
from tpaa_runtime.production_worker import ProductionPrerequisiteRow
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

SESSION_ID = "e2b10000-0000-4000-8000-000000000001"


def _session(*, source_count: int = 2) -> ProductionPrerequisiteRow:
    return ProductionPrerequisiteRow(
        table="registry.training_session",
        values={
            "session_id": SESSION_ID,
            "session_code": "ED2-B1-REUSE",
            "session_type": "SIM",
            "start_session_time_us": 0,
            "end_session_time_us": 1_000_000,
            "training_type_set": ["BVR", "WVR"],
            "data_status": "READY",
            "source_count": source_count,
            "schema_version": "1.9.0",
        },
        field_kinds={"training_type_set": "text_array"},
    )


def test_prerequisite_reuse_exactly_verifies_existing_engine_neutral_row(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        _persist_or_verify_prerequisite(uow, _session())
        uow.commit()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        _persist_or_verify_prerequisite(uow, _session())
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        row = uow.canonical_rows.one(
            "registry.training_session",
            where={"session_id": SESSION_ID},
            columns=(
                "session_id",
                "session_code",
                "training_type_set",
                "source_count",
            ),
        )
        uow.commit()

    assert row is not None
    assert row["session_id"] == SESSION_ID
    assert row["session_code"] == "ED2-B1-REUSE"
    assert row["source_count"] == 2


def test_prerequisite_reuse_fails_closed_on_identity_drift(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        _persist_or_verify_prerequisite(uow, _session())
        uow.commit()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        with pytest.raises(
            ProductionJobExecutionError,
            match="ED2_P1_PREREQUISITE_IDENTITY_DRIFT",
        ):
            _persist_or_verify_prerequisite(
                uow,
                _session(source_count=3),
            )
