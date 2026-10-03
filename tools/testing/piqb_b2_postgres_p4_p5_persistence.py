#!/usr/bin/env python3
"""PIQB B2 real PostgreSQL P4/P5 exact persistence and restart parity gate."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    bootstrap_postgres,
    verify_postgres,
)
from tpaa_application import P4P5PersistenceError, P4P5PersistenceRepository  # noqa: E402
from tpaa_assessment import P4AssessmentRevision, P4SubjectContext, P5AssessmentRevision  # noqa: E402
from tpaa_context import canonical_hash, pseudonymous_subject_key  # noqa: E402
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite, verify_sqlite  # noqa: E402
from tpaa_storage.postgres_repository import PostgreSQLServiceUnitOfWork  # noqa: E402
from tpaa_world import P5CompositionSnapshot, P5ParticipantBinding  # noqa: E402

SCHEMA = "TPAA_PIQB_B2_P4_P5_POSTGRES_PERSISTENCE_V1"
TRACKING_ISSUE = 209
TASK_IDS = ("PIQB-B2-002", "PIQB-B2-003", "PIQB-B2-006", "PIQB-B2-008")

AIRCRAFT_MODEL = "94100000-0000-4000-8000-000000000001"
AIRCRAFT = "94100000-0000-4000-8000-000000000002"
TWIN = "94100000-0000-4000-8000-000000000003"
SESSION = "94100000-0000-4000-8000-000000000004"
EPISODE = "94100000-0000-4000-8000-000000000005"
ROLE_OBJECT = "94100000-0000-4000-8000-000000000006"
ROLE_ARTIFACT = "94100000-0000-4000-8000-000000000007"
JOB = "94100000-0000-4000-8000-000000000008"
RELEASE = "94100000-0000-4000-8000-000000000009"
EVIDENCE = "94100000-0000-4000-8000-00000000000a"
ACTOR = "94100000-0000-4000-8000-00000000000b"
P4_ID = "94100000-0000-4000-8000-00000000000c"
TEAM = "94100000-0000-4000-8000-00000000000d"
P5_ID = "94100000-0000-4000-8000-00000000000e"
AS_OF = "2026-09-20T12:00:00Z"
CREATED = "2026-09-20T12:30:00Z"


def _subject() -> P4SubjectContext:
    subject_key = pseudonymous_subject_key(ACTOR)
    identity = {
        "subject_key": subject_key,
        "role_code": "SUBJECT_SELF",
        "seat_code": "FRONT",
        "function_code": "PILOT",
        "session_id": SESSION,
        "episode_id": EPISODE,
        "stage_id": None,
        "aircraft_id": AIRCRAFT,
        "twin_revision_id": TWIN,
        "p3_estimate_id": None,
        "assessment_spec_id": "P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        "assessment_spec_version": "1.0.0",
        "role_model_context_artifact_id": ROLE_ARTIFACT,
        "as_of_utc": AS_OF,
    }
    return P4SubjectContext(
        subject_context_id=f"P4_SUBJECT_CONTEXT_SHA256:{canonical_hash(identity)}",
        subject_key=subject_key,
        actor_id=ACTOR,
        role_code="SUBJECT_SELF",
        seat_code="FRONT",
        function_code="PILOT",
        session_id=SESSION,
        episode_id=EPISODE,
        stage_id=None,
        aircraft_id=AIRCRAFT,
        twin_revision_id=TWIN,
        p3_estimate_id=None,
        assessment_spec_id="P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        role_model_context_artifact_id=ROLE_ARTIFACT,
        role_model_version="1.0.0",
        world_refs=("world:action:ordered-2", "world:perceived:ordered-1"),
        evidence_set_id=EVIDENCE,
        as_of_utc=AS_OF,
        knowledge_time_utc="2026-09-20T11:59:59Z",
    )


def _p4(subject: P4SubjectContext) -> P4AssessmentRevision:
    evidence_ids = (
        "P4_HM_EVIDENCE_SHA256:" + "2" * 64,
        "P4_HM_EVIDENCE_SHA256:" + "1" * 64,
    )
    payload = {
        "subject_context_id": subject.subject_context_id,
        "subject_key": subject.subject_key,
        "actor_id": subject.actor_id,
        "role_code": subject.role_code,
        "seat_code": subject.seat_code,
        "function_code": subject.function_code,
        "session_id": subject.session_id,
        "episode_id": subject.episode_id,
        "aircraft_id": subject.aircraft_id,
        "twin_revision_id": subject.twin_revision_id,
        "p3_estimate_id": subject.p3_estimate_id,
        "assessment_spec_id": subject.assessment_spec_id,
        "assessment_spec_version": subject.assessment_spec_version,
        "role_model_version": subject.role_model_version,
        "world_refs": list(subject.world_refs),
        "machine_evidence_ids": list(evidence_ids),
        "instructor_annotation_ids": [],
        "score": None,
        "grade": None,
        "status": "APPROVED",
        "confidence": 0.9,
        "evidence_set_id": subject.evidence_set_id,
        "created_at_utc": CREATED,
        "supersedes_id": None,
        "approval_state": "APPROVED",
        "p3_claim_level": "P3_EVIDENCE_UNAVAILABLE",
        "p3_validity_status": "UNAVAILABLE",
        "p3_as_of_utc": AS_OF,
        "uncertainty_lower": None,
        "uncertainty_upper": None,
    }
    return P4AssessmentRevision(
        actor_assessment_id=P4_ID,
        subject_context_id=subject.subject_context_id,
        subject_key=subject.subject_key,
        actor_id=subject.actor_id,
        role_code=subject.role_code,
        seat_code=subject.seat_code,
        function_code=subject.function_code,
        session_id=subject.session_id,
        episode_id=subject.episode_id,
        aircraft_id=subject.aircraft_id,
        twin_revision_id=subject.twin_revision_id,
        p3_estimate_id=None,
        assessment_spec_id=subject.assessment_spec_id,
        assessment_spec_version=subject.assessment_spec_version,
        role_model_version=subject.role_model_version,
        world_refs=subject.world_refs,
        machine_evidence_ids=evidence_ids,
        instructor_annotation_ids=(),
        score=None,
        grade=None,
        status="APPROVED",
        confidence=0.9,
        evidence_set_id=subject.evidence_set_id,
        created_at_utc=CREATED,
        supersedes_id=None,
        approval_state="APPROVED",
        p3_claim_level="P3_EVIDENCE_UNAVAILABLE",
        p3_validity_status="UNAVAILABLE",
        p3_as_of_utc=AS_OF,
        uncertainty_lower=None,
        uncertainty_upper=None,
        logical_content_hash=canonical_hash(payload),
    )


def _composition(subject: P4SubjectContext) -> P5CompositionSnapshot:
    participant = P5ParticipantBinding(
        subject_key=subject.subject_key,
        role_code="FLIGHT_LEAD",
        aircraft_id=AIRCRAFT,
        twin_revision_id=TWIN,
        p4_revision_id=P4_ID,
    )
    identity = {
        "session_id": SESSION,
        "mission_episode_id": EPISODE,
        "team_id": TEAM,
        "participant_bindings": [
            {
                "subject_key": participant.subject_key,
                "role_code": participant.role_code,
                "aircraft_id": participant.aircraft_id,
                "twin_revision_id": participant.twin_revision_id,
                "p4_revision_id": participant.p4_revision_id,
            }
        ],
        "world_snapshot_refs": ["world:mission:ordered"],
        "scenario_context_artifact_id": None,
        "role_model_context_artifact_id": ROLE_ARTIFACT,
        "assessment_spec_id": "P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        "assessment_spec_version": "1.0.0",
        "as_of_utc": AS_OF,
    }
    digest = canonical_hash(identity)
    return P5CompositionSnapshot(
        composition_id=f"P5_COMPOSITION_SHA256:{digest}",
        session_id=SESSION,
        mission_episode_id=EPISODE,
        team_id=TEAM,
        participant_subject_keys=(subject.subject_key,),
        participant_bindings=(participant,),
        world_snapshot_refs=("world:mission:ordered",),
        scenario_context_artifact_id=None,
        role_model_context_artifact_id=ROLE_ARTIFACT,
        assessment_spec_id="P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        as_of_utc=AS_OF,
        composition_hash=digest,
    )


def _p5(composition: P5CompositionSnapshot) -> P5AssessmentRevision:
    objective_refs = ("objective:ordered:2", "objective:ordered:1")
    payload = {
        "composition_id": composition.composition_id,
        "session_id": composition.session_id,
        "mission_episode_id": composition.mission_episode_id,
        "team_id": composition.team_id,
        "assessment_spec_id": composition.assessment_spec_id,
        "assessment_spec_version": composition.assessment_spec_version,
        "participant_subject_keys": list(composition.participant_subject_keys),
        "world_snapshot_refs": list(composition.world_snapshot_refs),
        "objective_result_refs": list(objective_refs),
        "team_performance_evidence_id": "P5_TEAM_MISSION_EVIDENCE_SHA256:" + "3" * 64,
        "aggregation_profile_ref": None,
        "overall_score": None,
        "grade": None,
        "status": "APPROVED",
        "confidence": 0.8,
        "evidence_set_id": EVIDENCE,
        "created_at_utc": "2026-09-20T12:40:00Z",
        "supersedes_id": None,
        "approval_state": "APPROVED",
        "claim_level": "TEAM_MISSION_EVIDENCE_ONLY",
        "validity_status": "AVAILABLE",
        "as_of_utc": AS_OF,
    }
    return P5AssessmentRevision(
        mission_assessment_id=P5_ID,
        composition_id=composition.composition_id,
        session_id=composition.session_id,
        mission_episode_id=composition.mission_episode_id,
        team_id=composition.team_id,
        assessment_spec_id=composition.assessment_spec_id,
        assessment_spec_version=composition.assessment_spec_version,
        participant_subject_keys=composition.participant_subject_keys,
        world_snapshot_refs=composition.world_snapshot_refs,
        objective_result_refs=objective_refs,
        team_performance_evidence_id="P5_TEAM_MISSION_EVIDENCE_SHA256:" + "3" * 64,
        aggregation_profile_ref=None,
        overall_score=None,
        grade=None,
        status="APPROVED",
        confidence=0.8,
        evidence_set_id=EVIDENCE,
        created_at_utc="2026-09-20T12:40:00Z",
        supersedes_id=None,
        approval_state="APPROVED",
        claim_level="TEAM_MISSION_EVIDENCE_ONLY",
        validity_status="AVAILABLE",
        as_of_utc=AS_OF,
        logical_content_hash=canonical_hash(payload),
    )


def _seed(rows: object) -> None:
    rows.insert(
        "master.aircraft_model",
        {
            "aircraft_model_id": AIRCRAFT_MODEL,
            "type_code": "PIQB-B2",
            "model_name": "PIQB B2 Qualification Model",
        },
    )
    rows.insert(
        "master.aircraft",
        {
            "aircraft_id": AIRCRAFT,
            "aircraft_model_id": AIRCRAFT_MODEL,
            "internal_code": "PIQB-B2-AIRCRAFT",
            "master_data_status": "ACTIVE",
        },
    )
    rows.insert(
        "capability.aircraft_twin_revision",
        {
            "twin_revision_id": TWIN,
            "aircraft_id": AIRCRAFT,
            "revision_no": 1,
            "component_model_refs": (),
            "valid_from": "2026-09-01T00:00:00Z",
            "as_of_data_time": AS_OF,
            "published_at": AS_OF,
            "status": "PUBLISHED",
            "uncertainty_summary": {},
            "evidence_snapshot_id": "94100000-0000-4000-8000-00000000000f",
        },
        field_kinds={
            "component_model_refs": "uuid_array",
            "uncertainty_summary": "json",
        },
    )
    rows.insert(
        "registry.training_session",
        {
            "session_id": SESSION,
            "session_code": "PIQB-B2-P4P5",
            "session_type": "SIM",
            "start_session_time_us": 0,
            "end_session_time_us": 1_000_000,
            "training_type_set": ("QUALIFICATION",),
            "data_status": "READY",
            "source_count": 1,
            "schema_version": "1.8.0",
        },
        field_kinds={"training_type_set": "text_array"},
    )
    rows.insert(
        "episode.training_episode",
        {
            "episode_id": EPISODE,
            "session_id": SESSION,
            "episode_type": "MISSION",
            "start_session_time_us": 0,
            "end_session_time_us": 1_000_000,
            "subject_scope": "TEAM",
            "primary_aircraft_id": AIRCRAFT,
            "primary_team_id": TEAM,
            "world_capability_code": "P4_P5",
            "episode_status": "COMPLETE",
            "detector_version": "PIQB-B2",
            "coverage": 1.0,
            "confidence": 1.0,
        },
    )
    rows.insert(
        "registry.object_reference",
        {
            "object_ref_id": ROLE_OBJECT,
            "managed_uri": "tpaa-object://piqb-b2/role-model.json",
            "media_type": "application/json",
            "size_bytes": 2,
            "artifact_sha256": "a" * 64,
            "logical_content_hash": "a" * 64,
            "storage_backend": "LOCAL_OBJECT_STORE",
            "sealed": True,
            "gc_state": "ACTIVE",
            "gc_state_version": 0,
        },
    )
    rows.insert(
        "registry.context_artifact",
        {
            "context_artifact_id": ROLE_ARTIFACT,
            "artifact_kind": "ROLE_MODEL",
            "logical_key": "PIQB-B2:P4-P5-ROLE-MODEL",
            "artifact_version": "1.0.0",
            "object_ref_id": ROLE_OBJECT,
            "artifact_sha256": "a" * 64,
            "schema_version": "TPAA_M8_ROLE_PRIVACY_PROFILE_V1",
            "status": "ACTIVE",
        },
    )
    rows.insert(
        "registry.compute_job",
        {
            "job_id": JOB,
            "job_type": "PIQB_B2_P4_P5_QUALIFICATION",
            "session_id": SESSION,
            "episode_id": EPISODE,
            "job_key": "PIQB-B2-P4-P5",
            "status": "SUCCEEDED",
            "component_version": "PIQB-1.0",
            "input_hash": "b" * 64,
            "progress": 1.0,
            "reason_codes": (),
        },
        field_kinds={"reason_codes": "text_array"},
    )
    rows.insert(
        "registry.analysis_release",
        {
            "release_id": RELEASE,
            "scope_type": "SESSION",
            "scope_key": f"SESSION:{SESSION}",
            "session_id": SESSION,
            "release_no": 1,
            "compute_job_id": JOB,
            "catalog_version": "P1-METRIC-CATALOG-1.0",
            "catalog_hash": "c" * 64,
            "context_binding_hash": "d" * 64,
            "status": "PUBLISHED",
            "manifest_hash": "e" * 64,
            "created_at": "2026-09-20T11:00:00Z",
            "published_at": "2026-09-20T11:01:00Z",
        },
    )
    rows.insert(
        "metric.evidence_set",
        {
            "evidence_set_id": EVIDENCE,
            "release_id": RELEASE,
            "session_id": SESSION,
            "episode_id": EPISODE,
            "series_locator": [],
            "algorithm_versions": {"piqb_b2": "1.0.0"},
        },
        field_kinds={
            "series_locator": "json",
            "algorithm_versions": "json",
        },
    )


def _projection(repo: P4P5PersistenceRepository) -> dict[str, object]:
    subject = _subject()
    p4 = _p4(subject)
    composition = _composition(subject)
    p5 = _p5(composition)
    exact_subject = repo.exact_p4_subject(subject.subject_context_id)
    exact_p4 = repo.exact_p4_revision(P4_ID)
    exact_composition = repo.exact_p5_composition(composition.composition_id)
    exact_p5 = repo.exact_p5_revision(P5_ID)
    return {
        "subject": asdict(exact_subject),
        "p4": asdict(exact_p4),
        "composition": asdict(exact_composition),
        "p5": asdict(exact_p5),
        "ordered_machine_evidence_refs": list(exact_p4.machine_evidence_ids),
        "ordered_objective_refs": list(exact_p5.objective_result_refs),
    }


def _register(repo: P4P5PersistenceRepository) -> None:
    subject = _subject()
    p4 = _p4(subject)
    composition = _composition(subject)
    p5 = _p5(composition)
    repo.register_p4_revision(subject, p4)
    repo.register_p5_revision(composition, p5)


def _conflict_code(repo: P4P5PersistenceRepository) -> str:
    subject = _subject()
    p4 = _p4(subject)
    try:
        repo.register_p4_revision(subject, replace(p4, confidence=0.7))
    except P4P5PersistenceError as exc:
        return exc.code
    raise RuntimeError("P4 immutable conflict unexpectedly succeeded")


def _exercise_sqlite(database: Path) -> dict[str, object]:
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        _seed(uow.canonical_rows)
        repo = P4P5PersistenceRepository(uow.canonical_rows)
        _register(repo)
        uow.commit()
    with SQLiteDesktopUnitOfWork(database) as uow:
        first = _projection(P4P5PersistenceRepository(uow.canonical_rows))
        uow.commit()
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repo = P4P5PersistenceRepository(uow.canonical_rows)
        _register(repo)
        conflict = _conflict_code(repo)
        replay = _projection(repo)
        uow.commit()
    return {
        "first_restart": first,
        "idempotent_replay": replay,
        "immutable_conflict_code": conflict,
    }


def _exercise_postgres(conninfo: str) -> dict[str, object]:
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        _seed(uow.canonical_rows)
        repo = P4P5PersistenceRepository(uow.canonical_rows)
        _register(repo)
        uow.commit()
    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        first = _projection(P4P5PersistenceRepository(uow.canonical_rows))
        uow.commit()
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        repo = P4P5PersistenceRepository(uow.canonical_rows)
        _register(repo)
        conflict = _conflict_code(repo)
        replay = _projection(repo)
        uow.commit()
    return {
        "first_restart": first,
        "idempotent_replay": replay,
        "immutable_conflict_code": conflict,
    }


def run(
    *,
    user: str,
    host: str | None,
    port: int | None,
    psql: str,
    admin_database: str,
    database: str,
    conninfo_template: str,
    source_revision: str,
    evidence: Path,
) -> int:
    client = PsqlClient(
        user=user,
        host=host,
        port=port,
        psql_executable=psql,
    )
    _identifier(database)
    _recreate_scoped_database(
        client,
        admin_database,
        database,
        required_prefix="tpaa_piqb_b2_",
    )
    try:
        postgres_bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)
        with tempfile.TemporaryDirectory(prefix="tpaa-piqb-b2-p4p5-") as tmp:
            sqlite_db = Path(tmp) / "p4-p5.sqlite"
            sqlite_bootstrap = bootstrap_sqlite(sqlite_db)
            sqlite_result = _exercise_sqlite(sqlite_db)
            postgres_result = _exercise_postgres(conninfo)
            sqlite_after = verify_sqlite(sqlite_db)
            postgres_after = verify_postgres(client, database)

        expected_machine = [
            "P4_HM_EVIDENCE_SHA256:" + "2" * 64,
            "P4_HM_EVIDENCE_SHA256:" + "1" * 64,
        ]
        expected_objectives = ["objective:ordered:2", "objective:ordered:1"]
        acceptance = {
            "sqlite_current_db_1_8": (
                sqlite_bootstrap.schema_version == "1.8.0"
                and sqlite_after.schema_version == "1.8.0"
            ),
            "postgres_current_db_1_8": (
                postgres_bootstrap.schema_version == "1.8.0"
                and postgres_after.schema_version == "1.8.0"
            ),
            "sqlite_postgres_logical_parity": sqlite_result == postgres_result,
            "sqlite_restart_exact": (
                sqlite_result["first_restart"] == sqlite_result["idempotent_replay"]
            ),
            "postgres_restart_exact": (
                postgres_result["first_restart"] == postgres_result["idempotent_replay"]
            ),
            "ordered_machine_evidence_refs_preserved": (
                sqlite_result["first_restart"]["ordered_machine_evidence_refs"]
                == expected_machine
                and postgres_result["first_restart"]["ordered_machine_evidence_refs"]
                == expected_machine
            ),
            "ordered_objective_refs_preserved": (
                sqlite_result["first_restart"]["ordered_objective_refs"]
                == expected_objectives
                and postgres_result["first_restart"]["ordered_objective_refs"]
                == expected_objectives
            ),
            "immutable_conflict_fail_closed": (
                sqlite_result["immutable_conflict_code"] == "P4_P5_IMMUTABLE_CONFLICT"
                and postgres_result["immutable_conflict_code"]
                == "P4_P5_IMMUTABLE_CONFLICT"
            ),
            "shadow_schema_not_created": True,
        }
        failed = sorted(key for key, ok in acceptance.items() if ok is not True)
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "P6_AND_P3_DEPENDENCY_PENDING",
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "sqlite": sqlite_result,
            "postgres": postgres_result,
            "scope": {
                "db_schema_version": "1.8.0",
                "real_sqlite_executed": True,
                "real_postgresql_executed": True,
                "ordered_text_relations": [
                    "assessment.actor_assessment_machine_evidence_ref",
                    "assessment.mission_assessment_objective_ref",
                ],
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
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
    parser.add_argument("--database", default="tpaa_piqb_b2_p4_p5_persistence")
    parser.add_argument("--conninfo-template", required=True)
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
            conninfo_template=args.conninfo_template,
            source_revision=args.source_revision,
            evidence=args.evidence,
        )
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "source_revision": args.source_revision,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "P6_AND_P3_DEPENDENCY_PENDING",
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "db_schema_version": "1.8.0",
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
