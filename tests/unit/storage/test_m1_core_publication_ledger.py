from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tools.testing.m1_batch_2_support import (
    build_batch_2_fixture_products,
    seed_sqlite_core_prerequisites,
)
from tpaa_application.m1_publication import to_core_publication_bundle
from tpaa_storage.bootstrap import bootstrap_sqlite
from tpaa_storage.publication_bundle import CoreSystemObservationRecord
from tpaa_storage.sqlite_repository import SQLiteDesktopUnitOfWork

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_sqlite_core_publication_maps_only_authoritative_tables(tmp_path: Path) -> None:
    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
    )
    database = tmp_path / "m1-batch-2.sqlite3"
    bootstrap_sqlite(database)

    connection = sqlite3.connect(database)
    try:
        seed_sqlite_core_prerequisites(connection, products)
    finally:
        connection.close()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        receipt = uow.publication.publish(
            to_core_publication_bundle(products.release),
            idempotency_key="sqlite-batch-2",
            expected_version_token=0,
        )
        membership_before = uow.publication.logical_membership(products.release.release_id)
        uow.commit()

    assert receipt.reused is False
    assert receipt.version_token == 1
    assert membership_before["release"]["release_id"] == products.release.release_id
    assert membership_before["release"]["status"] == "PUBLISHED"
    assert len(membership_before["metric_instances"]) == 5
    assert len(membership_before["evidence_sets"]) == 5
    assert len(membership_before["observations"]) == 5
    assert "system_observations" not in membership_before

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        retry = uow.publication.publish(
            to_core_publication_bundle(products.release),
            idempotency_key="sqlite-batch-2",
            expected_version_token=0,
        )
        membership_after = uow.publication.logical_membership(products.release.release_id)
        uow.commit()

    assert retry.reused is True
    assert retry.version_token == 1
    assert membership_after == membership_before



def _stable_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ed2-b1-system-lane:{name}"))


def test_sqlite_core_publication_persists_db19_system_observation_lane(
    tmp_path: Path,
) -> None:
    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
    )
    database = tmp_path / "ed2-system-lane.sqlite3"
    bootstrap_sqlite(database)
    base = to_core_publication_bundle(products.release)
    base_definition = base.definitions[0]
    base_evidence = base.evidence_sets[0]
    base_metric = base.metric_instances[0]
    aircraft_id = base.observations[0].aircraft_id

    system_id = _stable_id("mission-system")
    definition_id = _stable_id("definition")
    evidence_id = _stable_id("evidence")
    metric_instance_id = _stable_id("metric-instance")
    system_observation_id = _stable_id("system-observation")
    definition_hash = "d" * 64
    metric_code = "P1-ED2-SYS-001"

    connection = sqlite3.connect(database)
    try:
        seed_sqlite_core_prerequisites(connection, products)
        connection.execute(
            """INSERT INTO "master.mission_system_instance" (
                   mission_system_instance_id, aircraft_id, system_type,
                   system_code, status, configuration_hash
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                system_id,
                aircraft_id,
                "RADAR",
                "ED2-B1-RADAR",
                "ACTIVE",
                "e" * 64,
            ),
        )
        connection.execute(
            """INSERT INTO "metric.metric_definition" (
                   metric_definition_id, metric_code, version, catalog_version,
                   catalog_hash, metric_semantic_id, metric_semantic_version,
                   name, subject_type, observation_lane, publication_route,
                   category, calculation_layer, capability_level,
                   capability_dimension, required_world_products, scope,
                   spec_uri, spec_hash, definition_hash, plugin_name,
                   plugin_version, status
               ) VALUES (
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
               )""",
            (
                definition_id,
                metric_code,
                "1.0.0",
                base_definition.catalog_version,
                base_definition.catalog_hash,
                "ED2.SYSTEM.TEST",
                1,
                metric_code,
                "MISSION_SYSTEM_INSTANCE",
                "SYSTEM_PERFORMANCE_OBSERVATION",
                "SYSTEM_PERFORMANCE_OBSERVATION",
                "TEST_ONLY",
                "TEST_ONLY_ED2_SYSTEM_LANE",
                "CAP_L1_OBSERVED",
                "SENSOR_PERFORMANCE",
                "[]",
                "EPISODE",
                "test-only://ed2/system-lane",
                definition_hash,
                definition_hash,
                "ED2_SYSTEM_TEST",
                "1.0.0",
                "TEST_ONLY_ACTIVE",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    definition = replace(
        base_definition,
        metric_definition_id=definition_id,
        metric_code=metric_code,
        metric_semantic_id="ED2.SYSTEM.TEST",
        metric_semantic_version=1,
        subject_type="MISSION_SYSTEM_INSTANCE",
        observation_lane="SYSTEM_PERFORMANCE_OBSERVATION",
        publication_route="SYSTEM_PERFORMANCE_OBSERVATION",
        definition_hash=definition_hash,
    )
    evidence = replace(
        base_evidence,
        evidence_set_id=evidence_id,
        series_locator={
            "ed2_contract": "DB_1_9_SYSTEM_PERFORMANCE_OBSERVATION",
        },
        algorithm_versions={"metric_code": metric_code},
    )
    metric = replace(
        base_metric,
        metric_instance_id=metric_instance_id,
        metric_definition_id=definition_id,
        metric_code=metric_code,
        subject_entity_id=None,
        mission_system_instance_id=system_id,
        value_numeric=0.5,
        value_structured=None,
        evidence_set_id=evidence_id,
        compute_version="ED2-B1-SYSTEM-LANE-V1",
        input_hash="f" * 64,
    )
    system_observation = CoreSystemObservationRecord(
        system_observation_id=system_observation_id,
        episode_id=metric.episode_id,
        stage_id=metric.stage_id,
        aircraft_id=aircraft_id,
        mission_system_instance_id=system_id,
        observed_metric_instance_id=metric_instance_id,
        reference_truth_profile_version="ED2-REFERENCE-V1",
        reference_quality_status="AVAILABLE",
        reference_uncertainty_summary={"status": "BOUNDED"},
        alignment_uncertainty_summary={"status": "BOUNDED"},
        observation_start_session_time_us=evidence.start_session_time_us,
        observation_end_session_time_us=evidence.end_session_time_us,
        context_tags={"source": "ED2_B1_TEST"},
        evidence_set_id=evidence_id,
        coverage=1.0,
        confidence=1.0,
        eligibility_status="ELIGIBLE",
        exclusion_reason_code=None,
        comparison_key_hash="a" * 64,
        observation_schema_version="ED2-B1-V1",
    )
    bundle = replace(
        base,
        manifest_hash=hashlib.sha256(b"ed2-dual-lane").hexdigest(),
        definitions=(*base.definitions, definition),
        evidence_sets=(*base.evidence_sets, evidence),
        metric_instances=(*base.metric_instances, metric),
        system_observations=(system_observation,),
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        receipt = uow.publication.publish(
            bundle,
            idempotency_key="ed2-b1-dual-lane",
            expected_version_token=0,
        )
        membership = uow.publication.logical_membership(bundle.release_id)
        uow.commit()

    assert receipt.reused is False
    assert len(membership["metric_instances"]) == 6
    assert len(membership["observations"]) == 5
    system_rows = membership["system_observations"]
    assert isinstance(system_rows, list)
    assert system_rows == [
        {
            "system_observation_id": system_observation_id,
            "episode_id": metric.episode_id,
            "stage_id": metric.stage_id,
            "aircraft_id": aircraft_id,
            "mission_system_instance_id": system_id,
            "observed_metric_instance_id": metric_instance_id,
            "reference_truth_profile_version": "ED2-REFERENCE-V1",
            "reference_quality_status": "AVAILABLE",
            "reference_uncertainty_summary": {"status": "BOUNDED"},
            "alignment_uncertainty_summary": {"status": "BOUNDED"},
            "observation_start_session_time_us": evidence.start_session_time_us,
            "observation_end_session_time_us": evidence.end_session_time_us,
            "context_tags": {"source": "ED2_B1_TEST"},
            "evidence_set_id": evidence_id,
            "coverage": 1.0,
            "confidence": 1.0,
            "eligibility_status": "ELIGIBLE",
            "exclusion_reason_code": None,
            "comparison_key_hash": "a" * 64,
            "observation_schema_version": "ED2-B1-V1",
        }
    ]
    metric_rows = membership["metric_instances"]
    assert isinstance(metric_rows, list)
    system_metric = next(
        item
        for item in metric_rows
        if isinstance(item, dict)
        and item.get("metric_instance_id") == metric_instance_id
    )
    assert system_metric["subject_entity_id"] is None
    assert system_metric["mission_system_instance_id"] == system_id
