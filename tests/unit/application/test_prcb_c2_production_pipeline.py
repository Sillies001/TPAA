from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tools.testing.ed2_p1_full_input_builder import (
    build_full_p1_request_contract,
)
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
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite
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
    payload: dict[str, object] = {
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
    payload.update(
        build_full_p1_request_contract(
            aircraft_id=AIRCRAFT_ID,
            authority_root=AUTHORITY,
        )
    )
    return payload


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
    assert release["catalog_definition_count"] == 116
    assert release["metric_code_count"] == 116
    assert release["metric_instance_count"] >= 116
    assert release["capability_observation_count"] > 0
    assert release["system_observation_count"] > 0
    assert release["evidence_only_metric_instance_count"] > 0
    assert release["world_product_count"] == 4
    assert release["production_compute_configured"] is True
    metrics = runtime.application.m1_metrics(release_id)
    assert len(metrics) == release["metric_instance_count"]
    evidence = runtime.application.m1_metric_evidence(
        release_id,
        "P1-AIR-001",
    )
    locator = evidence["series_locator"]
    assert isinstance(locator, dict)
    assert str(locator["canonical_dataset_uri"]).startswith(
        "tpaa-parquet://production/canonical-flight/"
    )
    assert len(str(locator["canonical_logical_content_hash"])) == 64
    canonical_dataset_id = str(locator["canonical_dataset_id"])
    source_lineage = locator["source_lineage"]
    assert isinstance(source_lineage, list)
    assert source_lineage
    assert all(
        isinstance(item, dict)
        and len(str(item.get("artifact_sha256"))) == 64
        for item in source_lineage
    )
    assert len(str(locator["source_lineage_hash"])) == 64
    source_sufficiency = locator["source_sufficiency"]
    assert isinstance(source_sufficiency, dict)
    assert source_sufficiency["status"] == "READY"

    with SQLiteDesktopUnitOfWork(database) as uow:
        episode_rows = uow.canonical_rows.many(
            "episode.training_episode",
            where={
                "session_id": SESSION_ID,
                "context_id": CONTEXT_ID,
            },
            columns=("episode_id", "episode_type", "data_sufficiency_status"),
            order_by=("episode_id",),
        )
        assert len(episode_rows) == 1
        episode_id = str(episode_rows[0]["episode_id"])
        assert episode_rows[0]["episode_type"] == "BASIC_FLIGHT"
        assert episode_rows[0]["data_sufficiency_status"] == "SUFFICIENT"
        stage_rows = uow.canonical_rows.many(
            "episode.episode_stage",
            where={"episode_id": episode_id},
            columns=(
                "stage_id",
                "stage_type",
                "stage_order",
                "start_session_time_us",
                "end_session_time_us",
                "stage_status",
                "detector_version",
            ),
            order_by=("stage_order",),
        )
        world_rows = uow.canonical_rows.many(
            "world.world_product_manifest",
            where={"release_id": release_id},
            columns=(
                "world_product_id",
                "world_kind",
                "episode_id",
                "status",
                "coverage",
                "logical_content_hash",
                "dataset_id",
            ),
            order_by=("world_kind",),
        )
        dataset_manifest_rows = uow.canonical_rows.many(
            "registry.dataset_manifest",
            where={"dataset_id": canonical_dataset_id},
            columns=(
                "dataset_id",
                "release_id",
                "scope_type",
                "session_id",
                "dataset_kind",
                "logical_name",
                "object_ref_id",
                "storage_uri",
                "schema_version",
                "row_count",
                "min_session_time_us",
                "max_session_time_us",
                "artifact_sha256",
                "logical_content_hash",
                "producer_component",
                "producer_version",
                "input_hash",
                "status",
                "supersedes_dataset_id",
            ),
            order_by=("dataset_id",),
        )
        assert len(dataset_manifest_rows) == 1
        dataset_manifest = dataset_manifest_rows[0]
        object_reference_rows = uow.canonical_rows.many(
            "registry.object_reference",
            where={"object_ref_id": dataset_manifest["object_ref_id"]},
            columns=(
                "object_ref_id",
                "managed_uri",
                "media_type",
                "size_bytes",
                "artifact_sha256",
                "logical_content_hash",
                "storage_backend",
                "sealed",
                "gc_state",
                "gc_state_version",
            ),
            order_by=("object_ref_id",),
        )
        assert len(object_reference_rows) == 1
        object_reference = object_reference_rows[0]
        relation_rows = uow.canonical_rows.many(
            "world.world_relation",
            where={"release_id": release_id},
            columns=(
                "relation_id",
                "episode_id",
                "stage_id",
                "relation_type",
                "subject_ref",
                "object_ref",
                "relation_source",
                "method_version",
                "start_session_time_us",
                "end_session_time_us",
            ),
            order_by=("start_session_time_us", "relation_id"),
        )
        uow.commit()

    assert [row["stage_type"] for row in stage_rows] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]
    assert [row["stage_order"] for row in stage_rows] == [0, 1, 2, 3]
    assert all(row["stage_status"] == "VALID" for row in stage_rows)
    assert all(
        row["detector_version"] == "ED2_B1_BASIC_FLIGHT_STAGE_PROJECTOR_V1"
        for row in stage_rows
    )
    assert [row["world_kind"] for row in world_rows] == [
        "ACTION",
        "CONTEXT",
        "MACHINE",
        "TRUTH",
    ]
    assert all(str(row["episode_id"]) == episode_id for row in world_rows)
    assert all(row["status"] == "READY" for row in world_rows)
    assert len(world_rows) == 4
    truth_world = next(
        row for row in world_rows if row["world_kind"] == "TRUTH"
    )
    assert str(truth_world["dataset_id"]) == canonical_dataset_id

    assert str(dataset_manifest["dataset_id"]) == canonical_dataset_id
    assert dataset_manifest["release_id"] is None
    assert dataset_manifest["scope_type"] == "SESSION"
    assert str(dataset_manifest["session_id"]) == SESSION_ID
    assert dataset_manifest["dataset_kind"] == "CANONICAL_FLIGHT"
    assert dataset_manifest["logical_name"] == (
        f"production/canonical-flight/{canonical_dataset_id}"
    )
    assert dataset_manifest["storage_uri"] == locator["canonical_dataset_uri"]
    assert dataset_manifest["schema_version"] == "1.0.0"
    assert int(dataset_manifest["row_count"]) > 1
    assert int(dataset_manifest["min_session_time_us"]) < int(
        dataset_manifest["max_session_time_us"]
    )
    assert len(str(dataset_manifest["artifact_sha256"])) == 64
    assert (
        dataset_manifest["logical_content_hash"]
        == locator["canonical_logical_content_hash"]
    )
    assert dataset_manifest["producer_component"] == "tpaa_runtime.production_p1"
    assert dataset_manifest["producer_version"] == "ED2-B1-P1-CANONICAL-1.0.0"
    assert dataset_manifest["input_hash"] == request_hash
    assert dataset_manifest["status"] == "READY"
    assert dataset_manifest["supersedes_dataset_id"] is None

    assert (
        str(object_reference["object_ref_id"])
        == str(dataset_manifest["object_ref_id"])
    )
    assert object_reference["managed_uri"] == dataset_manifest["storage_uri"]
    assert object_reference["media_type"] == "application/vnd.apache.parquet"
    assert int(object_reference["size_bytes"]) > 0
    assert (
        object_reference["artifact_sha256"]
        == dataset_manifest["artifact_sha256"]
    )
    assert (
        object_reference["logical_content_hash"]
        == dataset_manifest["logical_content_hash"]
    )
    assert object_reference["storage_backend"] == "LOCAL_OBJECT_STORE"
    assert bool(object_reference["sealed"]) is True
    assert object_reference["gc_state"] == "ACTIVE"
    assert int(object_reference["gc_state_version"]) == 0

    assert len(relation_rows) == 3
    assert all(row["relation_type"] == "PRECEDES" for row in relation_rows)
    assert all(row["relation_source"] == "OFFICIAL" for row in relation_rows)
    assert all(row["start_session_time_us"] is None for row in relation_rows)
    assert all(row["end_session_time_us"] is None for row in relation_rows)
    stage_ids = [str(row["stage_id"]) for row in stage_rows]
    assert [
        (str(row["subject_ref"]), str(row["object_ref"]))
        for row in relation_rows
    ] == list(zip(stage_ids, stage_ids[1:], strict=False))

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
    identity = changed["publication_identity"]
    assert isinstance(identity, dict)
    identity["entity_alias"] = "PRCB-C2-SUBJECT-CHANGED"
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
