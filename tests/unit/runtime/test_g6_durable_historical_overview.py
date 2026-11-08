"""G6 durable historical-overview adapter tests against a real SQLite canonical store."""

from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_application.historical_overview import HistoricalOverviewError
from tpaa_runtime.durable_historical_overview import DurableHistoricalOverviewAdapter, _properties
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.11.0" / "canonical"

SESSION_ID = "e6100000-0000-4000-8000-000000000001"
BATCH_ADJUDICATED = "e6100000-0000-4000-8000-0000000000b1"
BATCH_PENDING = "e6100000-0000-4000-8000-0000000000b2"


def _seed(database: Path) -> None:
    bootstrap_sqlite(database, authority_root=AUTHORITY)
    with SQLiteDesktopUnitOfWork(database, write=True, authority_root=AUTHORITY) as uow:
        uow.canonical_rows.insert(
            "registry.training_session",
            {
                "session_id": SESSION_ID,
                "session_code": "G6-DURABLE-001",
                "session_type": "LIVE",
                "start_session_time_us": 0,
                "end_session_time_us": 10_000_000,
                "training_type_set": (),
                "data_status": "IMPORTED",
                "source_count": 1,
                "schema_version": "1.10.0",
            },
            field_kinds={"training_type_set": "text_array"},
        )
        uow.canonical_rows.insert(
            "registry.compute_job",
            {
                "job_id": "e6100000-0000-4000-8000-0000000000j1",
                "job_type": "EPISODE_DETECTION",
                "session_id": SESSION_ID,
                "job_key": "g6-durable-test-job",
                "status": "SUCCEEDED",
                "component_version": "G6-DURABLE-TEST-1.0.0",
                "input_hash": "b" * 64,
            },
        )
        uow.canonical_rows.insert(
            "registry.analysis_release",
            {
                "release_id": "e6100000-0000-4000-8000-0000000000r1",
                "scope_type": "SESSION",
                "scope_key": SESSION_ID,
                "session_id": SESSION_ID,
                "release_no": 1,
                "compute_job_id": "e6100000-0000-4000-8000-0000000000j1",
                "catalog_version": "G6-DURABLE-TEST",
                "catalog_hash": "c" * 64,
                "context_binding_hash": "d" * 64,
                "status": "PUBLISHED",
                "manifest_hash": "e" * 64,
                "created_at": "2026-10-20T00:00:00+00:00",
            },
        )
        uow.canonical_rows.insert(
            "episode.training_episode",
            {
                "episode_id": "e6100000-0000-4000-8000-0000000000p1",
                "session_id": SESSION_ID,
                "episode_type": "BASIC_FLIGHT",
                "start_session_time_us": 0,
                "end_session_time_us": 10_000_000,
                "subject_scope": "SESSION",
                "world_capability_code": "BASIC_FLIGHT",
                "episode_status": "DETECTED",
                "detector_version": "G6-DURABLE-TEST-1.0.0",
                "coverage": 1.0,
                "confidence": 0.9,
            },
        )
        for batch_id, training_type in (
            (BATCH_ADJUDICATED, "COMPREHENSIVE_OPPOSITION"),
            (BATCH_PENDING, "SIMPLE_OPPOSITION"),
        ):
            uow.canonical_rows.insert(
                "registry.batch_registration",
                {
                    "batch_id": batch_id,
                    "session_id": SESSION_ID,
                    "batch_date": "2026-10-20",
                    "batch_training_type": training_type,
                    "training_type_confirmed": True,
                    "qualification_status": "QUALIFIED",
                    "source_manifest_sha256": "a" * 64,
                    "revision_no": 1,
                    "created_by": "g6-durable-test",
                },
            )
        rows = (
            ("e6100000-0000-4000-8000-0000000000e1", BATCH_ADJUDICATED, "ADJUDICATED"),
            ("e6100000-0000-4000-8000-0000000000e2", BATCH_ADJUDICATED, "ADJUDICATED"),
            ("e6100000-0000-4000-8000-0000000000e3", BATCH_PENDING, "ADJUDICATION_PENDING"),
        )
        for relation_id, batch_id, adjudication_state in rows:
            uow.canonical_rows.insert(
                "world.world_relation",
                {
                    "relation_id": relation_id,
                    "release_id": "e6100000-0000-4000-8000-0000000000r1",
                    "episode_id": "e6100000-0000-4000-8000-0000000000p1",
                    "relation_type": "WEAPON_EVENT",
                    "subject_ref": "e6100000-0000-4000-8000-0000000000s1",
                    "object_ref": "e6100000-0000-4000-8000-0000000000t1",
                    "start_session_time_us": 1_000_000,
                    "properties": {"batch_id": batch_id, "adjudication_state": adjudication_state},
                    "confidence": 0.9,
                    "relation_source": "DERIVED",
                    "method_version": "G6-DURABLE-TEST-1.0.0",
                },
                field_kinds={"properties": "json"},
            )
        uow.commit()


def _factory(database: Path):
    return lambda: SQLiteDesktopUnitOfWork(database, authority_root=AUTHORITY)


def test_adapter_counts_weapon_events_from_jsonb_text_properties(tmp_path: Path) -> None:
    database = tmp_path / "g6-durable.sqlite3"
    _seed(database)
    adapter = DurableHistoricalOverviewAdapter(_factory(database))
    batches = {record.batch_id: record for record in adapter.qualified_batches()}
    assert set(batches) == {BATCH_ADJUDICATED, BATCH_PENDING}
    assert batches[BATCH_ADJUDICATED].weapon_event_count == 2
    assert batches[BATCH_ADJUDICATED].adjudicated_event_count == 2
    assert batches[BATCH_ADJUDICATED].has_event_detail is True
    assert batches[BATCH_PENDING].weapon_event_count == 1
    assert batches[BATCH_PENDING].adjudicated_event_count == 0
    # Metric Authority 尚未准入：诚实空集。
    assert adapter.task_metric_inputs(tuple(batches)) == ()
    assert adapter.equipment_metric_inputs(tuple(batches)) == ()


@pytest.mark.parametrize("value", ["{broken", [], 17, None])
def test_malformed_weapon_event_properties_are_degraded_not_silent_empty(value: object) -> None:
    with pytest.raises(HistoricalOverviewError, match="CANONICAL_WE_PROPERTIES_INVALID"):
        _properties(value)
