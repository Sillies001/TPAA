from __future__ import annotations

from dataclasses import replace
from typing import Mapping

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from tpaa_api import create_m8_app
from tpaa_application import (
    ApplicationService,
    InMemoryM8AssessmentRepository,
    M8AircraftContextPort,
    M8ApplicationError,
    M8P4Query,
    M8ViewerContext,
    M8WorkspaceQuery,
    M8WorkspaceService,
)
from tpaa_assessment import (
    P4AssessmentRevision,
    P5ApprovalCommand,
    P5ApprovalWorkflow,
    build_p5_aggregation,
    build_p5_assessment_revision,
    materialize_p5_team_mission_evidence,
)
from tpaa_context import M8AdmissionEvidence, M8AuthorityPolicy, M8GovernanceError
from tpaa_gui import build_m8_layered_workspace_model
from tpaa_longitudinal import build_p5_longitudinal_replay
from tpaa_world import P5CompositionSnapshot, P5ParticipantBinding

ACTOR = "11111111-1111-4111-8111-111111111111"
REVIEWER = "12121212-1212-4121-8121-121212121212"
SESSION = "22222222-2222-4222-8222-222222222222"
EPISODE = "33333333-3333-4333-8333-333333333333"
AIRCRAFT = "44444444-4444-4444-8444-444444444444"
TWIN = "55555555-5555-4555-8555-555555555555"
ESTIMATE = "66666666-6666-4666-8666-666666666666"
EVIDENCE = "77777777-7777-4777-8777-777777777777"
P4_ID = "88888888-8888-4888-8888-888888888888"
TEAM = "99999999-9999-4999-8999-999999999999"
ROLE_ARTIFACT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SCENARIO = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class _Storage:
    def execute(self):
        from tpaa_application import StorageBaselineStatus

        return StorageBaselineStatus(
            core_baseline="CB-1.4.0",
            db_schema_version="1.6.0",
            migration_head="0016",
            engine="sqlite",
        )


class _AircraftContext(M8AircraftContextPort):
    def exact_context(
        self,
        *,
        twin_revision_id: str,
        estimate_id: str,
    ) -> dict[str, object]:
        assert twin_revision_id == TWIN
        assert estimate_id == ESTIMATE
        return {
            "identity": {
                "twin_revision_id": twin_revision_id,
                "estimate_id": estimate_id,
            },
            "observed": {
                "layer": "P1_OBSERVED",
                "release_id": "p1-release",
                "logical_hash": "1" * 64,
                "projection": {},
            },
            "adjusted": {
                "layer": "P2_ADJUSTED",
                "release_id": "p2-release",
                "logical_hash": "2" * 64,
                "projection": {},
            },
            "p3": {
                "layer": "P3_REFERENCE_CONDITION_LONGITUDINAL",
                "twin": {"twin_revision_id": twin_revision_id},
                "estimate": {"estimate_id": estimate_id},
            },
            "logical_product_hash": "3" * 64,
        }


def _subject_key(policy: M8AuthorityPolicy) -> str:
    from tpaa_context import pseudonymous_subject_key

    return pseudonymous_subject_key(ACTOR, policy=policy)


def _p4(policy: M8AuthorityPolicy) -> P4AssessmentRevision:
    return P4AssessmentRevision(
        actor_assessment_id=P4_ID,
        subject_context_id="P4_SUBJECT_CONTEXT_SHA256:" + "a" * 64,
        subject_key=_subject_key(policy),
        actor_id=ACTOR,
        role_code="SUBJECT_SELF",
        seat_code="FRONT",
        function_code="PILOT",
        session_id=SESSION,
        episode_id=EPISODE,
        aircraft_id=AIRCRAFT,
        twin_revision_id=TWIN,
        p3_estimate_id=ESTIMATE,
        assessment_spec_id="P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        role_model_version="1.0.0",
        world_refs=("world:action:1",),
        machine_evidence_ids=("P4_HM_EVIDENCE_SHA256:" + "c" * 64,),
        instructor_annotation_ids=(),
        score=None,
        grade=None,
        status="APPROVED",
        confidence=0.9,
        evidence_set_id=EVIDENCE,
        created_at_utc="2026-09-20T11:50:00Z",
        supersedes_id=None,
        approval_state="APPROVED",
        p3_claim_level="REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        p3_validity_status="VALID",
        p3_as_of_utc="2026-09-20T12:00:00Z",
        uncertainty_lower=39.0,
        uncertainty_upper=41.0,
        logical_content_hash="d" * 64,
    )


def _composition(policy: M8AuthorityPolicy) -> P5CompositionSnapshot:
    subject_key = _subject_key(policy)
    payload = {
        "session_id": SESSION,
        "mission_episode_id": EPISODE,
        "team_id": TEAM,
        "participant_bindings": [
            {
                "subject_key": subject_key,
                "role_code": "FLIGHT_LEAD",
                "aircraft_id": AIRCRAFT,
                "twin_revision_id": TWIN,
                "p4_revision_id": P4_ID,
            }
        ],
        "world_snapshot_refs": ["world:mission:1"],
        "scenario_context_artifact_id": SCENARIO,
        "role_model_context_artifact_id": ROLE_ARTIFACT,
        "assessment_spec_id": "P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        "assessment_spec_version": "1.0.0",
        "as_of_utc": "2026-09-20T12:00:00Z",
    }
    from tpaa_context import canonical_hash

    digest = canonical_hash(payload)
    return P5CompositionSnapshot(
        composition_id=f"P5_COMPOSITION_SHA256:{digest}",
        session_id=SESSION,
        mission_episode_id=EPISODE,
        team_id=TEAM,
        participant_subject_keys=(subject_key,),
        participant_bindings=(
            P5ParticipantBinding(
                subject_key=subject_key,
                role_code="FLIGHT_LEAD",
                aircraft_id=AIRCRAFT,
                twin_revision_id=TWIN,
                p4_revision_id=P4_ID,
            ),
        ),
        world_snapshot_refs=("world:mission:1",),
        scenario_context_artifact_id=SCENARIO,
        role_model_context_artifact_id=ROLE_ARTIFACT,
        assessment_spec_id="P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        as_of_utc="2026-09-20T12:00:00Z",
        composition_hash=digest,
    )


def _p5(policy: M8AuthorityPolicy):
    p4 = _p4(policy)
    composition = _composition(policy)
    evidence = materialize_p5_team_mission_evidence(
        composition,
        p4_revisions=(p4,),
        evidence_set_id=EVIDENCE,
        objective_result_refs=("objective:CAP:1",),
        as_of_utc=composition.as_of_utc,
        policy=policy,
    )
    aggregation = build_p5_aggregation(evidence, policy=policy)
    revision = build_p5_assessment_revision(
        composition,
        evidence=evidence,
        aggregation=aggregation,
        confidence=0.8,
        created_at_utc="2026-09-20T12:10:00Z",
        policy=policy,
    )
    return composition, evidence, aggregation, revision


def _admission() -> M8AdmissionEvidence:
    return M8AdmissionEvidence(
        source_revision="1" * 40,
        event_name="push",
        git_ref="refs/heads/main",
        protected_main=True,
        m8_exit_decision="GO",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
        p4_admitted=True,
        p5_admitted=True,
        p6_inactive=True,
    )


def _viewer(
    role: str,
    *,
    actor_id: str | None = None,
    export: bool = False,
    privileged: bool = False,
) -> M8ViewerContext:
    return M8ViewerContext(
        viewer_role=role,
        viewer_actor_id=actor_id,
        scope_match=True,
        privileged_identity_authorized=privileged,
        visibility_authorized=True,
        export_authorized=export,
    )


def _service(policy: M8AuthorityPolicy) -> tuple[M8WorkspaceService, object]:
    p4 = _p4(policy)
    _, _, _, p5 = _p5(policy)
    repository = InMemoryM8AssessmentRepository()
    repository.register_p4(p4)
    repository.register_p5(p5)
    service = M8WorkspaceService(
        repository,
        admission_evidence=_admission(),
        aircraft_context=_AircraftContext(),
        policy=policy,
    )
    return service, p5


def test_m8_batch3_p5_evidence_and_no_profile_aggregation(
    policy: M8AuthorityPolicy = M8AuthorityPolicy.from_canonical(),
) -> None:
    composition, evidence, aggregation, revision = _p5(policy)
    assert evidence.composition_id == composition.composition_id
    assert evidence.member_evidence[0].p4_revision_id == P4_ID
    assert evidence.availability_status == "AVAILABLE"
    assert aggregation.overall_score is None
    assert aggregation.grade is None
    assert revision.overall_score is None
    assert revision.grade is None
    assert revision.claim_level == "TEAM_MISSION_EVIDENCE_ONLY"

    with pytest.raises(M8GovernanceError) as unauthorized:
        build_p5_aggregation(
            evidence,
            aggregation_profile_ref="convenience-average",
            proposed_score=1.0,
            policy=policy,
        )
    assert (
        unauthorized.value.code
        == "FAIL_CLOSED_P4_P5_AGGREGATION_PROFILE_REQUIRED"
    )


def test_m8_batch3_missing_member_is_explicit(
    policy: M8AuthorityPolicy = M8AuthorityPolicy.from_canonical(),
) -> None:
    composition = _composition(policy)
    evidence = materialize_p5_team_mission_evidence(
        composition,
        p4_revisions=(),
        evidence_set_id=EVIDENCE,
        objective_result_refs=("objective:CAP:1",),
        as_of_utc=composition.as_of_utc,
        policy=policy,
    )
    assert evidence.availability_status == "UNAVAILABLE"
    assert evidence.member_evidence[0].availability_status == "UNAVAILABLE"
    assert evidence.member_evidence[0].reason_codes == ("MISSING_P4_REVISION",)
    assert evidence.reason_codes == (
        f"MISSING_MEMBER:{composition.participant_subject_keys[0]}",
    )


def test_m8_batch3_p5_replay_separates_changed_composition(
    policy: M8AuthorityPolicy = M8AuthorityPolicy.from_canonical(),
) -> None:
    composition, evidence, aggregation, first = _p5(policy)
    workflow = P5ApprovalWorkflow(policy)
    review = workflow.transition(
        first,
        P5ApprovalCommand(
            request_id="p5-review",
            reviewer_actor_id=REVIEWER,
            viewer_role="INSTRUCTOR_EVALUATOR",
            scope_match=True,
            target_state="IN_REVIEW",
            reason="review",
            created_at_utc="2026-09-20T12:20:00Z",
        ),
    ).revision
    changed = replace(
        composition,
        composition_id="P5_COMPOSITION_SHA256:" + "e" * 64,
        composition_hash="e" * 64,
        world_snapshot_refs=("world:mission:2",),
    )
    changed_evidence = replace(
        evidence,
        evidence_id="P5_TEAM_MISSION_EVIDENCE_SHA256:" + "f" * 64,
        composition_id=changed.composition_id,
        world_snapshot_refs=changed.world_snapshot_refs,
        evidence_hash="f" * 64,
    )
    changed_aggregation = replace(
        aggregation,
        evidence_id=changed_evidence.evidence_id,
        logical_hash="0" * 64,
    )
    second_series = build_p5_assessment_revision(
        changed,
        evidence=changed_evidence,
        aggregation=changed_aggregation,
        confidence=0.8,
        created_at_utc="2026-09-21T12:10:00Z",
        policy=policy,
    )
    replay = build_p5_longitudinal_replay(
        (first, review, second_series),
        replay_as_of_utc="2026-09-22T00:00:00Z",
    )
    assert replay.changed_composition is True
    assert len(replay.composition_series) == 2
    assert replay.composition_series[0].composition_id != (
        replay.composition_series[1].composition_id
    )


def test_m8_batch3_application_role_projection_and_export_denial(
    policy: M8AuthorityPolicy = M8AuthorityPolicy.from_canonical(),
) -> None:
    service, p5 = _service(policy)
    analyst = service.p4(
        M8P4Query(
            P4_ID,
            _viewer("ANALYST"),
        )
    )
    assert analyst["actor_id"] is None
    instructor = service.p4(
        M8P4Query(
            P4_ID,
            _viewer("INSTRUCTOR_EVALUATOR", actor_id=REVIEWER),
        )
    )
    assert instructor["actor_id"] == ACTOR

    with pytest.raises(M8ApplicationError) as denied:
        service.export_exact(
            M8WorkspaceQuery(
                P4_ID,
                p5.mission_assessment_id,
                _viewer("ANALYST"),
            )
        )
    assert "NOT_AUTHORIZED" in denied.value.code
    assert all(
        event.principal_key != ACTOR
        for event in service.security_events()
    )


def test_m8_batch3_api_exact_ids_role_privacy_and_idempotent_write(
    policy: M8AuthorityPolicy = M8AuthorityPolicy.from_canonical(),
) -> None:
    service, p5 = _service(policy)
    application = ApplicationService(
        get_storage_baseline_status=_Storage(),
        m8_workspace=service,
    )

    def resolver(request: Request) -> M8ViewerContext:
        role = request.headers.get("x-tpaa-role", "ANALYST")
        actor = request.headers.get("x-tpaa-actor-id")
        return _viewer(role, actor_id=actor)

    client = TestClient(
        create_m8_app(application, principal_resolver=resolver)
    )
    analyst = client.get(
        f"/m8/p4/assessments/{P4_ID}",
        headers={"x-tpaa-role": "ANALYST"},
    )
    assert analyst.status_code == 200
    assert analyst.json()["actor_id"] is None

    alias = client.get(
        "/m8/p4/assessments/latest",
        headers={"x-tpaa-role": "ANALYST"},
    )
    assert alias.status_code == 422

    body = {
        "request_id": "api-note-1",
        "base_release_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "annotation_type": "INSTRUCTOR_NOTE",
        "start_session_time_us": None,
        "end_session_time_us": None,
        "body_text": "Exact instructor note.",
        "visibility": "EVALUATOR",
        "reason": "training review",
        "created_at_utc": "2026-09-20T12:30:00Z",
    }
    denied = client.post(
        f"/m8/p4/assessments/{P4_ID}/annotations",
        headers={"x-tpaa-role": "ANALYST"},
        json=body,
    )
    assert denied.status_code == 403

    headers = {
        "x-tpaa-role": "INSTRUCTOR_EVALUATOR",
        "x-tpaa-actor-id": REVIEWER,
    }
    first = client.post(
        f"/m8/p4/assessments/{P4_ID}/annotations",
        headers=headers,
        json=body,
    )
    second = client.post(
        f"/m8/p4/assessments/{P4_ID}/annotations",
        headers=headers,
        json=body,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["annotation_id"] == second.json()["annotation_id"]
    assert second.json()["reused"] is True

    p5_read = client.get(
        f"/m8/p5/assessments/{p5.mission_assessment_id}",
        headers={"x-tpaa-role": "TEAM_LEAD"},
    )
    assert p5_read.status_code == 200
    assert p5_read.json()["participant_subject_keys"] == [
        _subject_key(policy)
    ]


def test_m8_batch3_gui_preserves_aircraft_p4_p5_separation(
    policy: M8AuthorityPolicy = M8AuthorityPolicy.from_canonical(),
) -> None:
    service, p5 = _service(policy)
    projection = service.workspace(
        M8WorkspaceQuery(
            P4_ID,
            p5.mission_assessment_id,
            _viewer("ANALYST"),
        )
    )
    model = build_m8_layered_workspace_model(
        projection,
        expected_p4_revision_id=P4_ID,
        expected_p5_revision_id=p5.mission_assessment_id,
    )
    assert model.aircraft_layers == (
        "P1_OBSERVED",
        "P2_ADJUSTED",
        "P3_REFERENCE_CONDITION_LONGITUDINAL",
    )
    assert model.p4.direct_actor_id is None
    assert model.p4.score is None
    assert model.p5.overall_score is None
    assert model.p5.composition_id == p5.composition_id


def test_m8_batch3_pre_exit_api_fails_closed(
    policy: M8AuthorityPolicy = M8AuthorityPolicy.from_canonical(),
) -> None:
    repository = InMemoryM8AssessmentRepository()
    repository.register_p4(_p4(policy))
    _, _, _, p5 = _p5(policy)
    repository.register_p5(p5)
    service = M8WorkspaceService(repository, policy=policy)
    with pytest.raises(M8ApplicationError) as blocked:
        service.p4(M8P4Query(P4_ID, _viewer("ANALYST")))
    assert blocked.value.code == "M8_P4_P5_NOT_ADMITTED"
