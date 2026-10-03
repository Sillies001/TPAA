from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_application.p4_p5_persistence import (
    P4P5PersistenceError,
    P4P5PersistenceRepository,
)
from tpaa_assessment import (
    InstructorAnnotationRevision,
    P4AssessmentRevision,
    P4SubjectContext,
    P5AssessmentRevision,
)
from tpaa_context import canonical_hash, pseudonymous_subject_key
from tpaa_storage.canonical_rows import SQLiteCanonicalRowRepository
from tpaa_world import P5CompositionSnapshot, P5ParticipantBinding

ACTOR = "11111111-1111-4111-8111-111111111111"
AUTHOR = "12121212-1212-4121-8121-121212121212"
SESSION = "22222222-2222-4222-8222-222222222222"
EPISODE = "33333333-3333-4333-8333-333333333333"
STAGE = "44444444-4444-4444-8444-444444444444"
AIRCRAFT = "55555555-5555-4555-8555-555555555555"
TWIN = "66666666-6666-4666-8666-666666666666"
ESTIMATE = "77777777-7777-4777-8777-777777777777"
EVIDENCE = "88888888-8888-4888-8888-888888888888"
ROLE_ARTIFACT = "99999999-9999-4999-8999-999999999999"
RELEASE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
P4_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ANNOTATION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
TEAM = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
SCENARIO = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
P5_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"


def _schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE "assessment.p4_subject_context" (
            subject_context_id TEXT PRIMARY KEY,
            subject_key TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            role_code TEXT NOT NULL,
            seat_code TEXT NULL,
            function_code TEXT NULL,
            session_id TEXT NOT NULL,
            episode_id TEXT NOT NULL,
            stage_id TEXT NULL,
            aircraft_id TEXT NULL,
            twin_revision_id TEXT NOT NULL,
            p3_estimate_id TEXT NULL,
            assessment_spec_id TEXT NOT NULL,
            assessment_spec_version TEXT NOT NULL,
            role_model_context_artifact_id TEXT NOT NULL,
            role_model_version TEXT NOT NULL,
            world_refs TEXT NOT NULL,
            evidence_set_id TEXT NOT NULL,
            as_of_utc TEXT NOT NULL,
            knowledge_time_utc TEXT NOT NULL
        );
        CREATE TABLE "debrief.annotation" (
            annotation_id TEXT PRIMARY KEY,
            base_release_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            episode_id TEXT NULL,
            stage_id TEXT NULL,
            author_id TEXT NOT NULL,
            annotation_type TEXT NOT NULL,
            start_session_time_us INTEGER NULL,
            end_session_time_us INTEGER NULL,
            body_text TEXT NOT NULL,
            visibility TEXT NOT NULL,
            status TEXT NOT NULL,
            revision_no INTEGER NOT NULL,
            supersedes_annotation_id TEXT NULL,
            evidence_set_id TEXT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE "assessment.actor_assessment" (
            actor_assessment_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            episode_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            aircraft_id TEXT NULL,
            assessment_spec_id TEXT NOT NULL,
            assessment_spec_version TEXT NOT NULL,
            world_refs TEXT NOT NULL,
            metric_refs TEXT NOT NULL,
            capability_projection_refs TEXT NOT NULL,
            score REAL NULL,
            grade TEXT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            evidence_set_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            supersedes_id TEXT NULL
        );
        CREATE TABLE "assessment.actor_assessment_revision" (
            actor_assessment_id TEXT PRIMARY KEY,
            subject_context_id TEXT NOT NULL,
            approval_state TEXT NOT NULL,
            p3_claim_level TEXT NOT NULL,
            p3_validity_status TEXT NOT NULL,
            p3_as_of_utc TEXT NOT NULL,
            uncertainty_lower REAL NULL,
            uncertainty_upper REAL NULL,
            logical_content_hash TEXT NOT NULL
        );
        CREATE TABLE "assessment.actor_assessment_machine_evidence_ref" (
            actor_assessment_id TEXT NOT NULL,
            ref_order INTEGER NOT NULL,
            evidence_ref TEXT NOT NULL,
            PRIMARY KEY (actor_assessment_id, ref_order)
        );
        CREATE TABLE "assessment.actor_assessment_annotation_ref" (
            actor_assessment_id TEXT NOT NULL,
            ref_order INTEGER NOT NULL,
            annotation_id TEXT NOT NULL,
            PRIMARY KEY (actor_assessment_id, ref_order)
        );
        CREATE TABLE "assessment.p5_composition_snapshot" (
            composition_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            mission_episode_id TEXT NOT NULL,
            team_id TEXT NULL,
            world_snapshot_refs TEXT NOT NULL,
            scenario_context_artifact_id TEXT NULL,
            role_model_context_artifact_id TEXT NOT NULL,
            assessment_spec_id TEXT NOT NULL,
            assessment_spec_version TEXT NOT NULL,
            as_of_utc TEXT NOT NULL,
            composition_hash TEXT NOT NULL
        );
        CREATE TABLE "assessment.p5_composition_participant" (
            composition_id TEXT NOT NULL,
            ref_order INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            role_code TEXT NOT NULL,
            aircraft_id TEXT NULL,
            twin_revision_id TEXT NULL,
            p4_revision_id TEXT NOT NULL,
            PRIMARY KEY (composition_id, ref_order)
        );
        CREATE TABLE "assessment.mission_assessment" (
            mission_assessment_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            mission_episode_id TEXT NOT NULL,
            team_id TEXT NULL,
            assessment_spec_id TEXT NOT NULL,
            assessment_spec_version TEXT NOT NULL,
            participant_ids TEXT NOT NULL,
            world_snapshot_refs TEXT NOT NULL,
            adjudication_refs TEXT NOT NULL,
            overall_score REAL NULL,
            grade TEXT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            evidence_set_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            supersedes_id TEXT NULL
        );
        CREATE TABLE "assessment.mission_assessment_revision" (
            mission_assessment_id TEXT PRIMARY KEY,
            composition_id TEXT NOT NULL,
            team_performance_evidence_id TEXT NOT NULL,
            approval_state TEXT NOT NULL,
            claim_level TEXT NOT NULL,
            validity_status TEXT NOT NULL,
            as_of_utc TEXT NOT NULL,
            logical_content_hash TEXT NOT NULL
        );
        CREATE TABLE "assessment.mission_assessment_objective_ref" (
            mission_assessment_id TEXT NOT NULL,
            ref_order INTEGER NOT NULL,
            objective_ref TEXT NOT NULL,
            PRIMARY KEY (mission_assessment_id, ref_order)
        );
        """
    )


def _subject() -> P4SubjectContext:
    subject_key = pseudonymous_subject_key(ACTOR)
    identity = {
        "subject_key": subject_key,
        "role_code": "SUBJECT_SELF",
        "seat_code": "FRONT",
        "function_code": "PILOT",
        "session_id": SESSION,
        "episode_id": EPISODE,
        "stage_id": STAGE,
        "aircraft_id": AIRCRAFT,
        "twin_revision_id": TWIN,
        "p3_estimate_id": ESTIMATE,
        "assessment_spec_id": "P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        "assessment_spec_version": "1.0.0",
        "role_model_context_artifact_id": ROLE_ARTIFACT,
        "as_of_utc": "2026-09-20T12:00:00Z",
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
        stage_id=STAGE,
        aircraft_id=AIRCRAFT,
        twin_revision_id=TWIN,
        p3_estimate_id=ESTIMATE,
        assessment_spec_id="P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        role_model_context_artifact_id=ROLE_ARTIFACT,
        role_model_version="1.0.0",
        world_refs=("world:action:1", "world:perceived:1"),
        evidence_set_id=EVIDENCE,
        as_of_utc="2026-09-20T12:00:00Z",
        knowledge_time_utc="2026-09-20T11:59:59Z",
    )


def _annotation(subject: P4SubjectContext) -> InstructorAnnotationRevision:
    author_subject_key = pseudonymous_subject_key(AUTHOR)
    payload = {
        "base_release_id": RELEASE,
        "session_id": SESSION,
        "episode_id": EPISODE,
        "stage_id": STAGE,
        "author_subject_key": author_subject_key,
        "author_id": AUTHOR,
        "annotation_type": "INSTRUCTOR_NOTE",
        "start_session_time_us": 100,
        "end_session_time_us": 200,
        "body_text": "Exact instructor note.",
        "visibility": "EVALUATOR",
        "status": "ACTIVE",
        "revision_no": 1,
        "supersedes_annotation_id": None,
        "evidence_set_id": EVIDENCE,
        "subject_context_id": subject.subject_context_id,
        "created_at_utc": "2026-09-20T12:20:00Z",
    }
    return InstructorAnnotationRevision(
        annotation_id=ANNOTATION_ID,
        base_release_id=RELEASE,
        session_id=SESSION,
        episode_id=EPISODE,
        stage_id=STAGE,
        author_subject_key=author_subject_key,
        author_id=AUTHOR,
        annotation_type="INSTRUCTOR_NOTE",
        start_session_time_us=100,
        end_session_time_us=200,
        body_text="Exact instructor note.",
        visibility="EVALUATOR",
        status="ACTIVE",
        revision_no=1,
        supersedes_annotation_id=None,
        evidence_set_id=EVIDENCE,
        subject_context_id=subject.subject_context_id,
        created_at_utc="2026-09-20T12:20:00Z",
        content_hash=canonical_hash(payload),
    )


def _p4(
    subject: P4SubjectContext,
    annotation: InstructorAnnotationRevision,
) -> P4AssessmentRevision:
    values: dict[str, object] = {
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
        "machine_evidence_ids": ["machine:ordered:2", "machine:ordered:1"],
        "instructor_annotation_ids": [annotation.annotation_id],
        "score": None,
        "grade": None,
        "status": "APPROVED",
        "confidence": 0.9,
        "evidence_set_id": subject.evidence_set_id,
        "created_at_utc": "2026-09-20T12:30:00Z",
        "supersedes_id": None,
        "approval_state": "APPROVED",
        "p3_claim_level": "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        "p3_validity_status": "VALID",
        "p3_as_of_utc": subject.as_of_utc,
        "uncertainty_lower": 39.0,
        "uncertainty_upper": 41.0,
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
        p3_estimate_id=subject.p3_estimate_id,
        assessment_spec_id=subject.assessment_spec_id,
        assessment_spec_version=subject.assessment_spec_version,
        role_model_version=subject.role_model_version,
        world_refs=subject.world_refs,
        machine_evidence_ids=("machine:ordered:2", "machine:ordered:1"),
        instructor_annotation_ids=(annotation.annotation_id,),
        score=None,
        grade=None,
        status="APPROVED",
        confidence=0.9,
        evidence_set_id=subject.evidence_set_id,
        created_at_utc="2026-09-20T12:30:00Z",
        supersedes_id=None,
        approval_state="APPROVED",
        p3_claim_level="REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        p3_validity_status="VALID",
        p3_as_of_utc=subject.as_of_utc,
        uncertainty_lower=39.0,
        uncertainty_upper=41.0,
        logical_content_hash=canonical_hash(values),
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
        "world_snapshot_refs": ["world:mission:1"],
        "scenario_context_artifact_id": SCENARIO,
        "role_model_context_artifact_id": ROLE_ARTIFACT,
        "assessment_spec_id": "P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        "assessment_spec_version": "1.0.0",
        "as_of_utc": "2026-09-20T12:00:00Z",
    }
    digest = canonical_hash(identity)
    return P5CompositionSnapshot(
        composition_id=f"P5_COMPOSITION_SHA256:{digest}",
        session_id=SESSION,
        mission_episode_id=EPISODE,
        team_id=TEAM,
        participant_subject_keys=(subject.subject_key,),
        participant_bindings=(participant,),
        world_snapshot_refs=("world:mission:1",),
        scenario_context_artifact_id=SCENARIO,
        role_model_context_artifact_id=ROLE_ARTIFACT,
        assessment_spec_id="P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        as_of_utc="2026-09-20T12:00:00Z",
        composition_hash=digest,
    )


def _p5(composition: P5CompositionSnapshot) -> P5AssessmentRevision:
    values: dict[str, object] = {
        "composition_id": composition.composition_id,
        "session_id": composition.session_id,
        "mission_episode_id": composition.mission_episode_id,
        "team_id": composition.team_id,
        "assessment_spec_id": composition.assessment_spec_id,
        "assessment_spec_version": composition.assessment_spec_version,
        "participant_subject_keys": list(composition.participant_subject_keys),
        "world_snapshot_refs": list(composition.world_snapshot_refs),
        "objective_result_refs": ["objective:CAP:2", "objective:CAP:1"],
        "team_performance_evidence_id": "P5_TEAM_MISSION_EVIDENCE_SHA256:" + "1" * 64,
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
        "as_of_utc": composition.as_of_utc,
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
        objective_result_refs=("objective:CAP:2", "objective:CAP:1"),
        team_performance_evidence_id="P5_TEAM_MISSION_EVIDENCE_SHA256:" + "1" * 64,
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
        as_of_utc=composition.as_of_utc,
        logical_content_hash=canonical_hash(values),
    )


def _repository(connection: sqlite3.Connection) -> P4P5PersistenceRepository:
    return P4P5PersistenceRepository(SQLiteCanonicalRowRepository(connection))


def test_db_1_8_p4_p5_exact_restart_round_trip(tmp_path: Path) -> None:
    database = tmp_path / "p4-p5.sqlite"
    connection = sqlite3.connect(database)
    _schema(connection)
    subject = _subject()
    annotation = _annotation(subject)
    p4 = _p4(subject, annotation)
    composition = _composition(subject)
    p5 = _p5(composition)

    repository = _repository(connection)
    repository.register_p4_revision(subject, p4, annotations=(annotation,))
    repository.register_p5_revision(composition, p5)
    connection.commit()
    connection.close()

    reopened = sqlite3.connect(database)
    restarted = _repository(reopened)
    assert restarted.exact_p4_subject(subject.subject_context_id) == subject
    assert restarted.exact_p4_revision(p4.actor_assessment_id) == p4
    assert restarted.exact_p4_annotation(
        p4.actor_assessment_id,
        annotation.annotation_id,
    ) == annotation
    assert restarted.exact_p5_composition(composition.composition_id) == composition
    assert restarted.exact_p5_revision(p5.mission_assessment_id) == p5
    reopened.close()


def test_db_1_8_ordered_text_refs_and_immutable_replay(tmp_path: Path) -> None:
    database = tmp_path / "ordered.sqlite"
    connection = sqlite3.connect(database)
    _schema(connection)
    subject = _subject()
    annotation = _annotation(subject)
    p4 = _p4(subject, annotation)
    composition = _composition(subject)
    p5 = _p5(composition)
    repository = _repository(connection)

    repository.register_p4_revision(subject, p4, annotations=(annotation,))
    repository.register_p5_revision(composition, p5)
    repository.register_p4_revision(subject, p4, annotations=(annotation,))
    repository.register_p5_revision(composition, p5)

    assert repository.exact_p4_revision(P4_ID).machine_evidence_ids == (
        "machine:ordered:2",
        "machine:ordered:1",
    )
    assert repository.exact_p5_revision(P5_ID).objective_result_refs == (
        "objective:CAP:2",
        "objective:CAP:1",
    )

    with pytest.raises(P4P5PersistenceError, match="P4_P5_IMMUTABLE_CONFLICT"):
        repository.register_p4_revision(
            subject,
            replace(p4, confidence=0.7),
            annotations=(annotation,),
        )
    with pytest.raises(P4P5PersistenceError, match="P4_P5_IMMUTABLE_CONFLICT"):
        repository.register_p5_revision(
            composition,
            replace(p5, confidence=0.7),
        )
    connection.close()
