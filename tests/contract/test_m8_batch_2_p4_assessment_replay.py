from __future__ import annotations

from dataclasses import replace

import pytest

from tpaa_assessment import (
    ApprovalCommand,
    InstructorAnnotationCommand,
    P4InstructorWorkflow,
    P4SubjectSource,
    build_p4_assessment_revision,
    build_p4_subject_context,
    materialize_p4_human_machine_evidence,
)
from tpaa_context import M8AuthorityPolicy, M8GovernanceError, M8RoleModelBinding, P3ClaimEnvelope
from tpaa_longitudinal import build_p4_longitudinal_replay
from tpaa_world import (
    M8EvidenceRef,
    M8WorldFactRef,
    build_p4_interaction_scope_snapshot,
)

H = "a" * 64
U = {
    "actor": "11111111-1111-4111-8111-111111111111",
    "reviewer": "12121212-1212-4121-8121-121212121212",
    "session": "22222222-2222-4222-8222-222222222222",
    "episode": "33333333-3333-4333-8333-333333333333",
    "prior_episode": "34343434-3434-4343-8343-343434343434",
    "stage": "44444444-4444-4444-8444-444444444444",
    "aircraft": "55555555-5555-4555-8555-555555555555",
    "twin": "66666666-6666-4666-8666-666666666666",
    "estimate": "77777777-7777-4777-8777-777777777777",
    "evidence": "88888888-8888-4888-8888-888888888888",
    "role_artifact": "99999999-9999-4999-8999-999999999999",
    "role_object": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "release": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
}


@pytest.fixture(scope="module")
def policy() -> M8AuthorityPolicy:
    return M8AuthorityPolicy.from_canonical()


def _role_model() -> M8RoleModelBinding:
    return M8RoleModelBinding(
        context_artifact_id=U["role_artifact"],
        object_ref_id=U["role_object"],
        artifact_kind="ROLE_MODEL",
        binding_role="ROLE_MODEL",
        logical_key="M8_ROLE_MODEL:P4_P5_LEAST_PRIVILEGE",
        artifact_version="1.0.0",
        schema_version="TPAA_M8_ROLE_PRIVACY_PROFILE_V1",
        artifact_sha256=H,
        status="ACTIVE",
        sealed=True,
        effective_from_utc="2026-09-01T00:00:00Z",
        effective_to_utc=None,
    )


def _subject_source() -> P4SubjectSource:
    return P4SubjectSource(
        actor_id=U["actor"],
        role_code="SUBJECT_SELF",
        seat_code="FRONT",
        function_code="PILOT",
        session_id=U["session"],
        episode_id=U["episode"],
        stage_id=U["stage"],
        aircraft_id=U["aircraft"],
        twin_revision_id=U["twin"],
        p3_estimate_id=U["estimate"],
        p3_source_episode_ids=(U["prior_episode"],),
        assessment_spec_id="P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        world_refs=("world:action:1", "world:perceived:1"),
        evidence_set_id=U["evidence"],
        as_of_utc="2026-09-20T12:00:00Z",
        knowledge_time_utc="2026-09-20T11:59:59Z",
    )


def _scope(policy: M8AuthorityPolicy):
    subject = build_p4_subject_context(
        _subject_source(),
        role_model=_role_model(),
        policy=policy,
    )
    fact = M8WorldFactRef(
        ref_id="world:action:1",
        world_layer="ACTION_WORLD",
        episode_id=U["episode"],
        stage_id=U["stage"],
        source_hash=H,
        knowledge_time_utc="2026-09-20T11:30:00Z",
    )
    machine = M8EvidenceRef(
        evidence_id="machine:action-timing:1",
        origin="MACHINE",
        evidence_family="ACTION_TIMING",
        evidence_set_id=U["evidence"],
        episode_id=U["episode"],
        world_refs=("world:action:1",),
        source_refs=("metric:timing:1",),
        availability_status="AVAILABLE",
        numeric_value=0.25,
        knowledge_time_utc="2026-09-20T11:40:00Z",
    )
    scope = build_p4_interaction_scope_snapshot(
        subject_context_id=subject.subject_context_id,
        episode_id=subject.episode_id,
        as_of_utc=subject.as_of_utc,
        fact_refs=(fact,),
        machine_evidence=(machine,),
        instructor_evidence=(),
        policy=policy,
    )
    return subject, scope


def _claim() -> P3ClaimEnvelope:
    return P3ClaimEnvelope(
        claim_level="REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        validity_status="VALID",
        as_of_utc="2026-09-20T12:00:00Z",
        uncertainty_lower=39.0,
        uncertainty_upper=41.0,
    )


def test_m8_batch2_machine_evidence_is_exact_deterministic_and_unscored(
    policy: M8AuthorityPolicy,
) -> None:
    subject, scope = _scope(policy)
    first = materialize_p4_human_machine_evidence(subject, scope, policy=policy)
    second = materialize_p4_human_machine_evidence(subject, scope, policy=policy)
    assert first == second
    assert len(first) == 1
    assert first[0].origin == "MACHINE"
    assert first[0].capability_projection_refs == (U["twin"], U["estimate"])
    assert "score" not in first[0].projection()
    assert first[0].reason_codes == ()


def test_m8_batch2_unavailable_evidence_remains_explicit(
    policy: M8AuthorityPolicy,
) -> None:
    subject, scope = _scope(policy)
    unavailable = replace(
        scope.machine_evidence[0],
        availability_status="OUT_OF_DOMAIN",
        numeric_value=None,
    )
    changed_scope = replace(scope, machine_evidence=(unavailable,))
    products = materialize_p4_human_machine_evidence(
        subject,
        changed_scope,
        policy=policy,
    )
    assert products[0].availability_status == "OUT_OF_DOMAIN"
    assert products[0].numeric_value is None
    assert products[0].reason_codes == ("P4_EVIDENCE_OUT_OF_DOMAIN",)


def test_m8_batch2_annotation_revision_is_immutable_and_idempotent(
    policy: M8AuthorityPolicy,
) -> None:
    subject, _ = _scope(policy)
    workflow = P4InstructorWorkflow(policy)
    create = InstructorAnnotationCommand(
        request_id="annotation-request-1",
        author_actor_id=U["reviewer"],
        viewer_role="INSTRUCTOR_EVALUATOR",
        scope_match=True,
        subject_context_id=subject.subject_context_id,
        base_release_id=U["release"],
        session_id=subject.session_id,
        episode_id=subject.episode_id,
        stage_id=subject.stage_id,
        annotation_type="INSTRUCTOR_NOTE",
        start_session_time_us=100,
        end_session_time_us=200,
        body_text="Observed timing discipline.",
        visibility="EVALUATOR",
        evidence_set_id=subject.evidence_set_id,
        reason="initial note",
        created_at_utc="2026-09-20T12:10:00Z",
    )
    first = workflow.annotate(create)
    replay = workflow.annotate(create)
    assert replay.reused is True
    assert replay.revision == first.revision
    assert first.audit.object_id == first.revision.annotation_id

    revise = replace(
        create,
        request_id="annotation-request-2",
        body_text="Observed timing discipline; correction verified.",
        reason="corrected note",
        created_at_utc="2026-09-20T12:20:00Z",
    )
    second = workflow.annotate(revise, previous=first.revision)
    assert second.revision.annotation_id != first.revision.annotation_id
    assert second.revision.revision_no == 2
    assert second.revision.supersedes_annotation_id == first.revision.annotation_id
    assert first.revision.body_text == "Observed timing discipline."


def test_m8_batch2_annotation_and_approval_role_denial_fail_closed(
    policy: M8AuthorityPolicy,
) -> None:
    subject, _ = _scope(policy)
    workflow = P4InstructorWorkflow(policy)
    denied = InstructorAnnotationCommand(
        request_id="annotation-denied",
        author_actor_id=U["reviewer"],
        viewer_role="ANALYST",
        scope_match=True,
        subject_context_id=subject.subject_context_id,
        base_release_id=U["release"],
        session_id=subject.session_id,
        episode_id=subject.episode_id,
        stage_id=subject.stage_id,
        annotation_type="INSTRUCTOR_NOTE",
        start_session_time_us=None,
        end_session_time_us=None,
        body_text="Denied.",
        visibility="EVALUATOR",
        evidence_set_id=None,
        reason="denied",
        created_at_utc="2026-09-20T12:10:00Z",
    )
    with pytest.raises(M8GovernanceError) as exc:
        workflow.annotate(denied)
    assert exc.value.code == "FAIL_CLOSED_P4_P5_APPROVAL_NOT_AUTHORIZED"


def test_m8_batch2_p4_assessment_revision_and_approval_chain(
    policy: M8AuthorityPolicy,
) -> None:
    subject, scope = _scope(policy)
    evidence = materialize_p4_human_machine_evidence(subject, scope, policy=policy)
    workflow = P4InstructorWorkflow(policy)
    annotation = workflow.annotate(
        InstructorAnnotationCommand(
            request_id="assessment-note-1",
            author_actor_id=U["reviewer"],
            viewer_role="INSTRUCTOR_EVALUATOR",
            scope_match=True,
            subject_context_id=subject.subject_context_id,
            base_release_id=U["release"],
            session_id=subject.session_id,
            episode_id=subject.episode_id,
            stage_id=subject.stage_id,
            annotation_type="INSTRUCTOR_NOTE",
            start_session_time_us=None,
            end_session_time_us=None,
            body_text="Ready for review.",
            visibility="EVALUATOR",
            evidence_set_id=subject.evidence_set_id,
            reason="support assessment",
            created_at_utc="2026-09-20T12:10:00Z",
        )
    ).revision
    draft = build_p4_assessment_revision(
        subject,
        evidence=evidence,
        annotations=(annotation,),
        p3_claim=_claim(),
        confidence=0.9,
        created_at_utc="2026-09-20T12:30:00Z",
        policy=policy,
    )
    assert draft.score is None
    assert draft.grade is None
    assert draft.approval_state == "DRAFT"
    assert draft.p3_claim_level == "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"

    review = workflow.transition_approval(
        draft,
        ApprovalCommand(
            request_id="approval-request-1",
            reviewer_actor_id=U["reviewer"],
            viewer_role="INSTRUCTOR_EVALUATOR",
            scope_match=True,
            target_state="IN_REVIEW",
            reason="begin review",
            created_at_utc="2026-09-20T12:40:00Z",
        ),
    )
    approval = workflow.transition_approval(
        review.revision,
        ApprovalCommand(
            request_id="approval-request-2",
            reviewer_actor_id=U["reviewer"],
            viewer_role="INSTRUCTOR_EVALUATOR",
            scope_match=True,
            target_state="APPROVED",
            reason="approved",
            created_at_utc="2026-09-20T12:50:00Z",
        ),
    )
    assert review.revision.supersedes_id == draft.actor_assessment_id
    assert approval.revision.supersedes_id == review.revision.actor_assessment_id
    assert approval.revision.approval_state == "APPROVED"
    assert approval.audit.action == policy.approval_audit_action_p4

    replay = workflow.transition_approval(
        review.revision,
        ApprovalCommand(
            request_id="approval-request-2",
            reviewer_actor_id=U["reviewer"],
            viewer_role="INSTRUCTOR_EVALUATOR",
            scope_match=True,
            target_state="APPROVED",
            reason="approved",
            created_at_utc="2026-09-20T12:50:00Z",
        ),
    )
    assert replay.reused is True
    assert replay.revision == approval.revision


def test_m8_batch2_invalid_approval_transition_and_request_conflict(
    policy: M8AuthorityPolicy,
) -> None:
    subject, scope = _scope(policy)
    draft = build_p4_assessment_revision(
        subject,
        evidence=materialize_p4_human_machine_evidence(subject, scope, policy=policy),
        annotations=(),
        p3_claim=_claim(),
        confidence=0.8,
        created_at_utc="2026-09-20T12:30:00Z",
        policy=policy,
    )
    workflow = P4InstructorWorkflow(policy)
    with pytest.raises(M8GovernanceError) as invalid:
        workflow.transition_approval(
            draft,
            ApprovalCommand(
                request_id="bad-transition",
                reviewer_actor_id=U["reviewer"],
                viewer_role="INSTRUCTOR_EVALUATOR",
                scope_match=True,
                target_state="APPROVED",
                reason="skip review",
                created_at_utc="2026-09-20T12:40:00Z",
            ),
        )
    assert invalid.value.code == "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID"


def test_m8_batch2_longitudinal_replay_is_exact_and_as_of_bounded(
    policy: M8AuthorityPolicy,
) -> None:
    subject, scope = _scope(policy)
    draft = build_p4_assessment_revision(
        subject,
        evidence=materialize_p4_human_machine_evidence(subject, scope, policy=policy),
        annotations=(),
        p3_claim=_claim(),
        confidence=0.8,
        created_at_utc="2026-09-20T12:30:00Z",
        policy=policy,
    )
    workflow = P4InstructorWorkflow(policy)
    review = workflow.transition_approval(
        draft,
        ApprovalCommand(
            request_id="replay-review",
            reviewer_actor_id=U["reviewer"],
            viewer_role="INSTRUCTOR_EVALUATOR",
            scope_match=True,
            target_state="IN_REVIEW",
            reason="review",
            created_at_utc="2026-09-20T12:40:00Z",
        ),
    ).revision
    approved = workflow.transition_approval(
        review,
        ApprovalCommand(
            request_id="replay-approved",
            reviewer_actor_id=U["reviewer"],
            viewer_role="INSTRUCTOR_EVALUATOR",
            scope_match=True,
            target_state="APPROVED",
            reason="approved",
            created_at_utc="2026-09-20T12:50:00Z",
        ),
    ).revision

    historical = build_p4_longitudinal_replay(
        (draft, review, approved),
        replay_as_of_utc="2026-09-20T12:45:00Z",
    )
    assert tuple(row.actor_assessment_id for row in historical.revisions) == (
        draft.actor_assessment_id,
        review.actor_assessment_id,
    )
    assert historical.active_revision_ids == (review.actor_assessment_id,)

    current = build_p4_longitudinal_replay(
        (approved, draft, review),
        replay_as_of_utc="2026-09-20T13:00:00Z",
    )
    assert current.active_revision_ids == (approved.actor_assessment_id,)
    assert current.longitudinal_identity == historical.longitudinal_identity


def test_m8_batch2_longitudinal_configuration_drift_is_not_pooled(
    policy: M8AuthorityPolicy,
) -> None:
    subject, scope = _scope(policy)
    evidence = materialize_p4_human_machine_evidence(subject, scope, policy=policy)
    first = build_p4_assessment_revision(
        subject,
        evidence=evidence,
        annotations=(),
        p3_claim=_claim(),
        confidence=0.8,
        created_at_utc="2026-09-20T12:30:00Z",
        policy=policy,
    )
    drifted = replace(
        first,
        actor_assessment_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        assessment_spec_version="2.0.0",
        created_at_utc="2026-09-21T12:30:00Z",
        supersedes_id=None,
        logical_content_hash="b" * 64,
    )
    with pytest.raises(M8GovernanceError) as exc:
        build_p4_longitudinal_replay(
            (first, drifted),
            replay_as_of_utc="2026-09-22T00:00:00Z",
        )
    assert exc.value.code == "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED"
