"""Synthetic-only Batch 2 fixture construction and Core prerequisite seeding.

This module is evidence/test support, never a runtime authority source. It seeds
only prerequisite rows that Batch 2 production persistence deliberately refuses
to invent. Values not frozen by the M1 synthetic fixture are visibly TEST_ONLY.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tpaa_context import ResolvedEvaluationContext, resolve_evaluation_context
from tpaa_ingest import load_synthetic_fixture_bundle
from tpaa_metric import build_metric_context, compute_representative_metrics
from tpaa_observation import (
    AircraftPublicationIdentity,
    SessionRelease,
    allocate_session_release_id,
    build_session_release,
)
from tpaa_storage.hashing import canonical_request_hash
from tpaa_world import AircraftObservedWorld, project_minimal_p1_world


@dataclass(frozen=True)
class Batch2FixtureProducts:
    release: SessionRelease
    world: AircraftObservedWorld
    context: ResolvedEvaluationContext


def build_batch_2_fixture_products(
    *,
    fixture_root: Path,
    authority_root: Path,
    fixture_id: str = "BF_M1_NOMINAL_V1",
    request_label: str = "batch-2",
    release_no: int = 1,
    parent_release_id: str | None = None,
) -> Batch2FixtureProducts:
    bundle_path = fixture_root / fixture_id
    bundle = load_synthetic_fixture_bundle(bundle_path)
    request_hash = canonical_request_hash(
        {
            "command": "M1_PUBLISH_SESSION",
            "fixture_id": fixture_id,
            "request_label": request_label,
            "release_no": release_no,
        }
    )
    release_id = allocate_session_release_id(
        session_id=bundle.session.session_id,
        request_hash=request_hash,
    )
    world = project_minimal_p1_world(
        bundle_path,
        authority_root=authority_root,
        release_id=release_id,
    )
    metric_context = build_metric_context(
        bundle_path,
        authority_root=authority_root,
        world=world,
    )
    metric_batch = compute_representative_metrics(metric_context, world)
    resolved_context = resolve_evaluation_context(
        bundle_path,
        authority_root=authority_root,
    )
    identity = AircraftPublicationIdentity(
        aircraft_id=world.aircraft_id,
        aircraft_model_id=str(uuid5(NAMESPACE_URL, "tpaa-m1-batch2-test-model")),
        aircraft_instance_id=str(uuid5(NAMESPACE_URL, "tpaa-m1-batch2-test-instance")),
        subject_entity_id=str(uuid5(NAMESPACE_URL, "tpaa-m1-batch2-test-entity")),
        capability_dimension="TEST_ONLY_AIRCRAFT_FLIGHT",
        capability_type="TEST_ONLY_OBSERVED_PERFORMANCE",
    )
    release = build_session_release(
        release_id=release_id,
        request_hash=request_hash,
        release_no=release_no,
        parent_release_id=parent_release_id,
        context=metric_context,
        context_version=resolved_context.context_version,
        world=world,
        batch=metric_batch,
        identity=identity,
    )
    return Batch2FixtureProducts(
        release=release,
        world=world,
        context=resolved_context,
    )


def _sqlite_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def seed_sqlite_core_prerequisites(
    connection: sqlite3.Connection,
    products: Batch2FixtureProducts,
) -> None:
    release = products.release
    world = products.world
    context = products.context
    identity = release.observations[0].identity
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """INSERT INTO "registry.training_session" (
               session_id, session_code, session_type, start_session_time_us,
               end_session_time_us, training_type_set, data_status, source_count,
               schema_version
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            release.session_id,
            "TEST_ONLY_M1_BATCH2",
            "SIM",
            world.start_session_time_us,
            world.end_session_time_us,
            _sqlite_json([]),
            "TEST_ONLY_READY",
            1,
            "1.6.0",
        ),
    )
    connection.execute(
        """INSERT INTO "master.aircraft_model" (
               aircraft_model_id, type_code, model_name
           ) VALUES (?, ?, ?)""",
        (identity.aircraft_model_id, "TEST_ONLY_TYPE", "TEST_ONLY_MODEL"),
    )
    connection.execute(
        """INSERT INTO "master.aircraft" (
               aircraft_id, aircraft_model_id, internal_code, master_data_status
           ) VALUES (?, ?, ?, ?)""",
        (
            identity.aircraft_id,
            identity.aircraft_model_id,
            "TEST_ONLY_AIRCRAFT",
            "TEST_ONLY",
        ),
    )
    connection.execute(
        """INSERT INTO "master.entity" (
               entity_id, session_id, entity_type, alias
           ) VALUES (?, ?, ?, ?)""",
        (
            identity.subject_entity_id,
            release.session_id,
            "AIRCRAFT",
            "TEST_ONLY_SUBJECT",
        ),
    )
    connection.execute(
        """INSERT INTO "master.aircraft_instance" (
               aircraft_instance_id, session_id, aircraft_id, entity_id,
               instance_seq, start_session_time_us, end_session_time_us,
               start_reason, identity_scope, identity_confidence
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            identity.aircraft_instance_id,
            release.session_id,
            identity.aircraft_id,
            identity.subject_entity_id,
            0,
            world.start_session_time_us,
            world.end_session_time_us,
            "TEST_ONLY",
            "SESSION_ONLY",
            1.0,
        ),
    )
    connection.execute(
        """INSERT INTO "context.evaluation_context" (
               context_id, session_id, context_version, revision_no,
               rule_set_version, metric_profile_version, status
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            release.context_id,
            release.session_id,
            release.context_version,
            context.revision_no,
            context.rule_set_version,
            context.metric_profile_version,
            context.status,
        ),
    )
    connection.execute(
        """INSERT INTO "episode.training_episode" (
               episode_id, session_id, episode_type, context_id,
               start_session_time_us, end_session_time_us, subject_scope,
               primary_aircraft_id, world_capability_code, episode_status,
               detector_version, coverage, confidence
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            world.episode_id,
            release.session_id,
            "BASIC_FLIGHT",
            release.context_id,
            world.start_session_time_us,
            world.end_session_time_us,
            "AIRCRAFT",
            identity.aircraft_id,
            world.capability_code,
            world.status,
            world.world_version,
            world.coverage,
            world.confidence,
        ),
    )
    for stage in world.stages:
        connection.execute(
            """INSERT INTO "episode.episode_stage" (
                   stage_id, episode_id, stage_type, stage_order,
                   start_session_time_us, end_session_time_us, detection_method,
                   stage_status, coverage, confidence, detector_version,
                   supersedes_stage_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                stage.stage_id,
                stage.episode_id,
                stage.stage_type,
                stage.stage_order,
                stage.start_session_time_us,
                stage.end_session_time_us,
                stage.detection_method,
                stage.stage_status,
                stage.coverage,
                stage.confidence,
                stage.detector_version,
                stage.supersedes_stage_id,
            ),
        )
    for definition in release.definitions:
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
                definition.metric_definition_id,
                definition.metric_code,
                definition.algorithm_version,
                definition.catalog_version,
                definition.catalog_hash,
                definition.semantic_id,
                definition.semantic_version,
                definition.metric_code,
                definition.subject_type,
                definition.observation_lane,
                definition.publication_route,
                "TEST_ONLY",
                "TEST_ONLY_M1_METRIC",
                "CAP_L1_OBSERVED",
                identity.capability_dimension,
                _sqlite_json([world.world_product_id]),
                "EPISODE",
                f"test-only://metric/{definition.metric_code}",
                definition.definition_hash,
                definition.definition_hash,
                definition.algorithm_id,
                definition.algorithm_version,
                "TEST_ONLY_ACTIVE",
            ),
        )
    connection.commit()


def seed_postgres_core_prerequisites(
    connection: Any,
    products: Batch2FixtureProducts,
) -> None:
    from psycopg.types.json import Jsonb

    release = products.release
    world = products.world
    context = products.context
    identity = release.observations[0].identity
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO "registry"."training_session" (
                   session_id, session_code, session_type, start_session_time_us,
                   end_session_time_us, training_type_set, data_status, source_count,
                   schema_version
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                release.session_id,
                "TEST_ONLY_M1_BATCH2",
                "SIM",
                world.start_session_time_us,
                world.end_session_time_us,
                [],
                "TEST_ONLY_READY",
                1,
                "1.6.0",
            ),
        )
        cursor.execute(
            """INSERT INTO "master"."aircraft_model" (
                   aircraft_model_id, type_code, model_name
               ) VALUES (%s, %s, %s)""",
            (identity.aircraft_model_id, "TEST_ONLY_TYPE", "TEST_ONLY_MODEL"),
        )
        cursor.execute(
            """INSERT INTO "master"."aircraft" (
                   aircraft_id, aircraft_model_id, internal_code, master_data_status
               ) VALUES (%s, %s, %s, %s)""",
            (
                identity.aircraft_id,
                identity.aircraft_model_id,
                "TEST_ONLY_AIRCRAFT",
                "TEST_ONLY",
            ),
        )
        cursor.execute(
            """INSERT INTO "master"."entity" (
                   entity_id, session_id, entity_type, alias
               ) VALUES (%s, %s, %s, %s)""",
            (
                identity.subject_entity_id,
                release.session_id,
                "AIRCRAFT",
                "TEST_ONLY_SUBJECT",
            ),
        )
        cursor.execute(
            """INSERT INTO "master"."aircraft_instance" (
                   aircraft_instance_id, session_id, aircraft_id, entity_id,
                   instance_seq, start_session_time_us, end_session_time_us,
                   start_reason, identity_scope, identity_confidence
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                identity.aircraft_instance_id,
                release.session_id,
                identity.aircraft_id,
                identity.subject_entity_id,
                0,
                world.start_session_time_us,
                world.end_session_time_us,
                "TEST_ONLY",
                "SESSION_ONLY",
                1.0,
            ),
        )
        cursor.execute(
            """INSERT INTO "context"."evaluation_context" (
                   context_id, session_id, context_version, revision_no,
                   rule_set_version, metric_profile_version, status
               ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                release.context_id,
                release.session_id,
                release.context_version,
                context.revision_no,
                context.rule_set_version,
                context.metric_profile_version,
                context.status,
            ),
        )
        cursor.execute(
            """INSERT INTO "episode"."training_episode" (
                   episode_id, session_id, episode_type, context_id,
                   start_session_time_us, end_session_time_us, subject_scope,
                   primary_aircraft_id, world_capability_code, episode_status,
                   detector_version, coverage, confidence
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                world.episode_id,
                release.session_id,
                "BASIC_FLIGHT",
                release.context_id,
                world.start_session_time_us,
                world.end_session_time_us,
                "AIRCRAFT",
                identity.aircraft_id,
                world.capability_code,
                world.status,
                world.world_version,
                world.coverage,
                world.confidence,
            ),
        )
        for stage in world.stages:
            cursor.execute(
                """INSERT INTO "episode"."episode_stage" (
                       stage_id, episode_id, stage_type, stage_order,
                       start_session_time_us, end_session_time_us, detection_method,
                       stage_status, coverage, confidence, detector_version,
                       supersedes_stage_id
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    stage.stage_id,
                    stage.episode_id,
                    stage.stage_type,
                    stage.stage_order,
                    stage.start_session_time_us,
                    stage.end_session_time_us,
                    stage.detection_method,
                    stage.stage_status,
                    stage.coverage,
                    stage.confidence,
                    stage.detector_version,
                    stage.supersedes_stage_id,
                ),
            )
        for definition in release.definitions:
            cursor.execute(
                """INSERT INTO "metric"."metric_definition" (
                       metric_definition_id, metric_code, version, catalog_version,
                       catalog_hash, metric_semantic_id, metric_semantic_version,
                       name, subject_type, observation_lane, publication_route,
                       category, calculation_layer, capability_level,
                       capability_dimension, required_world_products, scope,
                       spec_uri, spec_hash, definition_hash, plugin_name,
                       plugin_version, status
                   ) VALUES (
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                   )""",
                (
                    definition.metric_definition_id,
                    definition.metric_code,
                    definition.algorithm_version,
                    definition.catalog_version,
                    definition.catalog_hash,
                    definition.semantic_id,
                    definition.semantic_version,
                    definition.metric_code,
                    definition.subject_type,
                    definition.observation_lane,
                    definition.publication_route,
                    "TEST_ONLY",
                    "TEST_ONLY_M1_METRIC",
                    "CAP_L1_OBSERVED",
                    identity.capability_dimension,
                    Jsonb([world.world_product_id]),
                    "EPISODE",
                    f"test-only://metric/{definition.metric_code}",
                    definition.definition_hash,
                    definition.definition_hash,
                    definition.algorithm_id,
                    definition.algorithm_version,
                    "TEST_ONLY_ACTIVE",
                ),
            )
    connection.commit()
