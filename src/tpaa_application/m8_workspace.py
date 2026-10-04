"""M8 exact-revision P4/P5 Application workspace and runtime privacy enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from tpaa_assessment import (
    ApprovalCommand,
    InstructorAnnotationCommand,
    InstructorAnnotationRevision,
    P4AssessmentRevision,
    P4InstructorWorkflow,
    P5ApprovalCommand,
    P5ApprovalWorkflow,
    P5AssessmentRevision,
)
from tpaa_context import (
    M8AdmissionEvidence,
    M8AuthorityPolicy,
    M8GovernanceError,
    assert_capability_claim_allowed,
    canonical_hash,
    project_direct_actor_id,
    pseudonymous_subject_key,
)

from .m7_workspace import M7WorkspaceQuery, M7WorkspaceService
from .security_audit import SecurityAuditRecord, SecurityAuditSink


class M8ApplicationError(RuntimeError):
    """Fail-closed exact-revision M8 Application error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class M8ViewerContext:
    viewer_role: str
    viewer_actor_id: str | None
    scope_match: bool
    privileged_identity_authorized: bool = False
    visibility_authorized: bool = False
    export_authorized: bool = False


@dataclass(frozen=True)
class M8P4Query:
    actor_assessment_id: str
    viewer: M8ViewerContext


@dataclass(frozen=True)
class M8P5Query:
    mission_assessment_id: str
    viewer: M8ViewerContext


@dataclass(frozen=True)
class M8WorkspaceQuery:
    actor_assessment_id: str
    mission_assessment_id: str
    viewer: M8ViewerContext


@dataclass(frozen=True)
class M8AnnotationMutation:
    target_p4_revision_id: str
    previous_annotation_id: str | None
    request_id: str
    base_release_id: str
    annotation_type: str
    start_session_time_us: int | None
    end_session_time_us: int | None
    body_text: str
    visibility: str
    reason: str
    created_at_utc: str
    viewer: M8ViewerContext


@dataclass(frozen=True)
class M8ApprovalMutation:
    target_revision_id: str
    request_id: str
    target_state: str
    reason: str
    created_at_utc: str
    viewer: M8ViewerContext


@dataclass(frozen=True)
class M8SecurityAuditEvent:
    principal_key: str
    action: str
    object_ref: str
    outcome: str


class M8AircraftContextPort(Protocol):
    def exact_context(
        self,
        *,
        twin_revision_id: str,
        estimate_id: str,
    ) -> dict[str, object]:
        """Return exact P1/P2/P3 aircraft context without recomputation."""


class M7AircraftContextAdapter:
    def __init__(self, service: M7WorkspaceService) -> None:
        self._service = service

    def exact_context(
        self,
        *,
        twin_revision_id: str,
        estimate_id: str,
    ) -> dict[str, object]:
        return self._service.workspace(
            M7WorkspaceQuery(
                twin_revision_id=twin_revision_id,
                estimate_id=estimate_id,
            )
        )


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M8ApplicationError("M8_EXACT_ID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise M8ApplicationError("M8_EXACT_ID_INVALID", field)
    return value


class M8AssessmentRepository(Protocol):
    """Engine-neutral P4/P5 exact-revision read/write repository port."""

    def register_p4(self, revision: P4AssessmentRevision) -> None:
        """Persist one immutable P4 revision."""

    def register_p5(self, revision: P5AssessmentRevision) -> None:
        """Persist one immutable P5 revision."""

    def register_annotation(self, revision: InstructorAnnotationRevision) -> None:
        """Persist one immutable instructor annotation revision."""

    def exact_p4(self, revision_id: str) -> P4AssessmentRevision:
        """Return an exact P4 revision."""

    def exact_p5(self, revision_id: str) -> P5AssessmentRevision:
        """Return an exact P5 revision."""

    def exact_annotation(self, annotation_id: str) -> InstructorAnnotationRevision:
        """Return an exact annotation revision."""


class InMemoryM8AssessmentRepository:
    """Immutable exact-ID P4/P5 candidate repository for Application/API wiring."""

    def __init__(self) -> None:
        self._p4: dict[str, P4AssessmentRevision] = {}
        self._p5: dict[str, P5AssessmentRevision] = {}
        self._annotations: dict[str, InstructorAnnotationRevision] = {}

    def register_p4(self, revision: P4AssessmentRevision) -> None:
        _uuid(revision.actor_assessment_id, field="actor_assessment_id")
        current = self._p4.get(revision.actor_assessment_id)
        if current is not None and current != revision:
            raise M8ApplicationError(
                "M8_IMMUTABLE_CONFLICT",
                revision.actor_assessment_id,
            )
        self._p4[revision.actor_assessment_id] = revision

    def register_p5(self, revision: P5AssessmentRevision) -> None:
        _uuid(revision.mission_assessment_id, field="mission_assessment_id")
        current = self._p5.get(revision.mission_assessment_id)
        if current is not None and current != revision:
            raise M8ApplicationError(
                "M8_IMMUTABLE_CONFLICT",
                revision.mission_assessment_id,
            )
        self._p5[revision.mission_assessment_id] = revision

    def register_annotation(self, revision: InstructorAnnotationRevision) -> None:
        _uuid(revision.annotation_id, field="annotation_id")
        current = self._annotations.get(revision.annotation_id)
        if current is not None and current != revision:
            raise M8ApplicationError(
                "M8_IMMUTABLE_CONFLICT",
                revision.annotation_id,
            )
        self._annotations[revision.annotation_id] = revision

    def exact_p4(self, revision_id: str) -> P4AssessmentRevision:
        _uuid(revision_id, field="actor_assessment_id")
        try:
            return self._p4[revision_id]
        except KeyError as exc:
            raise M8ApplicationError("M8_P4_REVISION_NOT_FOUND", revision_id) from exc

    def exact_p5(self, revision_id: str) -> P5AssessmentRevision:
        _uuid(revision_id, field="mission_assessment_id")
        try:
            return self._p5[revision_id]
        except KeyError as exc:
            raise M8ApplicationError("M8_P5_REVISION_NOT_FOUND", revision_id) from exc

    def exact_annotation(self, annotation_id: str) -> InstructorAnnotationRevision:
        _uuid(annotation_id, field="annotation_id")
        try:
            return self._annotations[annotation_id]
        except KeyError as exc:
            raise M8ApplicationError(
                "M8_ANNOTATION_NOT_FOUND",
                annotation_id,
            ) from exc


class M8WorkspaceService:
    """Admission-gated exact P4/P5 read/write service with role-aware projection."""

    def __init__(
        self,
        repository: M8AssessmentRepository,
        *,
        admission_evidence: M8AdmissionEvidence | None = None,
        aircraft_context: M8AircraftContextPort | None = None,
        p4_workflow: P4InstructorWorkflow | None = None,
        p5_workflow: P5ApprovalWorkflow | None = None,
        policy: M8AuthorityPolicy | None = None,
        security_audit_sink: SecurityAuditSink | None = None,
    ) -> None:
        self._repository = repository
        self._admission_evidence = admission_evidence
        self._aircraft_context = aircraft_context
        self._policy = policy or M8AuthorityPolicy.from_canonical()
        self._p4_workflow = p4_workflow or P4InstructorWorkflow(self._policy)
        self._p5_workflow = p5_workflow or P5ApprovalWorkflow(self._policy)
        self._security_events: list[M8SecurityAuditEvent] = []
        self._security_audit_sink = security_audit_sink

    def _assert_admitted(self, phase: str) -> None:
        try:
            assert_capability_claim_allowed(
                phase,
                evidence=self._admission_evidence,
                policy=self._policy,
            )
        except M8GovernanceError as exc:
            raise M8ApplicationError("M8_P4_P5_NOT_ADMITTED", exc.detail) from exc

    def _principal_key(self, viewer: M8ViewerContext) -> str:
        if viewer.viewer_actor_id is None:
            return f"ROLE:{viewer.viewer_role}"
        try:
            return pseudonymous_subject_key(
                viewer.viewer_actor_id,
                policy=self._policy,
            )
        except M8GovernanceError as exc:
            raise M8ApplicationError(exc.code, exc.detail) from exc

    def _audit(
        self,
        viewer: M8ViewerContext,
        *,
        action: str,
        object_ref: str,
        outcome: str,
        request_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        principal_key = self._principal_key(viewer)
        self._security_events.append(
            M8SecurityAuditEvent(
                principal_key=principal_key,
                action=action,
                object_ref=object_ref,
                outcome=outcome,
            )
        )
        if self._security_audit_sink is not None:
            self._security_audit_sink.record(
                SecurityAuditRecord(
                    actor_id=viewer.viewer_actor_id,
                    principal_key=principal_key,
                    action=action,
                    object_type="M8_SECURITY_EVENT",
                    object_id=object_ref,
                    outcome=outcome,
                    request_id=request_id,
                    reason=reason or action,
                    details={
                        "viewer_role": viewer.viewer_role,
                        "scope_match": viewer.scope_match,
                        "privileged_identity_authorized": (
                            viewer.privileged_identity_authorized
                        ),
                        "visibility_authorized": viewer.visibility_authorized,
                        "export_authorized": viewer.export_authorized,
                    },
                )
            )

    def security_events(self) -> tuple[M8SecurityAuditEvent, ...]:
        return tuple(self._security_events)

    def _project_p4(
        self,
        revision: P4AssessmentRevision,
        viewer: M8ViewerContext,
    ) -> dict[str, object]:
        try:
            actor_id = project_direct_actor_id(
                revision.actor_id,
                viewer_role=viewer.viewer_role,
                viewer_actor_id=viewer.viewer_actor_id,
                scope_match=viewer.scope_match,
                privileged_identity_authorized=(
                    viewer.privileged_identity_authorized
                ),
                policy=self._policy,
            )
        except M8GovernanceError as exc:
            raise M8ApplicationError(exc.code, exc.detail) from exc
        return {
            "layer": "P4_INDIVIDUAL_HUMAN_MACHINE",
            "actor_assessment_id": revision.actor_assessment_id,
            "subject_context_id": revision.subject_context_id,
            "subject_key": revision.subject_key,
            "actor_id": actor_id,
            "role_code": revision.role_code,
            "seat_code": revision.seat_code,
            "function_code": revision.function_code,
            "session_id": revision.session_id,
            "episode_id": revision.episode_id,
            "aircraft_id": revision.aircraft_id,
            "twin_revision_id": revision.twin_revision_id,
            "p3_estimate_id": revision.p3_estimate_id,
            "assessment_spec_id": revision.assessment_spec_id,
            "assessment_spec_version": revision.assessment_spec_version,
            "world_refs": list(revision.world_refs),
            "machine_evidence_ids": list(revision.machine_evidence_ids),
            "instructor_annotation_ids": list(
                revision.instructor_annotation_ids
            ),
            "score": revision.score,
            "grade": revision.grade,
            "approval_state": revision.approval_state,
            "confidence": revision.confidence,
            "p3_claim_level": revision.p3_claim_level,
            "p3_validity_status": revision.p3_validity_status,
            "p3_as_of_utc": revision.p3_as_of_utc,
            "uncertainty": {
                "lower": revision.uncertainty_lower,
                "upper": revision.uncertainty_upper,
            },
            "created_at_utc": revision.created_at_utc,
            "supersedes_id": revision.supersedes_id,
            "logical_content_hash": revision.logical_content_hash,
        }

    @staticmethod
    def _project_p5(revision: P5AssessmentRevision) -> dict[str, object]:
        return {
            "layer": "P5_TEAM_MISSION",
            "mission_assessment_id": revision.mission_assessment_id,
            "composition_id": revision.composition_id,
            "session_id": revision.session_id,
            "mission_episode_id": revision.mission_episode_id,
            "team_id": revision.team_id,
            "assessment_spec_id": revision.assessment_spec_id,
            "assessment_spec_version": revision.assessment_spec_version,
            "participant_subject_keys": list(
                revision.participant_subject_keys
            ),
            "world_snapshot_refs": list(revision.world_snapshot_refs),
            "objective_result_refs": list(revision.objective_result_refs),
            "team_performance_evidence_id": (
                revision.team_performance_evidence_id
            ),
            "aggregation_profile_ref": revision.aggregation_profile_ref,
            "overall_score": revision.overall_score,
            "grade": revision.grade,
            "approval_state": revision.approval_state,
            "confidence": revision.confidence,
            "claim_level": revision.claim_level,
            "validity_status": revision.validity_status,
            "as_of_utc": revision.as_of_utc,
            "created_at_utc": revision.created_at_utc,
            "supersedes_id": revision.supersedes_id,
            "logical_content_hash": revision.logical_content_hash,
        }

    def p4(self, query: M8P4Query) -> dict[str, object]:
        self._assert_admitted("P4")
        revision = self._repository.exact_p4(query.actor_assessment_id)
        projected = self._project_p4(revision, query.viewer)
        self._audit(
            query.viewer,
            action="P4_READ",
            object_ref=revision.actor_assessment_id,
            outcome="ALLOW",
        )
        return projected

    def p5(self, query: M8P5Query) -> dict[str, object]:
        self._assert_admitted("P5")
        revision = self._repository.exact_p5(query.mission_assessment_id)
        projected = self._project_p5(revision)
        self._audit(
            query.viewer,
            action="P5_READ",
            object_ref=revision.mission_assessment_id,
            outcome="ALLOW",
        )
        return projected

    def workspace(self, query: M8WorkspaceQuery) -> dict[str, object]:
        self._assert_admitted("P4")
        self._assert_admitted("P5")
        p4 = self._repository.exact_p4(query.actor_assessment_id)
        p5 = self._repository.exact_p5(query.mission_assessment_id)
        if p4.subject_key not in p5.participant_subject_keys:
            raise M8ApplicationError(
                "M8_P4_P5_SCOPE_MISMATCH",
                p4.subject_key,
            )
        if p4.p3_estimate_id is None or self._aircraft_context is None:
            raise M8ApplicationError(
                "M8_P3_CONTEXT_REQUIRED",
                p4.actor_assessment_id,
            )
        aircraft = self._aircraft_context.exact_context(
            twin_revision_id=p4.twin_revision_id,
            estimate_id=p4.p3_estimate_id,
        )
        product = {
            "identity": {
                "actor_assessment_id": p4.actor_assessment_id,
                "mission_assessment_id": p5.mission_assessment_id,
                "composition_id": p5.composition_id,
            },
            "aircraft_capability_context": aircraft,
            "p4": self._project_p4(p4, query.viewer),
            "p5": self._project_p5(p5),
        }
        result = {
            **product,
            "logical_product_hash": canonical_hash(product),
        }
        self._audit(
            query.viewer,
            action="M8_WORKSPACE_READ",
            object_ref=(
                f"{p4.actor_assessment_id}:{p5.mission_assessment_id}"
            ),
            outcome="ALLOW",
        )
        return result

    def annotate_p4(
        self,
        mutation: M8AnnotationMutation,
    ) -> dict[str, object]:
        self._assert_admitted("P4")
        target = self._repository.exact_p4(mutation.target_p4_revision_id)
        actor_id = mutation.viewer.viewer_actor_id
        if actor_id is None:
            raise M8ApplicationError(
                "FAIL_CLOSED_P4_P5_APPROVAL_NOT_AUTHORIZED",
                "instructor actor identity required",
            )
        previous = (
            self._repository.exact_annotation(mutation.previous_annotation_id)
            if mutation.previous_annotation_id is not None
            else None
        )
        try:
            result = self._p4_workflow.annotate(
                InstructorAnnotationCommand(
                    request_id=mutation.request_id,
                    author_actor_id=actor_id,
                    viewer_role=mutation.viewer.viewer_role,
                    scope_match=mutation.viewer.scope_match,
                    subject_context_id=target.subject_context_id,
                    base_release_id=mutation.base_release_id,
                    session_id=target.session_id,
                    episode_id=target.episode_id,
                    stage_id=None,
                    annotation_type=mutation.annotation_type,
                    start_session_time_us=mutation.start_session_time_us,
                    end_session_time_us=mutation.end_session_time_us,
                    body_text=mutation.body_text,
                    visibility=mutation.visibility,
                    evidence_set_id=target.evidence_set_id,
                    reason=mutation.reason,
                    created_at_utc=mutation.created_at_utc,
                ),
                previous=previous,
            )
        except M8GovernanceError as exc:
            self._audit(
                mutation.viewer,
                action="P4_ANNOTATION_WRITE",
                object_ref=target.actor_assessment_id,
                outcome="DENY",
                request_id=mutation.request_id,
                reason=mutation.reason,
            )
            raise M8ApplicationError(exc.code, exc.detail) from exc
        self._repository.register_annotation(result.revision)
        self._audit(
            mutation.viewer,
            action="P4_ANNOTATION_WRITE",
            object_ref=result.revision.annotation_id,
            outcome="ALLOW",
            request_id=mutation.request_id,
            reason=mutation.reason,
        )
        return {
            "annotation_id": result.revision.annotation_id,
            "revision_no": result.revision.revision_no,
            "supersedes_annotation_id": (
                result.revision.supersedes_annotation_id
            ),
            "status": result.revision.status,
            "request_id": result.audit.request_id,
            "reused": result.reused,
        }

    def approve_p4(self, mutation: M8ApprovalMutation) -> dict[str, object]:
        self._assert_admitted("P4")
        previous = self._repository.exact_p4(mutation.target_revision_id)
        actor_id = mutation.viewer.viewer_actor_id
        if actor_id is None:
            raise M8ApplicationError(
                "FAIL_CLOSED_P4_P5_APPROVAL_NOT_AUTHORIZED",
                "reviewer actor identity required",
            )
        try:
            result = self._p4_workflow.transition_approval(
                previous,
                ApprovalCommand(
                    request_id=mutation.request_id,
                    reviewer_actor_id=actor_id,
                    viewer_role=mutation.viewer.viewer_role,
                    scope_match=mutation.viewer.scope_match,
                    target_state=mutation.target_state,
                    reason=mutation.reason,
                    created_at_utc=mutation.created_at_utc,
                ),
            )
        except M8GovernanceError as exc:
            self._audit(
                mutation.viewer,
                action="P4_APPROVAL_WRITE",
                object_ref=previous.actor_assessment_id,
                outcome="DENY",
                request_id=mutation.request_id,
                reason=mutation.reason,
            )
            raise M8ApplicationError(exc.code, exc.detail) from exc
        self._repository.register_p4(result.revision)
        self._audit(
            mutation.viewer,
            action="P4_APPROVAL_WRITE",
            object_ref=result.revision.actor_assessment_id,
            outcome="ALLOW",
            request_id=mutation.request_id,
            reason=mutation.reason,
        )
        return {
            "actor_assessment_id": result.revision.actor_assessment_id,
            "approval_state": result.revision.approval_state,
            "supersedes_id": result.revision.supersedes_id,
            "request_id": result.audit.request_id,
            "reused": result.reused,
        }

    def approve_p5(self, mutation: M8ApprovalMutation) -> dict[str, object]:
        self._assert_admitted("P5")
        previous = self._repository.exact_p5(mutation.target_revision_id)
        actor_id = mutation.viewer.viewer_actor_id
        if actor_id is None:
            raise M8ApplicationError(
                "FAIL_CLOSED_P4_P5_APPROVAL_NOT_AUTHORIZED",
                "reviewer actor identity required",
            )
        try:
            result = self._p5_workflow.transition(
                previous,
                P5ApprovalCommand(
                    request_id=mutation.request_id,
                    reviewer_actor_id=actor_id,
                    viewer_role=mutation.viewer.viewer_role,
                    scope_match=mutation.viewer.scope_match,
                    target_state=mutation.target_state,
                    reason=mutation.reason,
                    created_at_utc=mutation.created_at_utc,
                ),
            )
        except M8GovernanceError as exc:
            self._audit(
                mutation.viewer,
                action="P5_APPROVAL_WRITE",
                object_ref=previous.mission_assessment_id,
                outcome="DENY",
                request_id=mutation.request_id,
                reason=mutation.reason,
            )
            raise M8ApplicationError(exc.code, exc.detail) from exc
        self._repository.register_p5(result.revision)
        self._audit(
            mutation.viewer,
            action="P5_APPROVAL_WRITE",
            object_ref=result.revision.mission_assessment_id,
            outcome="ALLOW",
            request_id=mutation.request_id,
            reason=mutation.reason,
        )
        return {
            "mission_assessment_id": result.revision.mission_assessment_id,
            "approval_state": result.revision.approval_state,
            "supersedes_id": result.revision.supersedes_id,
            "request_id": result.audit.request_id,
            "reused": result.reused,
        }

    def export_exact(
        self,
        query: M8WorkspaceQuery,
    ) -> dict[str, object]:
        viewer = query.viewer
        if (
            viewer.viewer_role != "ADMIN_AUDITOR"
            or not viewer.scope_match
            or not viewer.export_authorized
            or not viewer.privileged_identity_authorized
        ):
            self._audit(
                viewer,
                action="M8_EXPORT",
                object_ref=query.actor_assessment_id,
                outcome="DENY",
            )
            raise M8ApplicationError(
                "FAIL_CLOSED_P4_P5_DIRECT_IDENTITY_NOT_AUTHORIZED",
                "explicit privileged export authorization required",
            )
        payload = self.workspace(query)
        self._audit(
            viewer,
            action="M8_EXPORT",
            object_ref=query.actor_assessment_id,
            outcome="ALLOW",
        )
        return payload
