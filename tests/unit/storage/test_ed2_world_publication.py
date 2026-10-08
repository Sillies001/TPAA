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
from tpaa_storage.publication_bundle import (
    CoreTpaaMChainRecord,
    CoreWorldProductRecord,
    CoreWorldRelationRecord,
)
from tpaa_storage.sqlite_repository import SQLiteDesktopUnitOfWork

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _id(kind: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ed2-b1-world-membership:{kind}"))


def test_core_publication_atomically_persists_world_relation_chain_and_evidence_refs(
    tmp_path: Path,
) -> None:
    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
    )
    database = tmp_path / "ed2-world-membership.sqlite3"
    bootstrap_sqlite(database)

    connection = sqlite3.connect(database)
    try:
        seed_sqlite_core_prerequisites(connection, products)
    finally:
        connection.close()

    base = to_core_publication_bundle(products.release)
    observation = base.observations[0]
    metric = base.metric_instances[0]
    evidence = base.evidence_sets[0]
    world_id = _id("world")
    relation_id = _id("relation")
    chain_id = _id("chain")

    world = CoreWorldProductRecord(
        world_product_id=world_id,
        episode_id=metric.episode_id,
        stage_id=metric.stage_id,
        world_kind="TRUTH",
        subject_id=observation.subject_entity_id,
        observer_id=None,
        actor_id=None,
        aircraft_id=observation.aircraft_id,
        aircraft_instance_id=observation.aircraft_instance_id,
        dataset_id=None,
        start_session_time_us=evidence.start_session_time_us,
        end_session_time_us=evidence.end_session_time_us,
        status="READY",
        coverage=1.0,
        confidence=1.0,
        reason_codes=(),
        source_authority_signature="ED2_B1_TEST_WORLD_AUTHORITY",
        world_version="ED2-B1-WORLD-V1",
        policy_version="ED2-CONFORMANCE-B1",
        artifact_sha256="a" * 64,
        logical_content_hash="b" * 64,
        request_hash=base.request_hash,
    )
    relation = CoreWorldRelationRecord(
        relation_id=relation_id,
        episode_id=metric.episode_id,
        stage_id=metric.stage_id,
        relation_type="ED2_TEST_ASSOCIATION",
        subject_ref=observation.subject_entity_id,
        object_ref=observation.aircraft_id,
        subject_series_id=None,
        object_series_id=None,
        cross_series=False,
        start_session_time_us=evidence.start_session_time_us,
        end_session_time_us=evidence.end_session_time_us,
        properties={"authority": "ED2_B1_TEST"},
        confidence=1.0,
        relation_source="DERIVED",
        method_version="ED2-B1-RELATION-V1",
    )
    chain = CoreTpaaMChainRecord(
        chain_id=chain_id,
        episode_id=metric.episode_id,
        stage_id=metric.stage_id,
        refs={
            "world_product_ids": [world_id],
            "relation_ids": [relation_id],
        },
        start_session_time_us=evidence.start_session_time_us,
        end_session_time_us=evidence.end_session_time_us,
        chain_status="COMPLETE",
        coverage=1.0,
        confidence=1.0,
        break_reason=None,
        chain_version="ED2-B1-CHAIN-V1",
    )
    linked_evidence = replace(
        evidence,
        world_product_ids=(world_id,),
        relation_ids=(relation_id,),
    )
    linked_metric = replace(
        metric,
        tpaa_chain_id=chain_id,
        world_product_versions={
            **metric.world_product_versions,
            "ed2_world_product_id": world_id,
            "ed2_world_logical_content_hash": world.logical_content_hash,
        },
    )
    bundle = replace(
        base,
        manifest_hash=hashlib.sha256(
            b"ED2_B1_WORLD_RELATION_CHAIN_MEMBERSHIP"
        ).hexdigest(),
        evidence_sets=(linked_evidence, *base.evidence_sets[1:]),
        metric_instances=(linked_metric, *base.metric_instances[1:]),
        world_products=(world,),
        world_relations=(relation,),
        tpaa_m_chains=(chain,),
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        receipt = uow.publication.publish(
            bundle,
            idempotency_key="ed2-b1-world-membership",
            expected_version_token=0,
        )
        membership = uow.publication.logical_membership(bundle.release_id)
        uow.commit()

    assert receipt.reused is False
    assert membership["world_products"] == [
        {
            "world_product_id": world_id,
            "episode_id": metric.episode_id,
            "stage_id": metric.stage_id,
            "world_kind": "TRUTH",
            "subject_id": observation.subject_entity_id,
            "observer_id": None,
            "actor_id": None,
            "aircraft_id": observation.aircraft_id,
            "aircraft_instance_id": observation.aircraft_instance_id,
            "dataset_id": None,
            "start_session_time_us": evidence.start_session_time_us,
            "end_session_time_us": evidence.end_session_time_us,
            "status": "READY",
            "coverage": 1.0,
            "confidence": 1.0,
            "reason_codes": [],
            "source_authority_signature": "ED2_B1_TEST_WORLD_AUTHORITY",
            "world_version": "ED2-B1-WORLD-V1",
            "policy_version": "ED2-CONFORMANCE-B1",
            "artifact_sha256": "a" * 64,
            "logical_content_hash": "b" * 64,
            "request_hash": base.request_hash,
            "supersedes_id": None,
        }
    ]
    assert membership["world_relations"][0]["relation_id"] == relation_id
    assert membership["tpaa_m_chains"][0]["chain_id"] == chain_id

    evidence_rows = membership["evidence_sets"]
    assert isinstance(evidence_rows, list)
    linked = next(
        item
        for item in evidence_rows
        if isinstance(item, dict)
        and item.get("evidence_set_id") == evidence.evidence_set_id
    )
    assert linked["world_product_ids"] == [world_id]
    assert linked["relation_ids"] == [relation_id]

    metric_rows = membership["metric_instances"]
    assert isinstance(metric_rows, list)
    linked_metric_row = next(
        item
        for item in metric_rows
        if isinstance(item, dict)
        and item.get("metric_instance_id") == metric.metric_instance_id
    )
    assert linked_metric_row["tpaa_chain_id"] == chain_id


def test_legacy_membership_projection_does_not_invent_new_world_keys(
    tmp_path: Path,
) -> None:
    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
    )
    database = tmp_path / "legacy-membership.sqlite3"
    bootstrap_sqlite(database)
    connection = sqlite3.connect(database)
    try:
        seed_sqlite_core_prerequisites(connection, products)
    finally:
        connection.close()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        uow.publication.publish(
            to_core_publication_bundle(products.release),
            idempotency_key="ed2-b1-legacy-shape",
            expected_version_token=0,
        )
        membership = uow.publication.logical_membership(
            products.release.release_id
        )
        uow.commit()

    assert "system_observations" not in membership
    assert "world_products" not in membership
    assert "world_relations" not in membership
    assert "tpaa_m_chains" not in membership
    first_evidence = membership["evidence_sets"][0]
    assert "world_product_ids" not in first_evidence
    assert "relation_ids" not in first_evidence
