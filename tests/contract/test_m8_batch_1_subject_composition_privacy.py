from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from tpaa_assessment import (
    P4SubjectSource,
    assert_p4_subject_context_identity,
    build_p4_subject_context,
)
from tpaa_canonical import CanonicalArtifactLoader
from tpaa_context import (
    M8AdmissionEvidence,
    M8AuthorityPolicy,
    M8GovernanceError,
    M8RoleModelBinding,
    P3ClaimEnvelope,
    assert_annotation_body_allowed,
    assert_capability_claim_allowed,
    assert_p3_claim_preserved,
    assert_scope_copy_allowed,
    assert_write_allowed,
    project_direct_actor_id,
    pseudonymous_subject_key,
    validate_availability_numeric,
)
from tpaa_world import (
    M8EvidenceRef,
    M8WorldFactRef,
    P5CompositionSnapshot,
    P5ParticipantBinding,
    assert_composition_identity,
    assert_world_facts_immutable,
    build_p4_interaction_scope_snapshot,
    build_p5_composition_snapshot,
)

H = "a" * 64
U = {
    "actor": "11111111-1111-4111-8111-111111111111",
    "actor2": "12121212-1212-4121-8121-121212121212",
    "session": "22222222-2222-4222-8222-222222222222",
    "episode": "33333333-3333-4333-8333-333333333333",
    "prior_episode": "34343434-3434-4343-8343-343434343434",
    "stage": "44444444-4444-4444-8444-444444444444",
    "aircraft": "55555555-5555-4555-8555-555555555555",
    "aircraft2": "56565656-5656-4565-8565-565656565656",
    "twin": "66666666-6666-4666-8666-666666666666",
    "twin2": "67676767-6767-4676-8676-676767676767",
    "estimate": "77777777-7777-4777-8777-777777777777",
    "evidence": "88888888-8888-4888-8888-888888888888",
    "role_artifact": "99999999-9999-4999-8999-999999999999",
    "role_object": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "p4_revision": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "p4_revision2": "bcbcbcbc-bcbc-4bcb-8bcb-bcbcbcbcbcbc",
    "team": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "scenario": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
}


class _BrokenLoader:
    def load(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OSError("missing authority")


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


def _subject(
    *,
    actor_id: str = U["actor"],
    aircraft_id: str = U["aircraft"],
    twin_revision_id: str = U["twin"],
) -> P4SubjectSource:
    return P4SubjectSource(
        actor_id=actor_id,
        role_code="SUBJECT_SELF",
        seat_code="FRONT",
        function_code="PILOT",
        session_id=U["session"],
        episode_id=U["episode"],
        stage_id=U["stage"],
        aircraft_id=aircraft_id,
        twin_revision_id=twin_revision_id,
        p3_estimate_id=U["estimate"],
        p3_source_episode_ids=(U["prior_episode"],),
        assessment_spec_id="P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        world_refs=("world:action:1", "world:perceived:1"),
        evidence_set_id=U["evidence"],
        as_of_utc="2026-09-20T12:00:00Z",
        knowledge_time_utc="2026-09-20T11:59:59Z",
    )


def _machine() -> M8EvidenceRef:
    return M8EvidenceRef(
        evidence_id="machine-evidence-1",
        origin="MACHINE",
        evidence_family="ACTION_TIMING",
        evidence_set_id=U["evidence"],
        episode_id=U["episode"],
        world_refs=("world:action:1",),
        source_refs=("metric:timing:1",),
        availability_status="AVAILABLE",
        numeric_value=0.25,
        knowledge_time_utc="2026-09-20T11:50:00Z",
    )


def _instructor() -> M8EvidenceRef:
    return M8EvidenceRef(
        evidence_id="instructor-evidence-1",
        origin="INSTRUCTOR",
        evidence_family="INSTRUCTOR_ANNOTATION",
        evidence_set_id=U["evidence"],
        episode_id=U["episode"],
        world_refs=("world:action:1",),
        source_refs=("annotation:1",),
        availability_status="AVAILABLE",
        numeric_value=None,
        knowledge_time_utc="2026-09-20T11:55:00Z",
    )


def _facts() -> tuple[M8WorldFactRef, ...]:
    return (
        M8WorldFactRef(
            ref_id="world:ground-truth:1",
            world_layer="GROUND_TRUTH",
            episode_id=U["episode"],
            stage_id=U["stage"],
            source_hash=H,
            knowledge_time_utc="2026-09-20T11:30:00Z",
        ),
        M8WorldFactRef(
            ref_id="world:perceived:1",
            world_layer="PERCEIVED_WORLD",
            episode_id=U["episode"],
            stage_id=U["stage"],
            source_hash="b" * 64,
            knowledge_time_utc="2026-09-20T11:31:00Z",
        ),
    )


def test_m8_batch1_policy_loads_and_missing_authority_fails_closed(
    policy: M8AuthorityPolicy,
) -> None:
    assert policy.role_profile_id == "P4_P5_ROLE_PRIVACY_PROFILE"
    assert tuple(rule.role for rule in policy.role_rules) == (
        "SUBJECT_SELF",
        "INSTRUCTOR_EVALUATOR",
        "TEAM_LEAD",
        "ANALYST",
        "ADMIN_AUDITOR",
    )
    with pytest.raises(M8GovernanceError) as missing:
        M8AuthorityPolicy.from_canonical(
            cast(CanonicalArtifactLoader, _BrokenLoader())
        )
    assert missing.value.code == "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED"


def test_m8_batch1_p4_subject_context_is_exact_and_deterministic(
    policy: M8AuthorityPolicy,
) -> None:
    first = build_p4_subject_context(
        _subject(),
        role_model=_role_model(),
        policy=policy,
    )
    second = build_p4_subject_context(
        _subject(),
        role_model=_role_model(),
        policy=policy,
    )
    assert first.subject_context_id == second.subject_context_id
    assert first.subject_context_id.startswith("P4_SUBJECT_CONTEXT_SHA256:")
    assert first.subject_key == pseudonymous_subject_key(U["actor"], policy=policy)
    assert first.world_refs == tuple(sorted(_subject().world_refs))
    assert_p4_subject_context_identity(first)


def test_m8_batch1_p4_alias_future_and_same_episode_fail_closed(
    policy: M8AuthorityPolicy,
) -> None:
    with pytest.raises(M8GovernanceError) as alias:
        build_p4_subject_context(
            replace(_subject(), assessment_spec_version="LATEST"),
            role_model=_role_model(),
            policy=policy,
        )
    assert alias.value.code == "FAIL_CLOSED_P4_P5_CURRENT_LATEST_DEFAULT_FORBIDDEN"

    with pytest.raises(M8GovernanceError) as future:
        build_p4_subject_context(
            replace(_subject(), knowledge_time_utc="2026-09-21T00:00:00Z"),
            role_model=_role_model(),
            policy=policy,
        )
    assert future.value.code == "FAIL_CLOSED_P4_P5_FUTURE_INFORMATION"

    with pytest.raises(M8GovernanceError) as episode:
        build_p4_subject_context(
            replace(_subject(), p3_source_episode_ids=(U["episode"],)),
            role_model=_role_model(),
            policy=policy,
        )
    assert episode.value.code == "FAIL_CLOSED_P4_P5_SAME_EPISODE_LEAKAGE"


def test_m8_batch1_privacy_projection_is_least_privilege(
    policy: M8AuthorityPolicy,
) -> None:
    assert (
        project_direct_actor_id(
            U["actor"],
            viewer_role="SUBJECT_SELF",
            viewer_actor_id=U["actor"],
            scope_match=True,
            policy=policy,
        )
        == U["actor"]
    )
    assert (
        project_direct_actor_id(
            U["actor"],
            viewer_role="SUBJECT_SELF",
            viewer_actor_id=U["actor2"],
            scope_match=True,
            policy=policy,
        )
        is None
    )
    assert (
        project_direct_actor_id(
            U["actor"],
            viewer_role="ANALYST",
            viewer_actor_id=None,
            scope_match=True,
            policy=policy,
        )
        is None
    )
    assert (
        project_direct_actor_id(
            U["actor"],
            viewer_role="TEAM_LEAD",
            viewer_actor_id=None,
            scope_match=True,
            policy=policy,
        )
        is None
    )
    assert (
        project_direct_actor_id(
            U["actor"],
            viewer_role="INSTRUCTOR_EVALUATOR",
            viewer_actor_id=U["actor2"],
            scope_match=True,
            policy=policy,
        )
        == U["actor"]
    )
    assert (
        project_direct_actor_id(
            U["actor"],
            viewer_role="ADMIN_AUDITOR",
            viewer_actor_id=None,
            scope_match=True,
            privileged_identity_authorized=False,
            policy=policy,
        )
        is None
    )
    assert (
        project_direct_actor_id(
            U["actor"],
            viewer_role="ADMIN_AUDITOR",
            viewer_actor_id=None,
            scope_match=True,
            privileged_identity_authorized=True,
            policy=policy,
        )
        == U["actor"]
    )

    assert_annotation_body_allowed(
        viewer_role="INSTRUCTOR_EVALUATOR",
        scope_match=True,
        visibility_authorized=True,
        policy=policy,
    )
    with pytest.raises(M8GovernanceError):
        assert_annotation_body_allowed(
            viewer_role="ANALYST",
            scope_match=True,
            visibility_authorized=True,
            policy=policy,
        )
    assert_write_allowed(
        "APPROVAL",
        viewer_role="INSTRUCTOR_EVALUATOR",
        scope_match=True,
        policy=policy,
    )
    with pytest.raises(M8GovernanceError) as admin:
        assert_write_allowed(
            "APPROVAL",
            viewer_role="ADMIN_AUDITOR",
            scope_match=True,
            policy=policy,
        )
    assert admin.value.code == "FAIL_CLOSED_P4_P5_APPROVAL_NOT_AUTHORIZED"


def test_m8_batch1_admission_claim_and_scope_guards_fail_closed(
    policy: M8AuthorityPolicy,
) -> None:
    blocked = M8AdmissionEvidence(
        source_revision="1" * 40,
        event_name="pull_request",
        git_ref="refs/pull/188/merge",
        protected_main=False,
        m8_exit_decision="PENDING_PROTECTED_MAIN",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
        p4_admitted=False,
        p5_admitted=False,
        p6_inactive=True,
    )
    with pytest.raises(M8GovernanceError) as p4:
        assert_capability_claim_allowed("P4", evidence=blocked, policy=policy)
    assert p4.value.code == "FAIL_CLOSED_P4_P5_NOT_ADMITTED"

    allowed = replace(
        blocked,
        event_name="push",
        git_ref="refs/heads/main",
        protected_main=True,
        m8_exit_decision="GO",
        p4_admitted=True,
        p5_admitted=True,
    )
    assert_capability_claim_allowed("P4", evidence=allowed, policy=policy)
    assert_capability_claim_allowed("P5", evidence=allowed, policy=policy)

    with pytest.raises(M8GovernanceError) as p6:
        assert_capability_claim_allowed("P6", evidence=allowed, policy=policy)
    assert p6.value.code == "FAIL_CLOSED_P6_NOT_ADMITTED"

    source = P3ClaimEnvelope(
        claim_level="REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        validity_status="VALID",
        as_of_utc="2026-09-20T00:00:00Z",
        uncertainty_lower=39.0,
        uncertainty_upper=41.0,
    )
    assert_p3_claim_preserved(source, source)
    with pytest.raises(M8GovernanceError):
        assert_p3_claim_preserved(
            source,
            replace(source, claim_level="INTRINSIC_CAPABILITY_ESTIMATE"),
        )

    with pytest.raises(M8GovernanceError) as copy:
        assert_scope_copy_allowed("P5", "P4")
    assert copy.value.code == "FAIL_CLOSED_P4_P5_TEAM_TO_INDIVIDUAL_COPY"


def test_m8_batch1_world_evidence_boundary_is_deterministic(
    policy: M8AuthorityPolicy,
) -> None:
    subject = build_p4_subject_context(
        _subject(),
        role_model=_role_model(),
        policy=policy,
    )
    first = build_p4_interaction_scope_snapshot(
        subject_context_id=subject.subject_context_id,
        episode_id=U["episode"],
        as_of_utc="2026-09-20T12:00:00Z",
        fact_refs=_facts(),
        machine_evidence=(_machine(),),
        instructor_evidence=(_instructor(),),
        policy=policy,
    )
    second = build_p4_interaction_scope_snapshot(
        subject_context_id=subject.subject_context_id,
        episode_id=U["episode"],
        as_of_utc="2026-09-20T12:00:00Z",
        fact_refs=tuple(reversed(_facts())),
        machine_evidence=(_machine(),),
        instructor_evidence=(_instructor(),),
        policy=policy,
    )
    assert first.scope_hash == second.scope_hash
    assert first.fact_refs == second.fact_refs
    assert first.machine_evidence[0].origin == "MACHINE"
    assert first.instructor_evidence[0].origin == "INSTRUCTOR"
    assert_world_facts_immutable(first.fact_refs, second.fact_refs)


def test_m8_batch1_world_leakage_conflation_and_zero_coercion_fail_closed(
    policy: M8AuthorityPolicy,
) -> None:
    subject = build_p4_subject_context(
        _subject(),
        role_model=_role_model(),
        policy=policy,
    )
    with pytest.raises(M8GovernanceError) as future:
        build_p4_interaction_scope_snapshot(
            subject_context_id=subject.subject_context_id,
            episode_id=U["episode"],
            as_of_utc="2026-09-20T12:00:00Z",
            fact_refs=_facts(),
            machine_evidence=(
                replace(_machine(), knowledge_time_utc="2026-09-21T00:00:00Z"),
            ),
            instructor_evidence=(_instructor(),),
            policy=policy,
        )
    assert future.value.code == "FAIL_CLOSED_P4_P5_FUTURE_INFORMATION"

    with pytest.raises(M8GovernanceError) as conflation:
        build_p4_interaction_scope_snapshot(
            subject_context_id=subject.subject_context_id,
            episode_id=U["episode"],
            as_of_utc="2026-09-20T12:00:00Z",
            fact_refs=_facts(),
            machine_evidence=(
                replace(
                    _machine(),
                    evidence_family="INSTRUCTOR_ANNOTATION",
                ),
            ),
            instructor_evidence=(_instructor(),),
            policy=policy,
        )
    assert (
        conflation.value.code
        == "FAIL_CLOSED_P4_P5_MACHINE_HUMAN_EVIDENCE_CONFLATION"
    )

    with pytest.raises(M8GovernanceError) as zero:
        validate_availability_numeric(
            status="UNAVAILABLE",
            numeric_value=0.0,
            policy=policy,
        )
    assert zero.value.code == "FAIL_CLOSED_P4_P5_UNAVAILABLE_ZERO_COERCION"


def _composition(
    policy: M8AuthorityPolicy,
    participants: tuple[P5ParticipantBinding, ...],
    *,
    assessment_spec_version: str = "1.0.0",
) -> P5CompositionSnapshot:
    return build_p5_composition_snapshot(
        session_id=U["session"],
        mission_episode_id=U["episode"],
        team_id=U["team"],
        participants=participants,
        world_snapshot_refs=("world-snapshot-b", "world-snapshot-a"),
        scenario_context_artifact_id=U["scenario"],
        role_model_context_artifact_id=U["role_artifact"],
        assessment_spec_id="P5_ASSESSMENT:TEAM_EVIDENCE_ONLY",
        assessment_spec_version=assessment_spec_version,
        as_of_utc="2026-09-20T12:00:00Z",
        policy=policy,
    )


def test_m8_batch1_p5_composition_is_deterministic_and_drift_sensitive(
    policy: M8AuthorityPolicy,
) -> None:
    subject1 = build_p4_subject_context(
        _subject(),
        role_model=_role_model(),
        policy=policy,
    )
    subject2 = build_p4_subject_context(
        _subject(
            actor_id=U["actor2"],
            aircraft_id=U["aircraft2"],
            twin_revision_id=U["twin2"],
        ),
        role_model=_role_model(),
        policy=policy,
    )
    participants = (
        P5ParticipantBinding(
            subject_key=subject1.subject_key,
            role_code="FLIGHT_LEAD",
            aircraft_id=U["aircraft"],
            twin_revision_id=U["twin"],
            p4_revision_id=U["p4_revision"],
        ),
        P5ParticipantBinding(
            subject_key=subject2.subject_key,
            role_code="WINGMAN",
            aircraft_id=U["aircraft2"],
            twin_revision_id=U["twin2"],
            p4_revision_id=U["p4_revision2"],
        ),
    )
    first = _composition(policy, participants)
    second = _composition(policy, tuple(reversed(participants)))
    assert first.composition_id == second.composition_id
    assert first.participant_subject_keys == tuple(
        sorted(first.participant_subject_keys)
    )
    assert first.world_snapshot_refs == ("world-snapshot-a", "world-snapshot-b")
    assert_composition_identity(first)

    changed_participant = replace(
        participants[1],
        role_code="ELEMENT_LEAD",
    )
    changed = _composition(
        policy,
        (participants[0], changed_participant),
    )
    assert changed.composition_id != first.composition_id

    with pytest.raises(M8GovernanceError) as drift:
        assert_composition_identity(
            replace(
                first,
                participant_bindings=(
                    first.participant_bindings[0],
                    changed_participant,
                ),
            )
        )
    assert drift.value.code == "FAIL_CLOSED_P4_P5_COMPOSITION_DRIFT"

    with pytest.raises(M8GovernanceError) as alias:
        _composition(
            policy,
            participants,
            assessment_spec_version="DEFAULT",
        )
    assert alias.value.code == "FAIL_CLOSED_P4_P5_CURRENT_LATEST_DEFAULT_FORBIDDEN"
