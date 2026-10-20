from __future__ import annotations

import math
from pathlib import Path

import pytest

from tpaa_application import SourceWorkflowError, SourceWorkflowService, bounded_source_bytes
from tpaa_ingest import (
    NASA_DASHLINK_MAT_MEDIA_TYPE,
    FlightRecorderCsvProfile,
    NasaDashlinkMatAdapter,
    ProductionSourceAdapterError,
    SourceFamily,
    build_production_source_registry,
    normalize_flight_recorder_csv,
)
from tpaa_runtime import materialize_source_documents
from tpaa_storage import LocalObjectStore

SESSION_ID = "d2000000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "d2000000-0000-4000-8000-000000000002"
RAW_ID = "d2000000-0000-4000-8000-000000000003"
CANONICAL_ID = "d2000000-0000-4000-8000-000000000004"
SOURCE_ID = "d2000000-0000-4000-8000-000000000005"
STREAM_ID = "d2000000-0000-4000-8000-000000000006"


def _csv() -> bytes:
    return (
        b"source_time_us,session_time_us,p_deg_s,nz_g,heading_deg_true,"
        b"tas_kt,mach,quality_mask\n"
        b"0,0,0,1.0,0,200,0.60,0\n"
        b"100000,100000,5,1.1,10,201,0.61,0\n"
        b"0,200000,10,1.2,20,202,0.62,1\n"
        b"100000,300000,,1.3,30,203,0.63,1\n"
    )


def _profile() -> FlightRecorderCsvProfile:
    return FlightRecorderCsvProfile(session_id=SESSION_ID, aircraft_id=AIRCRAFT_ID)


def test_csv_normalization_preserves_physical_order_reset_lineage_and_units() -> None:
    normalized = normalize_flight_recorder_csv(_csv(), profile=_profile())
    assert normalized.inspection.row_count == 4
    assert normalized.inspection.clock_segment_count == 2
    assert normalized.inspection.missing_value_counts["p"] == 1
    rows = normalized.production_document["rows"]
    assert isinstance(rows, list)
    assert [row["source_row_ordinal"] for row in rows] == [0, 1, 2, 3]
    assert [row["source_clock_segment"] for row in rows] == [0, 0, 1, 1]
    assert rows[1]["p"] == pytest.approx(math.radians(5.0))
    assert rows[1]["heading"] == pytest.approx(math.radians(10.0))
    assert rows[1]["tas"] == pytest.approx(201.0 * 0.514444)
    source_profile = normalized.production_document["source_profile"]
    assert isinstance(source_profile, dict)
    manifest = source_profile["mapping_manifest"]
    assert isinstance(manifest, dict)
    assert manifest["physical_order_preserved"] is True
    assert manifest["source_clock_segment_starts"] == [0, 2]


def test_csv_fails_closed_for_bad_time_and_unknown_schema() -> None:
    bad_time = _csv().replace(b"0,200000,10", b"0,100000,10")
    with pytest.raises(ProductionSourceAdapterError) as exc_info:
        normalize_flight_recorder_csv(bad_time, profile=_profile())
    assert exc_info.value.code == "W2_FLIGHT_CSV_SESSION_TIME_INVALID"

    bad_header = _csv().replace(b"tas_kt", b"tas_mps", 1)
    with pytest.raises(ProductionSourceAdapterError) as exc_info:
        normalize_flight_recorder_csv(bad_header, profile=_profile())
    assert exc_info.value.code == "W2_FLIGHT_CSV_SCHEMA_UNSUPPORTED"


def test_workflow_stages_raw_and_canonical_artifacts_for_existing_p1_path(
    tmp_path: Path,
) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    service = SourceWorkflowService(store)
    result = service.stage_flight_csv(
        _csv(),
        session_id=SESSION_ID,
        aircraft_id=AIRCRAFT_ID,
        source_ref="file:///operator/import/flight.csv",
        raw_artifact_id=RAW_ID,
        canonical_artifact_id=CANONICAL_ID,
        source_id=SOURCE_ID,
        source_stream_id=STREAM_ID,
        producer_system="ANON_FLIGHT_RECORDER_EXPORT",
        session_code="W2-ANON-001",
        session_type="LIVE",
        classification_label="UNCLASSIFIED",
        nominal_rate_hz=10.0,
    )
    assert result["status"] == "STAGED"
    raw = result["raw_artifact"]
    assert isinstance(raw, dict)
    assert store.read_bytes(str(raw["logical_uri"])) == _csv()
    source_document = result["source_document"]
    assert isinstance(source_document, dict)
    materialized = materialize_source_documents(store, source_document)
    assert isinstance(materialized["source_json"], str)
    metadata = materialized["source_import"]
    assert isinstance(metadata, dict)
    assert metadata["session_type"] == "LIVE"
    assert metadata["ingress_adapter_id"] == "tpaa-flight-recorder-csv"

    adapters = service.adapter_registry()["items"]
    assert isinstance(adapters, list)
    flight = [item for item in adapters if item["source_family"] == "FLIGHT"]
    assert {item["adapter_id"] for item in flight} == {
        "nasa-dashlink-mat-v5",
        "tpaa-flight-recorder-csv",
        "tpaa-production-flight-json",
    }
    assert len(build_production_source_registry().for_family(SourceFamily.FLIGHT)) == 3


def test_bounded_chunks_apply_limit_and_cancellation() -> None:
    assert bounded_source_bytes([b"a", b"b"]) == b"ab"
    with pytest.raises(SourceWorkflowError) as exc_info:
        bounded_source_bytes([b"ab", b"cd"], max_bytes=3)
    assert exc_info.value.code == "SOURCE_ARTIFACT_SIZE_INVALID"
    with pytest.raises(SourceWorkflowError) as exc_info:
        bounded_source_bytes([b"ab"], cancelled=lambda: True)
    assert exc_info.value.code == "W2_SOURCE_IMPORT_CANCELLED"


def test_nasa_mat_adapter_inspects_matlab_v5_bytes_without_runtime_decoder() -> None:
    data = b"MATLAB 5.0 MAT-file, Platform: PCWIN64" + (b"\x00" * 96)
    adapter = NasaDashlinkMatAdapter()
    envelope = adapter.inspect(
        source_ref="https://c3.ndc.nasa.gov/dashlink/resources/664/",
        data=data,
        media_type=NASA_DASHLINK_MAT_MEDIA_TYPE,
        classification_label="PUBLIC_DEIDENTIFIED",
    )
    assert envelope.adapter_id == "nasa-dashlink-mat-v5"
    assert envelope.size_bytes == len(data)
    assert envelope.classification_label == "PUBLIC_DEIDENTIFIED"

    with pytest.raises(ProductionSourceAdapterError) as exc_info:
        adapter.inspect(
            source_ref="local://invalid.mat",
            data=b"not-a-mat-file",
            media_type=NASA_DASHLINK_MAT_MEDIA_TYPE,
        )
    assert exc_info.value.code == "W2_NASA_DASHLINK_MAT_UNSUPPORTED"
