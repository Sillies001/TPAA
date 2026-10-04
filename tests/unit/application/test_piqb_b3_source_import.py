from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_application import (
    ProductionImportError,
    ProductionImportService,
    SourceImportCommand,
    SourceProvenanceRepository,
)
from tpaa_ingest import (
    SourceAdapterDescriptor,
    SourceAdapterRegistry,
    SourceArtifactEnvelope,
    SourceFamily,
)
from tpaa_storage import SQLiteCanonicalRowRepository, bootstrap_sqlite

SESSION_ID = "11111111-1111-4111-8111-111111111111"
SOURCE_ID = "22222222-2222-4222-8222-222222222222"
STREAM_ID = "33333333-3333-4333-8333-333333333333"
ARTIFACT_ID = "44444444-4444-4444-8444-444444444444"


def _seed_session(connection: sqlite3.Connection) -> None:
    rows = SQLiteCanonicalRowRepository(connection)
    rows.insert(
        "registry.training_session",
        {
            "session_id": SESSION_ID,
            "session_code": "B3-SESSION",
            "session_type": "SIM",
            "start_session_time_us": 0,
            "end_session_time_us": 1,
            "training_type_set": (),
            "data_status": "IMPORTING",
            "source_count": 0,
            "schema_version": "1.9.0",
        },
        field_kinds={"training_type_set": "text_array"},
    )


def _registry() -> SourceAdapterRegistry:
    return SourceAdapterRegistry(
        (
            SourceAdapterDescriptor(
                adapter_id="flight-adapter",
                adapter_version="1.0.0",
                source_family=SourceFamily.FLIGHT,
                media_types=("application/x-tpaa-flight",),
                external_decoder=True,
            ),
        )
    )


def _command() -> SourceImportCommand:
    return SourceImportCommand(
        source_id=SOURCE_ID,
        session_id=SESSION_ID,
        platform_id=None,
        producer_system="B3_TEST_SOURCE",
        schema_name="TPAA_TEST_FLIGHT",
        schema_version="1.0.0",
        time_basis="SOURCE_US",
        nominal_rate_hz=20.0,
        source_quality=1.0,
        source_stream_id=STREAM_ID,
        stream_code="FLIGHT_PRIMARY",
        ordinal_basis="CAPTURE_MANIFEST",
        stream_status="ACTIVE",
        artifact_id=ARTIFACT_ID,
        source_artifact_sequence=0,
        uri_kind="EXTERNAL_OBJECT",
        availability_status="AVAILABLE",
        last_verified_at="2026-10-04T00:00:00Z",
        mtime_source=None,
        envelope=SourceArtifactEnvelope(
            source_family=SourceFamily.FLIGHT,
            adapter_id="flight-adapter",
            adapter_version="1.0.0",
            source_ref="source://fixture/flight.bin",
            artifact_sha256="a" * 64,
            size_bytes=256,
            media_type="application/x-tpaa-flight",
            classification_label="TEST",
        ),
    )


def test_import_boundary_persists_exact_db_1_9_provenance_across_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "b3-source.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    _seed_session(connection)
    repository = SourceProvenanceRepository(SQLiteCanonicalRowRepository(connection))
    service = ProductionImportService(adapters=_registry(), provenance=repository)

    expected = service.register(_command())
    service.register(_command())
    connection.commit()
    connection.close()

    restarted_connection = sqlite3.connect(database)
    restarted = SourceProvenanceRepository(
        SQLiteCanonicalRowRepository(restarted_connection)
    )
    assert restarted.exact(ARTIFACT_ID) == expected
    restarted_connection.close()


def test_source_artifact_identity_is_immutable(tmp_path: Path) -> None:
    database = tmp_path / "b3-conflict.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    _seed_session(connection)
    repository = SourceProvenanceRepository(SQLiteCanonicalRowRepository(connection))
    service = ProductionImportService(adapters=_registry(), provenance=repository)
    record = service.register(_command())

    with pytest.raises(
        ProductionImportError,
        match="B3_SOURCE_ARTIFACT_IMMUTABLE_CONFLICT",
    ):
        repository.register(replace(record, sha256="b" * 64))

    connection.close()
