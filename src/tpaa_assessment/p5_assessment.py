"""M8 Batch 3 exact composition-bound P5 team/mission assessment substrate."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from uuid import UUID, uuid5

from tpaa_context import (
    M8AuthorityPolicy,
    M8GovernanceError,
    assert_scope_copy_allowed,
    assert_write_allowed,
    canonical_hash,
    exact_text,
    exact_uuid,
    pseudonymous_subject_key,
    utc,
)
from tpaa_world import P5CompositionSnapshot, assert_composition_identity

from .p4_revision import P4AssessmentRevision

_P5_ASSESSMENT_NAMESPACE = UUID("2fa00fb8-a1aa-57c9-9e82-61d8a0360a11")


@dataclass(frozen=True)
class P5MemberEvidence:
    subject_key: str
    mission_role_code: str
    aircraft_id: str | None
    twin_revision_id: str | None
    p4_revision_id: str
    availability_status: str
    reason_codes: tuple[str, ...]
    p4_approval_state: str | None
    p3_claim_level: str | None
    p3_validity_status: str | None
    p3_as_of_utc: str | None
    uncertainty_lower: float | None
    uncertainty_upper: float | None


@dataclass(frozen=True)
class P5TeamMissionEvidence:
    evidence_id: str
    composition_id: str
    participant_subject_keys: tuple[str, ...]
    member_evidence: tuple[P5MemberEvidence, ...]
    world_snapshot_refs: tuple[str, ...]
    objective_result_refs: tuple[str, ...]
    evidence_set_id: str
    availability_status: str
    reason_codes: tuple[str, ...]
    as_of_utc: str
    evidence_hash: str


@dataclass(frozen=True)
class P5AggregationResult:
    aggregation_profile_ref: None
    overall_score: None
    grade: None
    mode: str
    evidence_id: str
    logical_hash: str


@dataclass(frozen=True)
class P5AssessmentRevision:
    mission_assessment_id: str
    composition_id: str
    session_id: str
    mission_episode_id: str
    team_id: str | None
    assessment_spec_id: str
    assessment_spec_version: str
    participant_subject_keys: tuple[str, ...]
    world_snapshot_refs: tuple[str, ...]
    objective_result_refs: tuple[str, ...]
    team_performance_evidence_id: str
    aggregation_profile_ref: None
    overall_score: None
    grade: None
    status: str
    confidence: float
    evidence_set_id: str
    created_at_utc: str
    supersedes_id: str | None
    approval_state: str
    claim_level: str
    validity_status: str
    as_of_utc: str
    logical_content_hash: str


@dataclass(frozen=True)
class P5ApprovalCommand:
    request_id: str
    reviewer_actor_id: str
    viewer_role: str
    scope_match: bool
    target_state: str
    reason: str
    created_at_utc: str


@dataclass(frozen=True)
class P5AuditRecord:
    audit_key: str
    actor_subject_key: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    reason: str
    request_id: str
    created_at_utc: str


@dataclass(frozen=True)
class P5ApprovalWorkflowResult:
    revision: P5AssessmentRevision
    audit: P5AuditRecord
    reused: bool


def _exact_refs(
    values: tuple[str, ...],
    *,
    field: str,
    policy: M8AuthorityPolicy,
) -> tuple[str, ...]:
    checked = tuple(
        exact_text(value, field=f"{field}[{index}]", policy=policy)
        for index, value in enumerate(values)
    )
    if len(set(checked)) != len(checked):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"duplicate {field}",
        )
    return tuple(sorted(checked))


def materialize_p5_team_mission_evidence(
    composition: P5CompositionSnapshot,
    *,
    p4_revisions: tuple[P4AssessmentRevision, ...],
    evidence_set_id: str,
    objective_result_refs: tuple[str, ...],
    as_of_utc: str,
    policy: M8AuthorityPolicy | None = None,
) -> P5TeamMissionEvidence:
    p = policy or M8AuthorityPolicy.from_canonical()
    assert_composition_identity(composition)
    exact_text(composition.composition_id, field="composition_id", policy=p)
    exact_uuid(evidence_set_id, field="evidence_set_id", policy=p)
    if as_of_utc != composition.as_of_utc:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "P5 evidence as_of must equal composition as_of",
        )
    cutoff = utc(as_of_utc, field="as_of_utc")
    objectives = _exact_refs(
        objective_result_refs,
        field="objective_result_refs",
        policy=p,
    )

    by_id: dict[str, P4AssessmentRevision] = {}
    for revision in p4_revisions:
        if revision.actor_assessment_id in by_id:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                "duplicate P4 revision input",
            )
        by_id[revision.actor_assessment_id] = revision

    members: list[P5MemberEvidence] = []
    missing: list[str] = []
    for binding in composition.participant_bindings:
        revision = by_id.get(binding.p4_revision_id)
        if revision is None:
            missing.append(binding.subject_key)
            members.append(
                P5MemberEvidence(
                    subject_key=binding.subject_key,
                    mission_role_code=binding.role_code,
                    aircraft_id=binding.aircraft_id,
                    twin_revision_id=binding.twin_revision_id,
                    p4_revision_id=binding.p4_revision_id,
                    availability_status="UNAVAILABLE",
                    reason_codes=("MISSING_P4_REVISION",),
                    p4_approval_state=None,
                    p3_claim_level=None,
                    p3_validity_status=None,
                    p3_as_of_utc=None,
                    uncertainty_lower=None,
                    uncertainty_upper=None,
                )
            )
            continue
        if (
            revision.subject_key != binding.subject_key
            or revision.aircraft_id != binding.aircraft_id
            or revision.twin_revision_id != binding.twin_revision_id
        ):
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_COMPOSITION_DRIFT",
                binding.subject_key,
            )
        if utc(revision.created_at_utc, field="p4.created_at_utc") > cutoff:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_FUTURE_INFORMATION",
                revision.actor_assessment_id,
            )
        members.append(
            P5MemberEvidence(
                subject_key=binding.subject_key,
                mission_role_code=binding.role_code,
                aircraft_id=binding.aircraft_id,
                twin_revision_id=binding.twin_revision_id,
                p4_revision_id=revision.actor_assessment_id,
                availability_status="AVAILABLE",
                reason_codes=(),
                p4_approval_state=revision.approval_state,
                p3_claim_level=revision.p3_claim_level,
                p3_validity_status=revision.p3_validity_status,
                p3_as_of_utc=revision.p3_as_of_utc,
                uncertainty_lower=revision.uncertainty_lower,
                uncertainty_upper=revision.uncertainty_upper,
            )
        )

    ordered = tuple(sorted(members, key=lambda item: item.subject_key))
    status = "AVAILABLE" if not missing else "UNAVAILABLE"
    reason_codes = tuple(
        f"MISSING_MEMBER:{subject_key}" for subject_key in sorted(missing)
    )
    payload = {
        "composition_id": composition.composition_id,
        "participant_subject_keys": list(composition.participant_subject_keys),
        "member_evidence": [
            {
                "subject_key": item.subject_key,
                "mission_role_code": item.mission_role_code,
                "aircraft_id": item.aircraft_id,
                "twin_revision_id": item.twin_revision_id,
                "p4_revision_id": item.p4_revision_id,
                "availability_status": item.availability_status,
                "reason_codes": list(item.reason_codes),
                "p4_approval_state": item.p4_approval_state,
                "p3_claim_level": item.p3_claim_level,
                "p3_validity_status": item.p3_validity_status,
                "p3_as_of_utc": item.p3_as_of_utc,
                "uncertainty_lower": item.uncertainty_lower,
                "uncertainty_upper": item.uncertainty_upper,
            }
            for item in ordered
        ],
        "world_snapshot_refs": list(composition.world_snapshot_refs),
        "objective_result_refs": list(objectives),
        "evidence_set_id": evidence_set_id,
        "availability_status": status,
        "reason_codes": list(reason_codes),
        "as_of_utc": as_of_utc,
    }
    digest = canonical_hash(payload)
    return P5TeamMissionEvidence(
        evidence_id=f"P5_TEAM_MISSION_EVIDENCE_SHA256:{digest}",
        composition_id=composition.composition_id,
        participant_subject_keys=composition.participant_subject_keys,
        member_evidence=ordered,
        world_snapshot_refs=composition.world_snapshot_refs,
        objective_result_refs=objectives,
        evidence_set_id=evidence_set_id,
        availability_status=status,
        reason_codes=reason_codes,
        as_of_utc=as_of_utc,
        evidence_hash=digest,
    )


def build_p5_aggregation(
    evidence: P5TeamMissionEvidence,
    *,
    aggregation_profile_ref: str | None = None,
    normalization_authority_ref: str | None = None,
    proposed_score: float | None = None,
    proposed_grade: str | None = None,
    policy: M8AuthorityPolicy | None = None,
) -> P5AggregationResult:
    p = policy or M8AuthorityPolicy.from_canonical()
    if (
        aggregation_profile_ref is not None
        or normalization_authority_ref is not None
        or proposed_score is not None
        or proposed_grade is not None
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_AGGREGATION_PROFILE_REQUIRED",
            "no numeric P5 aggregation profile is adopted in M8 authority",
        )
    if p.no_profile_behavior != "EVIDENCE_ONLY_SCORE_AND_GRADE_NULL":
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
            "aggregation no-profile behavior drift",
        )
    payload = {
        "evidence_id": evidence.evidence_id,
        "aggregation_profile_ref": None,
        "overall_score": None,
        "grade": None,
        "mode": p.no_profile_behavior,
    }
    return P5AggregationResult(
        aggregation_profile_ref=None,
        overall_score=None,
        grade=None,
        mode=p.no_profile_behavior,
        evidence_id=evidence.evidence_id,
        logical_hash=canonical_hash(payload),
    )


def build_p5_assessment_revision(
    composition: P5CompositionSnapshot,
    *,
    evidence: P5TeamMissionEvidence,
    aggregation: P5AggregationResult,
    confidence: float,
    created_at_utc: str,
    approval_state: str = "DRAFT",
    supersedes: P5AssessmentRevision | None = None,
    policy: M8AuthorityPolicy | None = None,
) -> P5AssessmentRevision:
    p = policy or M8AuthorityPolicy.from_canonical()
    assert_composition_identity(composition)
    if evidence.composition_id != composition.composition_id:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_COMPOSITION_DRIFT",
            "evidence/composition mismatch",
        )
    if aggregation.evidence_id != evidence.evidence_id:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "aggregation/evidence mismatch",
        )
    if aggregation.overall_score is not None or aggregation.grade is not None:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_AGGREGATION_PROFILE_REQUIRED",
            "numeric P5 aggregate is not authorized",
        )
    if approval_state not in p.approval_states:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
            approval_state,
        )
    utc(created_at_utc, field="created_at_utc")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "confidence",
        )
    value = float(confidence)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "confidence",
        )
    supersedes_id: str | None = None
    if supersedes is not None:
        if supersedes.composition_id != composition.composition_id:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_COMPOSITION_DRIFT",
                "changed composition cannot silently supersede old series",
            )
        supersedes_id = supersedes.mission_assessment_id

    payload = {
        "composition_id": composition.composition_id,
        "session_id": composition.session_id,
        "mission_episode_id": composition.mission_episode_id,
        "team_id": composition.team_id,
        "assessment_spec_id": composition.assessment_spec_id,
        "assessment_spec_version": composition.assessment_spec_version,
        "participant_subject_keys": list(composition.participant_subject_keys),
        "world_snapshot_refs": list(composition.world_snapshot_refs),
        "objective_result_refs": list(evidence.objective_result_refs),
        "team_performance_evidence_id": evidence.evidence_id,
        "aggregation_profile_ref": None,
        "overall_score": None,
        "grade": None,
        "status": approval_state,
        "confidence": value,
        "evidence_set_id": evidence.evidence_set_id,
        "created_at_utc": created_at_utc,
        "supersedes_id": supersedes_id,
        "approval_state": approval_state,
        "claim_level": "TEAM_MISSION_EVIDENCE_ONLY",
        "validity_status": evidence.availability_status,
        "as_of_utc": evidence.as_of_utc,
    }
    digest = canonical_hash(payload)
    return P5AssessmentRevision(
        mission_assessment_id=str(uuid5(_P5_ASSESSMENT_NAMESPACE, digest)),
        composition_id=composition.composition_id,
        session_id=composition.session_id,
        mission_episode_id=composition.mission_episode_id,
        team_id=composition.team_id,
        assessment_spec_id=composition.assessment_spec_id,
        assessment_spec_version=composition.assessment_spec_version,
        participant_subject_keys=composition.participant_subject_keys,
        world_snapshot_refs=composition.world_snapshot_refs,
        objective_result_refs=evidence.objective_result_refs,
        team_performance_evidence_id=evidence.evidence_id,
        aggregation_profile_ref=None,
        overall_score=None,
        grade=None,
        status=approval_state,
        confidence=value,
        evidence_set_id=evidence.evidence_set_id,
        created_at_utc=created_at_utc,
        supersedes_id=supersedes_id,
        approval_state=approval_state,
        claim_level="TEAM_MISSION_EVIDENCE_ONLY",
        validity_status=evidence.availability_status,
        as_of_utc=evidence.as_of_utc,
        logical_content_hash=digest,
    )


class P5ApprovalWorkflow:
    """Deterministic idempotent approval workflow for exact P5 revisions."""

    def __init__(self, policy: M8AuthorityPolicy | None = None) -> None:
        self.policy = policy or M8AuthorityPolicy.from_canonical()
        self._requests: dict[str, tuple[str, P5ApprovalWorkflowResult]] = {}

    def transition(
        self,
        previous: P5AssessmentRevision,
        command: P5ApprovalCommand,
    ) -> P5ApprovalWorkflowResult:
        p = self.policy
        assert_write_allowed(
            "APPROVAL",
            viewer_role=command.viewer_role,
            scope_match=command.scope_match,
            policy=p,
        )
        exact_text(command.request_id, field="request_id", policy=p)
        exact_uuid(command.reviewer_actor_id, field="reviewer_actor_id", policy=p)
        exact_text(command.reason, field="reason", policy=p)
        utc(command.created_at_utc, field="created_at_utc")
        transition = f"{previous.approval_state}->{command.target_state}"
        terminal_correction = (
            previous.approval_state in {"APPROVED", "REJECTED"}
            and command.target_state == "DRAFT"
            and p.correction_after_terminal_creates_new_draft_revision
        )
        if (
            command.target_state not in p.approval_states
            or (
                transition not in p.approval_transitions
                and not terminal_correction
            )
        ):
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
                transition,
            )

        fingerprint = canonical_hash(
            {
                "request_id": command.request_id,
                "previous_revision_id": previous.mission_assessment_id,
                "target_state": command.target_state,
                "reviewer_actor_id": command.reviewer_actor_id,
                "reason": command.reason,
                "created_at_utc": command.created_at_utc,
            }
        )
        prior = self._requests.get(command.request_id)
        if prior is not None:
            if prior[0] != fingerprint:
                raise M8GovernanceError(
                    "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
                    "P5 approval request_id conflict",
                )
            return replace(prior[1], reused=True)

        payload = {
            "composition_id": previous.composition_id,
            "session_id": previous.session_id,
            "mission_episode_id": previous.mission_episode_id,
            "team_id": previous.team_id,
            "assessment_spec_id": previous.assessment_spec_id,
            "assessment_spec_version": previous.assessment_spec_version,
            "participant_subject_keys": list(previous.participant_subject_keys),
            "world_snapshot_refs": list(previous.world_snapshot_refs),
            "objective_result_refs": list(previous.objective_result_refs),
            "team_performance_evidence_id": previous.team_performance_evidence_id,
            "aggregation_profile_ref": None,
            "overall_score": None,
            "grade": None,
            "status": command.target_state,
            "confidence": previous.confidence,
            "evidence_set_id": previous.evidence_set_id,
            "created_at_utc": command.created_at_utc,
            "supersedes_id": previous.mission_assessment_id,
            "approval_state": command.target_state,
            "claim_level": previous.claim_level,
            "validity_status": previous.validity_status,
            "as_of_utc": previous.as_of_utc,
        }
        digest = canonical_hash(payload)
        revision = replace(
            previous,
            mission_assessment_id=str(uuid5(_P5_ASSESSMENT_NAMESPACE, digest)),
            status=command.target_state,
            created_at_utc=command.created_at_utc,
            supersedes_id=previous.mission_assessment_id,
            approval_state=command.target_state,
            logical_content_hash=digest,
        )
        audit_payload = {
            "actor_id": command.reviewer_actor_id,
            "action": p.approval_audit_action_p5,
            "object_type": "assessment.mission_assessment",
            "object_id": revision.mission_assessment_id,
            "reason": command.reason,
            "request_id": command.request_id,
            "created_at_utc": command.created_at_utc,
        }
        audit = P5AuditRecord(
            audit_key=f"P5_AUDIT_SHA256:{canonical_hash(audit_payload)}",
            actor_subject_key=pseudonymous_subject_key(
                command.reviewer_actor_id,
                policy=p,
            ),
            actor_id=command.reviewer_actor_id,
            action=p.approval_audit_action_p5,
            object_type="assessment.mission_assessment",
            object_id=revision.mission_assessment_id,
            reason=command.reason,
            request_id=command.request_id,
            created_at_utc=command.created_at_utc,
        )
        result = P5ApprovalWorkflowResult(
            revision=revision,
            audit=audit,
            reused=False,
        )
        self._requests[command.request_id] = (fingerprint, result)
        return result


def assert_no_team_result_copy_to_individual() -> None:
    assert_scope_copy_allowed("P5", "P4")
