from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tpaa_application import IdempotencyConflict, JobStatus
from tpaa_ingest import (
    FROZEN_SOURCE_FAMILIES,
    PRODUCTION_FLIGHT_MEDIA_TYPE,
    ProductionFlightJsonAdapter,
    SourceFamily,
    build_production_source_registry,
)
from tpaa_observation import allocate_session_release_id
from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import bootstrap_sqlite
from tpaa_storage.hashing import canonical_request_hash

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
SOURCE = (
    ROOT
    / "docs"
    / "baseline"
    / "PRCB-1.0"
    / "qualification"
    / "PRCB_C2_NOMINAL_FLIGHT.json"
)
SESSION_ID = "c2000000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "c2000000-0000-4000-8000-000000000002"
CONTEXT_ID = "c2000000-0000-4000-8000-000000000003"
SOURCE_ID = "c2000000-0000-4000-8000-000000000004"
STREAM_ID = "c2000000-0000-4000-8000-000000000005"
ARTIFACT_ID = "c2000000-0000-4000-8000-000000000006"
MODEL_ID = "c2000000-0000-4000-8000-000000000007"
INSTANCE_ID = "c2000000-0000-4000-8000-000000000008"
ENTITY_ID = "c2000000-0000-4000-8000-000000000009"


def _payload() -> dict[str, object]:
    source_json = SOURCE.read_text(encoding="utf-8")
    return {
        "source_json": source_json,
        "source_import": {
            "source_family": "FLIGHT",
            "source_id": SOURCE_ID,
            "session_id": SESSION_ID,
            "platform_id": None,
            "producer_system": "PRCB_C2_QUALIFICATION",
            "schema_name": "TPAA_PRODUCTION_FLIGHT_SOURCE_V1",
            "schema_version": "1.0.0",
            "time_basis": "SOURCE_US",
            "nominal_rate_hz": "10.0",
            "source_quality": "1.0",
            "source_stream_id": STREAM_ID,
            "stream_code": "FLIGHT_PRIMARY",
            "ordinal_basis": "SOURCE_SEQUENCE",
            "stream_status": "ACTIVE",
            "artifact_id": ARTIFACT_ID,
            "source_artifact_sequence": 0,
            "uri_kind": "EXTERNAL_FILE",
            "availability_status": "AVAILABLE",
            "last_verified_at": "2026-10-05T00:00:00Z",
            "mtime_source": None,
            "source_ref": "qualification://PRCB_C2_NOMINAL_FLIGHT",
            "media_type": PRODUCTION_FLIGHT_MEDIA_TYPE,
            "classification_label": "UNCLASSIFIED",
            "session_code": "PRCB-C2-NOMINAL",
            "session_type": "SIM",
        },
        "evaluation_context": {
            "context_id": CONTEXT_ID,
            "session_id": SESSION_ID,
            "context_version": "PRCB-C2-CONTEXT-1.0.0",
            "revision_no": 1,
            "rule_set_version": "PRCB-C2-RULES-1.0.0",
            "metric_profile_version": "PRCB_C2_P1_PROFILE_V1",
            "status": "ACTIVE",
        },
        "metric_profile": {
            "profile_id": "PRCB_C2_P1_PROFILE_V1",
            "min_coverage": "0.8",
            "max_gap_us": 200000,
            "derivative_window_s": "0.3",
            "sustain_duration_s": "0.5",
        },
        "publication_identity": {
            "aircraft_model_id": MODEL_ID,
            "aircraft_instance_id": INSTANCE_ID,
            "subject_entity_id": ENTITY_ID,
            "capability_dimension": "AIRCRAFT_FLIGHT",
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "aircraft_type_code": "PRCB-C2-TYPE",
            "aircraft_model_name": "PRCB C2 Qualification Aircraft",
            "aircraft_internal_code": "PRCB-C2-AIRCRAFT",
            "entity_alias": "PRCB-C2-SUBJECT",
        },
        "expected_version_token": 0,
        "parent_release_id": None,
    }


def test_prcb_c2_production_adapter_is_explicit_and_no_fallback() -> None:
    source_bytes = SOURCE.read_bytes()
    adapter = ProductionFlightJsonAdapter()
    envelope = adapter.inspect(
        source_ref="qualification://PRCB_C2_NOMINAL_FLIGHT",
        data=source_bytes,
        media_type=PRODUCTION_FLIGHT_MEDIA_TYPE,
        classification_label="UNCLASSIFIED",
    )
    assert envelope.source_family is SourceFamily.FLIGHT
    assert envelope.size_bytes == len(source_bytes)
    assert len(envelope.artifact_sha256) == 64

    registry = build_production_source_registry()
    inventory = registry.inventory()
    assert {item.source_family for item in inventory} == FROZEN_SOURCE_FAMILIES
    assert registry.require_family(SourceFamily.FLIGHT) == (adapter.descriptor,)
    for family in FROZEN_SOURCE_FAMILIES - {SourceFamily.FLIGHT}:
        descriptors = registry.require_family(family)
        assert len(descriptors) == 1
        assert descriptors[0].source_family is family
        assert descriptors[0].external_decoder is True


def test_prcb_c2_desktop_job_runs_worker_pipeline_and_survives_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    object_root = tmp_path / "objects"
    bootstrap_sqlite(database)

    config = ProductionRuntimeConfig(
        profile=RuntimeProfile.DESKTOP,
        product_build_version="1.0.1",
        authority_root=AUTHORITY,
        object_root=object_root,
        desktop_database_path=database,
    )
    runtime = build_desktop_production_runtime(config)
    payload = _payload()
    submission = runtime.application.submit_job(
        idempotency_key="prcb-c2-production-p1",
        command="BUILD_P1_RELEASE",
        payload=payload,
        actor="PRCB-C2-TEST",
    )
    assert submission.reused is False
    assert submission.record.status is JobStatus.SUCCEEDED

    request_hash = canonical_request_hash(
        {"job_type": "BUILD_P1_RELEASE", "payload": payload}
    )
    release_id = allocate_session_release_id(
        session_id=SESSION_ID,
        request_hash=request_hash,
    )
    release = runtime.application.m1_release(release_id)
    assert release["release_id"] == release_id
    assert release["metric_count"] == 5
    assert release["production_compute_configured"] is True
    metrics = runtime.application.m1_metrics(release_id)
    assert len(metrics) == 5
    evidence = runtime.application.m1_metric_evidence(
        release_id,
        str(metrics[0]["metric_code"]),
    )
    locator = evidence["series_locator"]
    assert isinstance(locator, dict)
    assert str(locator["canonical_dataset_uri"]).startswith(
        "tpaa-parquet://production/canonical-flight/"
    )
    assert len(str(locator["canonical_logical_content_hash"])) == 64

    restarted = build_desktop_production_runtime(config)
    assert (
        restarted.application.job(submission.record.job_id).status
        is JobStatus.SUCCEEDED
    )
    assert restarted.application.m1_release(release_id) == release

    reused = restarted.application.submit_job(
        idempotency_key="prcb-c2-production-p1",
        command="BUILD_P1_RELEASE",
        payload=payload,
        actor="PRCB-C2-TEST",
    )
    assert reused.reused is True
    assert reused.record.status is JobStatus.SUCCEEDED

    changed = copy.deepcopy(payload)
    profile = changed["metric_profile"]
    assert isinstance(profile, dict)
    profile["min_coverage"] = "0.75"
    with pytest.raises(IdempotencyConflict):
        restarted.application.submit_job(
            idempotency_key="prcb-c2-production-p1",
            command="BUILD_P1_RELEASE",
            payload=changed,
            actor="PRCB-C2-TEST",
        )


def test_prcb_c2_unsupported_domain_command_is_durable_failure(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=AUTHORITY,
            object_root=tmp_path / "objects",
            desktop_database_path=database,
        )
    )
    submission = runtime.application.submit_job(
        idempotency_key="prcb-c2-unsupported",
        command="UNKNOWN_DOMAIN_COMMAND",
        payload={},
        actor="PRCB-C2-TEST",
    )
    assert submission.record.status is JobStatus.FAILED
    restarted = build_desktop_production_runtime(runtime.config)
    assert (
        restarted.application.job(submission.record.job_id).status
        is JobStatus.FAILED
    )
