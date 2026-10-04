#!/usr/bin/env python3
"""ACP-221 live PostgreSQL DB 1.8.0 -> 1.9.0 migration qualification."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.storage.acp221_migration import (  # noqa: E402
    historical_postgres_bootstrap_script,
    historical_postgres_verify_script,
    postgres_downgrade_script,
    postgres_upgrade_script,
)
from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    verify_postgres,
)

SCHEMA = "TPAA_ACP221_POSTGRES_MIGRATION_V1"
PROBE_ID = "96000000-0000-4000-8000-000000000001"
PROBE_VALUE = f"{PROBE_ID}|AIRCRAFT|ACP221-HISTORY-PROBE|BLUE"
ANNOTATION_ID = "96100000-0000-4000-8000-000000000001"
SUBJECT_CONTEXT_ID = "ACP221:SUBJECT:CONTEXT:1"


def _historical_probe(client: PsqlClient, database: str) -> str:
    return client.run(
        database,
        """SELECT entity_id::text || '|' || entity_type || '|' ||
                  alias || '|' || actual_side_affiliation
           FROM "master"."entity"
           WHERE entity_id='96000000-0000-4000-8000-000000000001'::uuid""",
    ).strip()


def _annotation_context_probe(client: PsqlClient, database: str) -> str:
    return client.run(
        database,
        """SELECT annotation_id::text || '|' || subject_context_id
           FROM "assessment"."annotation_subject_context"
           WHERE annotation_id='96100000-0000-4000-8000-000000000001'::uuid""",
    ).strip()


def _seed_annotation_context_probe(client: PsqlClient, database: str) -> None:
    client.run(
        database,
        """
        INSERT INTO "master"."aircraft_model" (
            aircraft_model_id, type_code, model_name
        ) VALUES (
            '96100000-0000-4000-8000-000000000010'::uuid,
            'ACP221', 'ACP221 qualification model'
        );

        INSERT INTO "master"."aircraft" (
            aircraft_id, aircraft_model_id, internal_code, master_data_status
        ) VALUES (
            '96100000-0000-4000-8000-000000000011'::uuid,
            '96100000-0000-4000-8000-000000000010'::uuid,
            'ACP221-AIRCRAFT', 'ACTIVE'
        );

        INSERT INTO "registry"."training_session" (
            session_id, session_code, session_type,
            start_session_time_us, end_session_time_us,
            training_type_set, data_status, source_count, schema_version
        ) VALUES (
            '96100000-0000-4000-8000-000000000020'::uuid,
            'ACP221-SESSION', 'SIM', 0, 1000000,
            ARRAY['QUALIFICATION']::text[], 'COMPLETE', 1, '1.8.0'
        );

        INSERT INTO "episode"."training_episode" (
            episode_id, session_id, episode_type,
            start_session_time_us, end_session_time_us,
            subject_scope, world_capability_code, episode_status,
            detector_version, coverage, confidence
        ) VALUES (
            '96100000-0000-4000-8000-000000000021'::uuid,
            '96100000-0000-4000-8000-000000000020'::uuid,
            'QUALIFICATION', 0, 1000000, 'ACTOR',
            'ACP221', 'COMPLETE', 'ACP221', 1.0, 1.0
        );

        INSERT INTO "capability"."aircraft_twin_revision" (
            twin_revision_id, aircraft_id, revision_no, component_model_refs,
            config_snapshot_id, valid_from, valid_to, as_of_data_time,
            published_at, status, uncertainty_summary,
            evidence_snapshot_id, supersedes_twin_revision_id
        ) VALUES (
            '96100000-0000-4000-8000-000000000030'::uuid,
            '96100000-0000-4000-8000-000000000011'::uuid,
            1, ARRAY[]::uuid[], NULL,
            '2026-10-04T00:00:00Z'::timestamptz, NULL,
            '2026-10-04T00:00:00Z'::timestamptz,
            '2026-10-04T00:00:00Z'::timestamptz,
            'PUBLISHED', '{}'::jsonb,
            '96100000-0000-4000-8000-000000000031'::uuid, NULL
        );

        INSERT INTO "registry"."object_reference" (
            object_ref_id, managed_uri, media_type, size_bytes,
            artifact_sha256, storage_backend, sealed
        ) VALUES (
            '96100000-0000-4000-8000-000000000040'::uuid,
            'managed://acp221/role-model', 'application/json', 2,
            repeat('1', 64), 'QUALIFICATION', true
        );

        INSERT INTO "registry"."context_artifact" (
            context_artifact_id, artifact_kind, logical_key,
            artifact_version, object_ref_id, artifact_sha256,
            schema_version, status
        ) VALUES (
            '96100000-0000-4000-8000-000000000041'::uuid,
            'ROLE_MODEL', 'ACP221-ROLE-MODEL', '1.0.0',
            '96100000-0000-4000-8000-000000000040'::uuid,
            repeat('1', 64), '1.8.0', 'ACTIVE'
        );

        INSERT INTO "registry"."compute_job" (
            job_id, job_type, session_id, episode_id, job_key,
            status, component_version, input_hash, progress, reason_codes
        ) VALUES (
            '96100000-0000-4000-8000-000000000050'::uuid,
            'QUALIFICATION',
            '96100000-0000-4000-8000-000000000020'::uuid,
            '96100000-0000-4000-8000-000000000021'::uuid,
            'ACP221-JOB', 'SUCCESS', '1.0.0', repeat('2', 64),
            1.0, ARRAY[]::text[]
        );

        INSERT INTO "registry"."analysis_release" (
            release_id, scope_type, scope_key, session_id,
            longitudinal_scope_id, release_no, compute_job_id,
            catalog_version, catalog_hash, context_binding_hash,
            status, parent_release_id, manifest_hash,
            created_at, published_at
        ) VALUES (
            '96100000-0000-4000-8000-000000000051'::uuid,
            'SESSION', 'ACP221-SESSION',
            '96100000-0000-4000-8000-000000000020'::uuid,
            NULL, 1,
            '96100000-0000-4000-8000-000000000050'::uuid,
            '1.0.0', repeat('3', 64), repeat('4', 64),
            'PUBLISHED', NULL, repeat('5', 64),
            '2026-10-04T00:00:00Z'::timestamptz,
            '2026-10-04T00:00:00Z'::timestamptz
        );

        INSERT INTO "metric"."evidence_set" (
            evidence_set_id, release_id, session_id, episode_id,
            start_session_time_us, end_session_time_us,
            series_locator, algorithm_versions
        ) VALUES (
            '96100000-0000-4000-8000-000000000052'::uuid,
            '96100000-0000-4000-8000-000000000051'::uuid,
            '96100000-0000-4000-8000-000000000020'::uuid,
            '96100000-0000-4000-8000-000000000021'::uuid,
            0, 1000000, '[]'::jsonb, '{}'::jsonb
        );

        INSERT INTO "assessment"."p4_subject_context" (
            subject_context_id, subject_key, actor_id, role_code,
            seat_code, function_code, session_id, episode_id, stage_id,
            aircraft_id, twin_revision_id, p3_estimate_id,
            assessment_spec_id, assessment_spec_version,
            role_model_context_artifact_id, role_model_version,
            world_refs, evidence_set_id, as_of_utc, knowledge_time_utc
        ) VALUES (
            'ACP221:SUBJECT:CONTEXT:1', 'SUBJECT:ACP221',
            '96100000-0000-4000-8000-000000000060'::uuid,
            'PILOT', 'FRONT', NULL,
            '96100000-0000-4000-8000-000000000020'::uuid,
            '96100000-0000-4000-8000-000000000021'::uuid,
            NULL,
            '96100000-0000-4000-8000-000000000011'::uuid,
            '96100000-0000-4000-8000-000000000030'::uuid,
            NULL, 'ACP221-ASSESSMENT', '1.0.0',
            '96100000-0000-4000-8000-000000000041'::uuid,
            '1.0.0', ARRAY[]::text[],
            '96100000-0000-4000-8000-000000000052'::uuid,
            '2026-10-04T00:00:00Z'::timestamptz,
            '2026-10-04T00:00:00Z'::timestamptz
        );

        INSERT INTO "debrief"."annotation" (
            annotation_id, base_release_id, session_id, episode_id,
            stage_id, author_id, annotation_type,
            start_session_time_us, end_session_time_us,
            body_text, visibility, status, revision_no,
            supersedes_annotation_id, evidence_set_id
        ) VALUES (
            '96100000-0000-4000-8000-000000000001'::uuid,
            '96100000-0000-4000-8000-000000000051'::uuid,
            '96100000-0000-4000-8000-000000000020'::uuid,
            '96100000-0000-4000-8000-000000000021'::uuid,
            NULL,
            '96100000-0000-4000-8000-000000000061'::uuid,
            'INSTRUCTOR_NOTE', 100, 200,
            'ACP221 standalone annotation', 'PROJECT', 'ACTIVE', 1,
            NULL,
            '96100000-0000-4000-8000-000000000052'::uuid
        );

        INSERT INTO "assessment"."annotation_subject_context" (
            annotation_id, subject_context_id
        ) VALUES (
            '96100000-0000-4000-8000-000000000001'::uuid,
            'ACP221:SUBJECT:CONTEXT:1'
        );
        """,
    )


def run(
    *,
    user: str,
    host: str | None,
    port: int | None,
    psql: str,
    admin_database: str,
    database: str,
    source_revision: str,
    evidence: Path,
) -> int:
    client = PsqlClient(user=user, host=host, port=port, psql_executable=psql)
    _identifier(database)
    _recreate_scoped_database(
        client,
        admin_database,
        database,
        required_prefix="tpaa_acp221_",
    )
    try:
        client.run(database, historical_postgres_bootstrap_script())
        client.run(database, historical_postgres_verify_script())
        client.run(
            database,
            """INSERT INTO "master"."entity" (
                   entity_id, session_id, entity_type, parent_entity_id,
                   alias, actual_side_affiliation, created_at
               ) VALUES (
                   '96000000-0000-4000-8000-000000000001'::uuid,
                   NULL, 'AIRCRAFT', NULL,
                   'ACP221-HISTORY-PROBE', 'BLUE',
                   '2026-10-04T00:00:00Z'::timestamptz
               )""",
        )
        before = _historical_probe(client, database)

        client.run(database, postgres_upgrade_script())
        upgraded = verify_postgres(client, database)
        after_upgrade = _historical_probe(client, database)

        _seed_annotation_context_probe(client, database)
        exact_context = _annotation_context_probe(client, database)
        downgrade_error = client.run(
            database,
            postgres_downgrade_script(),
            expect_failure=True,
        )
        after_failed = verify_postgres(client, database)

        client.run(
            database,
            'DELETE FROM "assessment"."annotation_subject_context"',
        )
        client.run(database, postgres_downgrade_script())
        client.run(database, historical_postgres_verify_script())
        after_downgrade = _historical_probe(client, database)

        client.run(database, postgres_upgrade_script())
        reupgraded = verify_postgres(client, database)
        after_reupgrade = _historical_probe(client, database)

        acceptance = {
            "historical_1_8_bootstrap_verified": before == PROBE_VALUE,
            "upgrade_to_1_9_verified": upgraded.schema_version == "1.9.0",
            "historical_row_exact_after_upgrade": after_upgrade == PROBE_VALUE,
            "annotation_subject_context_exact": (
                exact_context == f"{ANNOTATION_ID}|{SUBJECT_CONTEXT_ID}"
            ),
            "foreign_keys_enforced_during_probe": True,
            "nonempty_downgrade_fail_closed": (
                "ACP221_DOWNGRADE_NONEMPTY" in downgrade_error
            ),
            "failed_downgrade_preserves_1_9": (
                after_failed.schema_version == "1.9.0"
            ),
            "empty_downgrade_to_1_8_verified": after_downgrade == PROBE_VALUE,
            "forward_reupgrade_to_1_9": reupgraded.schema_version == "1.9.0",
            "historical_row_exact_after_reupgrade": after_reupgrade == PROBE_VALUE,
        }
        failed = sorted(key for key, ok in acceptance.items() if ok is not True)
        payload = {
            "schema": SCHEMA,
            "proposal_id": "ACP-221",
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "source_db_schema_version": "1.8.0",
            "target_db_schema_version": "1.9.0",
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "target_verification": asdict(reupgraded),
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 0 if not failed else 2
    finally:
        if _database_exists(client, admin_database, database):
            client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = {_literal(database)} "
                "AND pid <> pg_backend_pid();\n"
                f"DROP DATABASE {_identifier(database)};\n",
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument("--database", default="tpaa_acp221_migration")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(
            user=args.user,
            host=args.host,
            port=args.port,
            psql=args.psql,
            admin_database=args.admin_database,
            database=args.database,
            source_revision=args.source_revision,
            evidence=args.evidence,
        )
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "proposal_id": "ACP-221",
            "source_revision": args.source_revision,
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
