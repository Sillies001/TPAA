"""M8 Batch 2 immutable instructor workflow and P4 assessment revisions."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from uuid import UUID, uuid5

from tpaa_context import (
    M8AuthorityPolicy,
    M8GovernanceError,
    P3ClaimEnvelope,
    assert_p3_claim_preserved,
    assert_write_allowed,
    canonical_hash,
    exact_text,
    exact_uuid,
    pseudonymous_subject_key,
    utc,
)

from .p4_evidence import P4HumanMachineEvidence
from .p4_subject import P4SubjectContext

_ANNOTATION_NAMESPACE = UUID("612a4a2a-2107-5fe0-82f0-386136b3b9e9")
_ASSESSMENT_NAMESPACE = UUID("7be38d30-d97b-57d7-9c05-9ddc3cd2c892")


@dataclass(frozen=True)
class P4AuditRecord:
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
class InstructorAnnotationCommand:
    request_id: str
    author_actor_id: str
    viewer_role: str
    scope_match: bool
    subject_context_id: str
    base_release_id: str
    session_id: str
    episode_id: str | None
    stage_id: str | None
    annotation_type: str
    start_session_time_us: int | None
    end_session_time_us: int | None
    body_text: str
    visibility: str
    evidence_set_id: str | None
    reason: str
    created_at_utc: str


@dataclass(frozen=True)
class InstructorAnnotationRevision:
    annotation_id: str
    base_release_id: str
    session_id: str
    episode_id: str | None
    stage_id: str | None
    author_subject_key: str
    author_id: str
    annotation_type: str
    start_session_time_us: int | None
    end_session_time_us: int | None
    body_text: str
    visibility: str
    status: str
    revision_no: int
    supersedes_annotation_id: str | None
    evidence_set_id: str | None
    subject_context_id: str
    created_at_utc: str
    content_hash: str


@dataclass(frozen=True)
class AnnotationWorkflowResult:
    revision: InstructorAnnotationRevision
    audit: P4AuditRecord
    reused: bool


@dataclass(frozen=True)
class P4AssessmentRevision:
    actor_assessment_id: str
    subject_context_id: str
    subject_key: str
    actor_id: str
    role_code: str
    seat_code: str | None
    function_code: str | None
    session_id: str
    episode_id: str
    aircraft_id: str | None
    twin_revision_id: str
    p3_estimate_id: str | None
    assessment_spec_id: str
    assessment_spec_version: str
    role_model_version: str
    world_refs: tuple[str, ...]
    machine_evidence_ids: tuple[str, ...]
    instructor_annotation_ids: tuple[str, ...]
    score: None
    grade: None
    status: str
    confidence: float
    evidence_set_id: str
    created_at_utc: str
    supersedes_id: str | None
    approval_state: str
    p3_claim_level: str
    p3_validity_status: str
    p3_as_of_utc: str
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    logical_content_hash: str


@dataclass(frozen=True)
class ApprovalCommand:
    request_id: str
    reviewer_actor_id: str
    viewer_role: str
    scope_match: bool
    target_state: str
    reason: str
    created_at_utc: str


@dataclass(frozen=True)
class ApprovalWorkflowResult:
    revision: P4AssessmentRevision
    audit: P4AuditRecord
    reused: bool


class P4InstructorWorkflow:
    """In-memory deterministic workflow model with request-id idempotency."""

    def __init__(self, policy: M8AuthorityPolicy | None = None) -> None:
        self.policy = policy or M8AuthorityPolicy.from_canonical()
        self._annotations: dict[str, tuple[str, AnnotationWorkflowResult]] = {}
        self._approvals: dict[str, tuple[str, ApprovalWorkflowResult]] = {}

    def annotate(
        self,
        command: InstructorAnnotationCommand,
        *,
        previous: InstructorAnnotationRevision | None = None,
    ) -> AnnotationWorkflowResult:
        p = self.policy
        assert_write_allowed(
            "ANNOTATION",
            viewer_role=command.viewer_role,
            scope_match=command.scope_match,
            policy=p,
        )
        exact_text(command.request_id, field="request_id", policy=p)
        exact_uuid(command.author_actor_id, field="author_actor_id", policy=p)
        exact_text(command.subject_context_id, field="subject_context_id", policy=p)
        exact_uuid(command.base_release_id, field="base_release_id", policy=p)
        exact_uuid(command.session_id, field="session_id", policy=p)
        if command.episode_id is not None:
            exact_uuid(command.episode_id, field="episode_id", policy=p)
        if command.stage_id is not None:
            exact_uuid(command.stage_id, field="stage_id", policy=p)
        if command.evidence_set_id is not None:
            exact_uuid(command.evidence_set_id, field="evidence_set_id", policy=p)
        exact_text(command.annotation_type, field="annotation_type", policy=p)
        exact_text(command.body_text, field="body_text", policy=p)
        exact_text(command.visibility, field="visibility", policy=p)
        exact_text(command.reason, field="reason", policy=p)
        utc(command.created_at_utc, field="created_at_utc")
        _validate_interval(
            command.start_session_time_us,
            command.end_session_time_us,
        )

        revision_no = 1 if previous is None else previous.revision_no + 1
        supersedes = None if previous is None else previous.annotation_id
        if previous is not None:
            if (
                previous.subject_context_id != command.subject_context_id
                or previous.base_release_id != command.base_release_id
                or previous.session_id != command.session_id
            ):
                raise M8GovernanceError(
                    "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                    "annotation revision target drift",
                )
            if p.annotation_physical_delete_forbidden is not True:
                raise M8GovernanceError(
                    "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
                    "annotation delete authority drift",
                )

        payload = {
            "base_release_id": command.base_release_id,
            "session_id": command.session_id,
            "episode_id": command.episode_id,
            "stage_id": command.stage_id,
            "author_subject_key": pseudonymous_subject_key(
                command.author_actor_id,
                policy=p,
            ),
            "author_id": command.author_actor_id,
            "annotation_type": command.annotation_type,
            "start_session_time_us": command.start_session_time_us,
            "end_session_time_us": command.end_session_time_us,
            "body_text": command.body_text,
            "visibility": command.visibility,
            "status": "ACTIVE",
            "revision_no": revision_no,
            "supersedes_annotation_id": supersedes,
            "evidence_set_id": command.evidence_set_id,
            "subject_context_id": command.subject_context_id,
            "created_at_utc": command.created_at_utc,
        }
        fingerprint = canonical_hash(
            {"request_id": command.request_id, "payload": payload}
        )
        prior = self._annotations.get(command.request_id)
        if prior is not None:
            if prior[0] != fingerprint:
                raise M8GovernanceError(
                    "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                    "annotation request_id conflict",
                )
            return replace(prior[1], reused=True)

        content_hash = canonical_hash(payload)
        annotation_id = str(uuid5(_ANNOTATION_NAMESPACE, content_hash))
        revision = InstructorAnnotationRevision(
            annotation_id=annotation_id,
            base_release_id=command.base_release_id,
            session_id=command.session_id,
            episode_id=command.episode_id,
            stage_id=command.stage_id,
            author_subject_key=pseudonymous_subject_key(
                command.author_actor_id,
                policy=p,
            ),
            author_id=command.author_actor_id,
            annotation_type=command.annotation_type,
            start_session_time_us=command.start_session_time_us,
            end_session_time_us=command.end_session_time_us,
            body_text=command.body_text,
            visibility=command.visibility,
            status="ACTIVE",
            revision_no=revision_no,
            supersedes_annotation_id=supersedes,
            evidence_set_id=command.evidence_set_id,
            subject_context_id=command.subject_context_id,
            created_at_utc=command.created_at_utc,
            content_hash=content_hash,
        )
        action = "P4_ANNOTATION_CREATE" if previous is None else "P4_ANNOTATION_REVISE"
        audit = _audit(
            actor_id=command.author_actor_id,
            action=action,
            object_type="debrief.annotation",
            object_id=annotation_id,
            reason=command.reason,
            request_id=command.request_id,
            created_at_utc=command.created_at_utc,
            policy=p,
        )
        result = AnnotationWorkflowResult(revision=revision, audit=audit, reused=False)
        self._annotations[command.request_id] = (fingerprint, result)
        return result

    def transition_approval(
        self,
        previous: P4AssessmentRevision,
        command: ApprovalCommand,
    ) -> ApprovalWorkflowResult:
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
        if command.target_state not in p.approval_states:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
                command.target_state,
            )
        transition = f"{previous.approval_state}->{command.target_state}"
        terminal_correction = (
            previous.approval_state in {"APPROVED", "REJECTED"}
            and command.target_state == "DRAFT"
            and p.correction_after_terminal_creates_new_draft_revision
        )
        if transition not in p.approval_transitions and not terminal_correction:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
                transition,
            )

        fingerprint = canonical_hash(
            {
                "request_id": command.request_id,
                "previous_revision_id": previous.actor_assessment_id,
                "target_state": command.target_state,
                "reviewer_actor_id": command.reviewer_actor_id,
                "reason": command.reason,
                "created_at_utc": command.created_at_utc,
            }
        )
        prior = self._approvals.get(command.request_id)
        if prior is not None:
            if prior[0] != fingerprint:
                raise M8GovernanceError(
                    "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
                    "approval request_id conflict",
                )
            return replace(prior[1], reused=True)

        revision = _assessment_with_state(
            previous,
            target_state=command.target_state,
            supersedes_id=previous.actor_assessment_id,
            created_at_utc=command.created_at_utc,
        )
        audit = _audit(
            actor_id=command.reviewer_actor_id,
            action=p.approval_audit_action_p4,
            object_type="assessment.actor_assessment",
            object_id=revision.actor_assessment_id,
            reason=command.reason,
            request_id=command.request_id,
            created_at_utc=command.created_at_utc,
            policy=p,
        )
        result = ApprovalWorkflowResult(revision=revision, audit=audit, reused=False)
        self._approvals[command.request_id] = (fingerprint, result)
        return result


def _validate_interval(start: int | None, end: int | None) -> None:
    if (start is None) != (end is None):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "annotation interval must be jointly present or absent",
        )
    if start is not None:
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or start >= end
        ):
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                f"annotation interval=[{start!r},{end!r})",
            )


def _audit(
    *,
    actor_id: str,
    action: str,
    object_type: str,
    object_id: str,
    reason: str,
    request_id: str,
    created_at_utc: str,
    policy: M8AuthorityPolicy,
) -> P4AuditRecord:
    payload = {
        "actor_id": actor_id,
        "action": action,
        "object_type": object_type,
        "object_id": object_id,
        "reason": reason,
        "request_id": request_id,
        "created_at_utc": created_at_utc,
    }
    return P4AuditRecord(
        audit_key=f"P4_AUDIT_SHA256:{canonical_hash(payload)}",
        actor_subject_key=pseudonymous_subject_key(actor_id, policy=policy),
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        reason=reason,
        request_id=request_id,
        created_at_utc=created_at_utc,
    )


def build_p4_assessment_revision(
    subject: P4SubjectContext,
    *,
    evidence: tuple[P4HumanMachineEvidence, ...],
    annotations: tuple[InstructorAnnotationRevision, ...],
    p3_claim: P3ClaimEnvelope,
    confidence: float,
    created_at_utc: str,
    approval_state: str = "DRAFT",
    supersedes_id: str | None = None,
    policy: M8AuthorityPolicy | None = None,
) -> P4AssessmentRevision:
    p = policy or M8AuthorityPolicy.from_canonical()
    if approval_state not in p.approval_states:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
            approval_state,
        )
    if not evidence:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "P4 assessment requires machine evidence",
        )
    utc(created_at_utc, field="created_at_utc")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "confidence",
        )
    confidence_value = float(confidence)
    if not math.isfinite(confidence_value) or not 0.0 <= confidence_value <= 1.0:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "confidence",
        )
    if p3_claim.as_of_utc != subject.as_of_utc:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "P3 as_of must equal subject context as_of",
        )
    assert_p3_claim_preserved(p3_claim, p3_claim)
    if (p3_claim.uncertainty_lower is None) != (
        p3_claim.uncertainty_upper is None
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "uncertainty bounds must be jointly present or absent",
        )
    if p3_claim.uncertainty_lower is not None:
        assert p3_claim.uncertainty_upper is not None
        if (
            not math.isfinite(p3_claim.uncertainty_lower)
            or not math.isfinite(p3_claim.uncertainty_upper)
            or p3_claim.uncertainty_lower > p3_claim.uncertainty_upper
        ):
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                "uncertainty bounds invalid",
            )
    for item in evidence:
        if (
            item.subject_context_id != subject.subject_context_id
            or item.subject_key != subject.subject_key
            or item.as_of_utc != subject.as_of_utc
            or item.origin != "MACHINE"
        ):
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                f"evidence binding drift={item.evidence_id}",
            )
    for annotation in annotations:
        if annotation.subject_context_id != subject.subject_context_id:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                f"annotation binding drift={annotation.annotation_id}",
            )
    if supersedes_id is not None:
        exact_uuid(supersedes_id, field="supersedes_id", policy=p)

    evidence_ids = tuple(sorted(item.evidence_id for item in evidence))
    annotation_ids = tuple(sorted(item.annotation_id for item in annotations))
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
        "instructor_annotation_ids": list(annotation_ids),
        "score": None,
        "grade": None,
        "status": approval_state,
        "confidence": confidence_value,
        "evidence_set_id": subject.evidence_set_id,
        "created_at_utc": created_at_utc,
        "supersedes_id": supersedes_id,
        "approval_state": approval_state,
        "p3_claim_level": p3_claim.claim_level,
        "p3_validity_status": p3_claim.validity_status,
        "p3_as_of_utc": p3_claim.as_of_utc,
        "uncertainty_lower": p3_claim.uncertainty_lower,
        "uncertainty_upper": p3_claim.uncertainty_upper,
    }
    digest = canonical_hash(payload)
    return P4AssessmentRevision(
        actor_assessment_id=str(uuid5(_ASSESSMENT_NAMESPACE, digest)),
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
        machine_evidence_ids=evidence_ids,
        instructor_annotation_ids=annotation_ids,
        score=None,
        grade=None,
        status=approval_state,
        confidence=confidence_value,
        evidence_set_id=subject.evidence_set_id,
        created_at_utc=created_at_utc,
        supersedes_id=supersedes_id,
        approval_state=approval_state,
        p3_claim_level=p3_claim.claim_level,
        p3_validity_status=p3_claim.validity_status,
        p3_as_of_utc=p3_claim.as_of_utc,
        uncertainty_lower=p3_claim.uncertainty_lower,
        uncertainty_upper=p3_claim.uncertainty_upper,
        logical_content_hash=digest,
    )


def _assessment_with_state(
    previous: P4AssessmentRevision,
    *,
    target_state: str,
    supersedes_id: str,
    created_at_utc: str,
) -> P4AssessmentRevision:
    payload = {
        "subject_context_id": previous.subject_context_id,
        "subject_key": previous.subject_key,
        "actor_id": previous.actor_id,
        "role_code": previous.role_code,
        "seat_code": previous.seat_code,
        "function_code": previous.function_code,
        "session_id": previous.session_id,
        "episode_id": previous.episode_id,
        "aircraft_id": previous.aircraft_id,
        "twin_revision_id": previous.twin_revision_id,
        "p3_estimate_id": previous.p3_estimate_id,
        "assessment_spec_id": previous.assessment_spec_id,
        "assessment_spec_version": previous.assessment_spec_version,
        "role_model_version": previous.role_model_version,
        "world_refs": list(previous.world_refs),
        "machine_evidence_ids": list(previous.machine_evidence_ids),
        "instructor_annotation_ids": list(previous.instructor_annotation_ids),
        "score": None,
        "grade": None,
        "status": target_state,
        "confidence": previous.confidence,
        "evidence_set_id": previous.evidence_set_id,
        "created_at_utc": created_at_utc,
        "supersedes_id": supersedes_id,
        "approval_state": target_state,
        "p3_claim_level": previous.p3_claim_level,
        "p3_validity_status": previous.p3_validity_status,
        "p3_as_of_utc": previous.p3_as_of_utc,
        "uncertainty_lower": previous.uncertainty_lower,
        "uncertainty_upper": previous.uncertainty_upper,
    }
    digest = canonical_hash(payload)
    return replace(
        previous,
        actor_assessment_id=str(uuid5(_ASSESSMENT_NAMESPACE, digest)),
        status=target_state,
        created_at_utc=created_at_utc,
        supersedes_id=supersedes_id,
        approval_state=target_state,
        logical_content_hash=digest,
    )
