"""PIQB B2 exact P4/P5 mapping over adopted DB 1.9 canonical relations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from tpaa_assessment import (
    InstructorAnnotationRevision,
    P4AssessmentRevision,
    P4SubjectContext,
    P5AssessmentRevision,
    assert_p4_subject_context_identity,
)
from tpaa_context import canonical_hash, pseudonymous_subject_key
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_world import (
    P5CompositionSnapshot,
    P5ParticipantBinding,
    assert_composition_identity,
)


class P4P5PersistenceError(RuntimeError):
    """Fail-closed exact persistence error for M8 P4/P5 products."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


def _time_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    raise P4P5PersistenceError("P4_P5_DB_TIME_INVALID", type(value).__name__)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P4P5PersistenceError("P4_P5_DB_NUMERIC_INVALID", type(value).__name__)
    return float(value)


def _required_float(value: object, field: str) -> float:
    result = _optional_float(value)
    if result is None:
        raise P4P5PersistenceError("P4_P5_DB_NUMERIC_INVALID", field)
    return result


def _optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise P4P5PersistenceError("P4_P5_DB_INTEGER_INVALID", field)
    return value


def _required_int(value: object, field: str) -> int:
    result = _optional_int(value, field)
    if result is None:
        raise P4P5PersistenceError("P4_P5_DB_INTEGER_INVALID", field)
    return result


def _text_array(value: object, field: str) -> tuple[str, ...]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P4P5PersistenceError("P4_P5_DB_ARRAY_INVALID", field) from exc
    if not isinstance(decoded, (list, tuple)):
        raise P4P5PersistenceError("P4_P5_DB_ARRAY_INVALID", field)
    result: list[str] = []
    for item in decoded:
        if not isinstance(item, str):
            raise P4P5PersistenceError("P4_P5_DB_ARRAY_INVALID", field)
        result.append(item)
    return tuple(result)


def _uuid_array(value: object, field: str) -> tuple[str, ...]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P4P5PersistenceError("P4_P5_DB_ARRAY_INVALID", field) from exc
    if not isinstance(decoded, (list, tuple)):
        raise P4P5PersistenceError("P4_P5_DB_ARRAY_INVALID", field)
    result: list[str] = []
    for item in decoded:
        if isinstance(item, UUID):
            result.append(str(item))
        elif isinstance(item, str):
            result.append(item)
        else:
            raise P4P5PersistenceError("P4_P5_DB_ARRAY_INVALID", field)
    return tuple(result)


def _p4_hash(value: P4AssessmentRevision) -> str:
    return canonical_hash(
        {
            "subject_context_id": value.subject_context_id,
            "subject_key": value.subject_key,
            "actor_id": value.actor_id,
            "role_code": value.role_code,
            "seat_code": value.seat_code,
            "function_code": value.function_code,
            "session_id": value.session_id,
            "episode_id": value.episode_id,
            "aircraft_id": value.aircraft_id,
            "twin_revision_id": value.twin_revision_id,
            "p3_estimate_id": value.p3_estimate_id,
            "assessment_spec_id": value.assessment_spec_id,
            "assessment_spec_version": value.assessment_spec_version,
            "role_model_version": value.role_model_version,
            "world_refs": list(value.world_refs),
            "machine_evidence_ids": list(value.machine_evidence_ids),
            "instructor_annotation_ids": list(value.instructor_annotation_ids),
            "score": None,
            "grade": None,
            "status": value.status,
            "confidence": value.confidence,
            "evidence_set_id": value.evidence_set_id,
            "created_at_utc": value.created_at_utc,
            "supersedes_id": value.supersedes_id,
            "approval_state": value.approval_state,
            "p3_claim_level": value.p3_claim_level,
            "p3_validity_status": value.p3_validity_status,
            "p3_as_of_utc": value.p3_as_of_utc,
            "uncertainty_lower": value.uncertainty_lower,
            "uncertainty_upper": value.uncertainty_upper,
        }
    )


def _p5_hash(value: P5AssessmentRevision) -> str:
    return canonical_hash(
        {
            "composition_id": value.composition_id,
            "session_id": value.session_id,
            "mission_episode_id": value.mission_episode_id,
            "team_id": value.team_id,
            "assessment_spec_id": value.assessment_spec_id,
            "assessment_spec_version": value.assessment_spec_version,
            "participant_subject_keys": list(value.participant_subject_keys),
            "world_snapshot_refs": list(value.world_snapshot_refs),
            "objective_result_refs": list(value.objective_result_refs),
            "team_performance_evidence_id": value.team_performance_evidence_id,
            "aggregation_profile_ref": None,
            "overall_score": None,
            "grade": None,
            "status": value.status,
            "confidence": value.confidence,
            "evidence_set_id": value.evidence_set_id,
            "created_at_utc": value.created_at_utc,
            "supersedes_id": value.supersedes_id,
            "approval_state": value.approval_state,
            "claim_level": value.claim_level,
            "validity_status": value.validity_status,
            "as_of_utc": value.as_of_utc,
        }
    )


class P4P5PersistenceRepository:
    """Shared SQLite/PostgreSQL mapper for exact M8 assessment revisions."""

    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows

    def register_p4_subject(self, value: P4SubjectContext) -> None:
        assert_p4_subject_context_identity(value)
        current = self._try_exact_p4_subject(value.subject_context_id)
        if current is not None:
            if current != value:
                raise P4P5PersistenceError(
                    "P4_P5_IMMUTABLE_CONFLICT",
                    value.subject_context_id,
                )
            return
        self._rows.insert(
            "assessment.p4_subject_context",
            {
                "subject_context_id": value.subject_context_id,
                "subject_key": value.subject_key,
                "actor_id": value.actor_id,
                "role_code": value.role_code,
                "seat_code": value.seat_code,
                "function_code": value.function_code,
                "session_id": value.session_id,
                "episode_id": value.episode_id,
                "stage_id": value.stage_id,
                "aircraft_id": value.aircraft_id,
                "twin_revision_id": value.twin_revision_id,
                "p3_estimate_id": value.p3_estimate_id,
                "assessment_spec_id": value.assessment_spec_id,
                "assessment_spec_version": value.assessment_spec_version,
                "role_model_context_artifact_id": value.role_model_context_artifact_id,
                "role_model_version": value.role_model_version,
                "world_refs": value.world_refs,
                "evidence_set_id": value.evidence_set_id,
                "as_of_utc": value.as_of_utc,
                "knowledge_time_utc": value.knowledge_time_utc,
            },
            field_kinds={"world_refs": "text_array"},
        )

    def _try_exact_p4_subject(self, subject_context_id: str) -> P4SubjectContext | None:
        row = self._rows.one(
            "assessment.p4_subject_context",
            where={"subject_context_id": subject_context_id},
            columns=(
                "subject_context_id",
                "subject_key",
                "actor_id",
                "role_code",
                "seat_code",
                "function_code",
                "session_id",
                "episode_id",
                "stage_id",
                "aircraft_id",
                "twin_revision_id",
                "p3_estimate_id",
                "assessment_spec_id",
                "assessment_spec_version",
                "role_model_context_artifact_id",
                "role_model_version",
                "world_refs",
                "evidence_set_id",
                "as_of_utc",
                "knowledge_time_utc",
            ),
        )
        if row is None:
            return None
        value = P4SubjectContext(
            subject_context_id=str(row["subject_context_id"]),
            subject_key=str(row["subject_key"]),
            actor_id=str(row["actor_id"]),
            role_code=str(row["role_code"]),
            seat_code=_optional_text(row["seat_code"]),
            function_code=_optional_text(row["function_code"]),
            session_id=str(row["session_id"]),
            episode_id=str(row["episode_id"]),
            stage_id=_optional_text(row["stage_id"]),
            aircraft_id=_optional_text(row["aircraft_id"]),
            twin_revision_id=str(row["twin_revision_id"]),
            p3_estimate_id=_optional_text(row["p3_estimate_id"]),
            assessment_spec_id=str(row["assessment_spec_id"]),
            assessment_spec_version=str(row["assessment_spec_version"]),
            role_model_context_artifact_id=str(row["role_model_context_artifact_id"]),
            role_model_version=str(row["role_model_version"]),
            world_refs=_text_array(row["world_refs"], "p4_subject_context.world_refs"),
            evidence_set_id=str(row["evidence_set_id"]),
            as_of_utc=_time_text(row["as_of_utc"]),
            knowledge_time_utc=_time_text(row["knowledge_time_utc"]),
        )
        assert_p4_subject_context_identity(value)
        return value

    def exact_p4_subject(self, subject_context_id: str) -> P4SubjectContext:
        value = self._try_exact_p4_subject(subject_context_id)
        if value is None:
            raise P4P5PersistenceError("P4_SUBJECT_NOT_FOUND", subject_context_id)
        return value

    def _annotation_from_row(
        self,
        row: dict[str, object],
        *,
        subject_context_id: str,
    ) -> InstructorAnnotationRevision:
        author_id = str(row["author_id"])
        author_subject_key = pseudonymous_subject_key(author_id)
        base_release_id = str(row["base_release_id"])
        session_id = str(row["session_id"])
        episode_id = _optional_text(row["episode_id"])
        stage_id = _optional_text(row["stage_id"])
        annotation_type = str(row["annotation_type"])
        start_session_time_us = _optional_int(
            row["start_session_time_us"],
            "annotation.start_session_time_us",
        )
        end_session_time_us = _optional_int(
            row["end_session_time_us"],
            "annotation.end_session_time_us",
        )
        body_text = str(row["body_text"])
        visibility = str(row["visibility"])
        status = str(row["status"])
        revision_no = _required_int(row["revision_no"], "annotation.revision_no")
        supersedes_annotation_id = _optional_text(row["supersedes_annotation_id"])
        evidence_set_id = _optional_text(row["evidence_set_id"])
        created_at_utc = _time_text(row["created_at"])
        payload = {
            "base_release_id": base_release_id,
            "session_id": session_id,
            "episode_id": episode_id,
            "stage_id": stage_id,
            "author_subject_key": author_subject_key,
            "author_id": author_id,
            "annotation_type": annotation_type,
            "start_session_time_us": start_session_time_us,
            "end_session_time_us": end_session_time_us,
            "body_text": body_text,
            "visibility": visibility,
            "status": status,
            "revision_no": revision_no,
            "supersedes_annotation_id": supersedes_annotation_id,
            "evidence_set_id": evidence_set_id,
            "subject_context_id": subject_context_id,
            "created_at_utc": created_at_utc,
        }
        return InstructorAnnotationRevision(
            annotation_id=str(row["annotation_id"]),
            base_release_id=base_release_id,
            session_id=session_id,
            episode_id=episode_id,
            stage_id=stage_id,
            author_subject_key=author_subject_key,
            author_id=author_id,
            annotation_type=annotation_type,
            start_session_time_us=start_session_time_us,
            end_session_time_us=end_session_time_us,
            body_text=body_text,
            visibility=visibility,
            status=status,
            revision_no=revision_no,
            supersedes_annotation_id=supersedes_annotation_id,
            evidence_set_id=evidence_set_id,
            subject_context_id=subject_context_id,
            created_at_utc=created_at_utc,
            content_hash=canonical_hash(payload),
        )

    def _annotation_row(
        self,
        annotation_id: str,
    ) -> dict[str, object] | None:
        return self._rows.one(
            "debrief.annotation",
            where={"annotation_id": annotation_id},
            columns=(
                "annotation_id",
                "base_release_id",
                "session_id",
                "episode_id",
                "stage_id",
                "author_id",
                "annotation_type",
                "start_session_time_us",
                "end_session_time_us",
                "body_text",
                "visibility",
                "status",
                "revision_no",
                "supersedes_annotation_id",
                "evidence_set_id",
                "created_at",
            ),
        )

    def _annotation_subject_context(
        self,
        annotation_id: str,
    ) -> str | None:
        row = self._rows.one(
            "assessment.annotation_subject_context",
            where={"annotation_id": annotation_id},
            columns=("annotation_id", "subject_context_id"),
        )
        if row is None:
            return None
        return str(row["subject_context_id"])

    def _ensure_annotation_subject_context(
        self,
        annotation_id: str,
        subject_context_id: str,
    ) -> None:
        # DB 1.9 makes this standalone association canonical authority.
        self.exact_p4_subject(subject_context_id)
        current = self._annotation_subject_context(annotation_id)
        if current is not None:
            if current != subject_context_id:
                raise P4P5PersistenceError(
                    "P4_ANNOTATION_CONTEXT_MISMATCH",
                    annotation_id,
                )
            return
        self._rows.insert(
            "assessment.annotation_subject_context",
            {
                "annotation_id": annotation_id,
                "subject_context_id": subject_context_id,
            },
        )

    def _register_annotation(
        self,
        value: InstructorAnnotationRevision,
        *,
        subject_context_id: str,
    ) -> None:
        if value.subject_context_id != subject_context_id:
            raise P4P5PersistenceError(
                "P4_ANNOTATION_CONTEXT_MISMATCH",
                value.annotation_id,
            )
        expected_author = pseudonymous_subject_key(value.author_id)
        if value.author_subject_key != expected_author:
            raise P4P5PersistenceError(
                "P4_ANNOTATION_AUTHOR_KEY_MISMATCH",
                value.annotation_id,
            )
        payload_hash = canonical_hash(
            {
                "base_release_id": value.base_release_id,
                "session_id": value.session_id,
                "episode_id": value.episode_id,
                "stage_id": value.stage_id,
                "author_subject_key": value.author_subject_key,
                "author_id": value.author_id,
                "annotation_type": value.annotation_type,
                "start_session_time_us": value.start_session_time_us,
                "end_session_time_us": value.end_session_time_us,
                "body_text": value.body_text,
                "visibility": value.visibility,
                "status": value.status,
                "revision_no": value.revision_no,
                "supersedes_annotation_id": value.supersedes_annotation_id,
                "evidence_set_id": value.evidence_set_id,
                "subject_context_id": value.subject_context_id,
                "created_at_utc": value.created_at_utc,
            }
        )
        if payload_hash != value.content_hash:
            raise P4P5PersistenceError(
                "P4_ANNOTATION_CONTENT_HASH_MISMATCH",
                value.annotation_id,
            )
        current_row = self._annotation_row(value.annotation_id)
        if current_row is not None:
            current = self._annotation_from_row(
                current_row,
                subject_context_id=subject_context_id,
            )
            if current != value:
                raise P4P5PersistenceError(
                    "P4_P5_IMMUTABLE_CONFLICT",
                    value.annotation_id,
                )
            self._ensure_annotation_subject_context(
                value.annotation_id,
                subject_context_id,
            )
            return
        self._rows.insert(
            "debrief.annotation",
            {
                "annotation_id": value.annotation_id,
                "base_release_id": value.base_release_id,
                "session_id": value.session_id,
                "episode_id": value.episode_id,
                "stage_id": value.stage_id,
                "author_id": value.author_id,
                "annotation_type": value.annotation_type,
                "start_session_time_us": value.start_session_time_us,
                "end_session_time_us": value.end_session_time_us,
                "body_text": value.body_text,
                "visibility": value.visibility,
                "status": value.status,
                "revision_no": value.revision_no,
                "supersedes_annotation_id": value.supersedes_annotation_id,
                "evidence_set_id": value.evidence_set_id,
                "created_at": value.created_at_utc,
            },
        )
        self._ensure_annotation_subject_context(
            value.annotation_id,
            subject_context_id,
        )

    def register_annotation(self, value: InstructorAnnotationRevision) -> None:
        """Persist one standalone M8 annotation with exact DB 1.9 subject context."""
        self._register_annotation(
            value,
            subject_context_id=value.subject_context_id,
        )

    def exact_annotation(
        self,
        annotation_id: str,
    ) -> InstructorAnnotationRevision:
        """Return one standalone M8 annotation from DB 1.9 canonical authority."""
        subject_context_id = self._annotation_subject_context(annotation_id)
        if subject_context_id is None:
            raise P4P5PersistenceError(
                "P4_ANNOTATION_SUBJECT_CONTEXT_NOT_FOUND",
                annotation_id,
            )
        row = self._annotation_row(annotation_id)
        if row is None:
            raise P4P5PersistenceError("P4_ANNOTATION_NOT_FOUND", annotation_id)
        return self._annotation_from_row(
            row,
            subject_context_id=subject_context_id,
        )

    def register_p4_revision(
        self,
        subject: P4SubjectContext,
        value: P4AssessmentRevision,
        *,
        annotations: tuple[InstructorAnnotationRevision, ...] = (),
    ) -> None:
        self.register_p4_subject(subject)
        current = self._try_exact_p4_revision(value.actor_assessment_id)
        if current is not None:
            if current != value:
                raise P4P5PersistenceError(
                    "P4_P5_IMMUTABLE_CONFLICT",
                    value.actor_assessment_id,
                )
            return
        if (
            value.subject_context_id != subject.subject_context_id
            or value.subject_key != subject.subject_key
            or value.actor_id != subject.actor_id
            or value.role_code != subject.role_code
            or value.seat_code != subject.seat_code
            or value.function_code != subject.function_code
            or value.session_id != subject.session_id
            or value.episode_id != subject.episode_id
            or value.aircraft_id != subject.aircraft_id
            or value.twin_revision_id != subject.twin_revision_id
            or value.p3_estimate_id != subject.p3_estimate_id
            or value.assessment_spec_id != subject.assessment_spec_id
            or value.assessment_spec_version != subject.assessment_spec_version
            or value.role_model_version != subject.role_model_version
            or value.world_refs != subject.world_refs
            or value.evidence_set_id != subject.evidence_set_id
        ):
            raise P4P5PersistenceError(
                "P4_SUBJECT_REVISION_MISMATCH",
                value.actor_assessment_id,
            )
        if value.score is not None or value.grade is not None:
            raise P4P5PersistenceError(
                "P4_NUMERIC_OUTCOME_NOT_AUTHORIZED",
                value.actor_assessment_id,
            )
        if value.logical_content_hash != _p4_hash(value):
            raise P4P5PersistenceError(
                "P4_LOGICAL_HASH_MISMATCH",
                value.actor_assessment_id,
            )
        annotation_by_id = {item.annotation_id: item for item in annotations}
        if len(annotation_by_id) != len(annotations) or tuple(
            item.annotation_id for item in annotations
        ) != value.instructor_annotation_ids:
            raise P4P5PersistenceError(
                "P4_ANNOTATION_MEMBERSHIP_MISMATCH",
                value.actor_assessment_id,
            )
        for annotation in annotations:
            self._register_annotation(
                annotation,
                subject_context_id=subject.subject_context_id,
            )
        capability_refs = (
            () if value.p3_estimate_id is None else (value.p3_estimate_id,)
        )
        # DB 1.9 keeps the exact logical text world refs in p4_subject_context.
        # The legacy UUID[] base columns are not overloaded with hashed text identities.
        self._rows.insert(
            "assessment.actor_assessment",
            {
                "actor_assessment_id": value.actor_assessment_id,
                "session_id": value.session_id,
                "episode_id": value.episode_id,
                "actor_id": value.actor_id,
                "aircraft_id": value.aircraft_id,
                "assessment_spec_id": value.assessment_spec_id,
                "assessment_spec_version": value.assessment_spec_version,
                "world_refs": (),
                "metric_refs": (),
                "capability_projection_refs": capability_refs,
                "score": None,
                "grade": None,
                "status": value.status,
                "confidence": value.confidence,
                "evidence_set_id": value.evidence_set_id,
                "created_at": value.created_at_utc,
                "supersedes_id": value.supersedes_id,
            },
            field_kinds={
                "world_refs": "uuid_array",
                "metric_refs": "uuid_array",
                "capability_projection_refs": "uuid_array",
            },
        )
        self._rows.insert(
            "assessment.actor_assessment_revision",
            {
                "actor_assessment_id": value.actor_assessment_id,
                "subject_context_id": value.subject_context_id,
                "approval_state": value.approval_state,
                "p3_claim_level": value.p3_claim_level,
                "p3_validity_status": value.p3_validity_status,
                "p3_as_of_utc": value.p3_as_of_utc,
                "uncertainty_lower": value.uncertainty_lower,
                "uncertainty_upper": value.uncertainty_upper,
                "logical_content_hash": value.logical_content_hash,
            },
        )
        for index, evidence_ref in enumerate(value.machine_evidence_ids):
            self._rows.insert(
                "assessment.actor_assessment_machine_evidence_ref",
                {
                    "actor_assessment_id": value.actor_assessment_id,
                    "ref_order": index,
                    "evidence_ref": evidence_ref,
                },
            )
        for index, annotation_id in enumerate(value.instructor_annotation_ids):
            self._rows.insert(
                "assessment.actor_assessment_annotation_ref",
                {
                    "actor_assessment_id": value.actor_assessment_id,
                    "ref_order": index,
                    "annotation_id": annotation_id,
                },
            )

    def _try_exact_p4_revision(
        self,
        actor_assessment_id: str,
    ) -> P4AssessmentRevision | None:
        base = self._rows.one(
            "assessment.actor_assessment",
            where={"actor_assessment_id": actor_assessment_id},
            columns=(
                "actor_assessment_id",
                "session_id",
                "episode_id",
                "actor_id",
                "aircraft_id",
                "assessment_spec_id",
                "assessment_spec_version",
                "capability_projection_refs",
                "score",
                "grade",
                "status",
                "confidence",
                "evidence_set_id",
                "created_at",
                "supersedes_id",
            ),
        )
        if base is None:
            return None
        revision = self._rows.one(
            "assessment.actor_assessment_revision",
            where={"actor_assessment_id": actor_assessment_id},
            columns=(
                "subject_context_id",
                "approval_state",
                "p3_claim_level",
                "p3_validity_status",
                "p3_as_of_utc",
                "uncertainty_lower",
                "uncertainty_upper",
                "logical_content_hash",
            ),
        )
        if revision is None:
            raise P4P5PersistenceError(
                "P4_REVISION_METADATA_MISSING",
                actor_assessment_id,
            )
        subject = self.exact_p4_subject(str(revision["subject_context_id"]))
        machine_rows = self._rows.many(
            "assessment.actor_assessment_machine_evidence_ref",
            where={"actor_assessment_id": actor_assessment_id},
            columns=("ref_order", "evidence_ref"),
            order_by=("ref_order",),
        )
        annotation_rows = self._rows.many(
            "assessment.actor_assessment_annotation_ref",
            where={"actor_assessment_id": actor_assessment_id},
            columns=("ref_order", "annotation_id"),
            order_by=("ref_order",),
        )
        capability_refs = _uuid_array(
            base["capability_projection_refs"],
            "actor_assessment.capability_projection_refs",
        )
        expected_capability_refs = (
            () if subject.p3_estimate_id is None else (subject.p3_estimate_id,)
        )
        if capability_refs != expected_capability_refs:
            raise P4P5PersistenceError(
                "P4_CAPABILITY_PROJECTION_MISMATCH",
                actor_assessment_id,
            )
        if (
            str(base["session_id"]) != subject.session_id
            or str(base["episode_id"]) != subject.episode_id
            or str(base["actor_id"]) != subject.actor_id
            or _optional_text(base["aircraft_id"]) != subject.aircraft_id
            or str(base["assessment_spec_id"]) != subject.assessment_spec_id
            or str(base["assessment_spec_version"])
            != subject.assessment_spec_version
            or str(base["evidence_set_id"]) != subject.evidence_set_id
        ):
            raise P4P5PersistenceError(
                "P4_SUBJECT_REVISION_MISMATCH",
                actor_assessment_id,
            )
        value = P4AssessmentRevision(
            actor_assessment_id=str(base["actor_assessment_id"]),
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
            machine_evidence_ids=tuple(str(row["evidence_ref"]) for row in machine_rows),
            instructor_annotation_ids=tuple(
                str(row["annotation_id"]) for row in annotation_rows
            ),
            score=None,
            grade=None,
            status=str(base["status"]),
            confidence=_required_float(
                base["confidence"],
                "actor_assessment.confidence",
            ),
            evidence_set_id=str(base["evidence_set_id"]),
            created_at_utc=_time_text(base["created_at"]),
            supersedes_id=_optional_text(base["supersedes_id"]),
            approval_state=str(revision["approval_state"]),
            p3_claim_level=str(revision["p3_claim_level"]),
            p3_validity_status=str(revision["p3_validity_status"]),
            p3_as_of_utc=_time_text(revision["p3_as_of_utc"]),
            uncertainty_lower=_optional_float(revision["uncertainty_lower"]),
            uncertainty_upper=_optional_float(revision["uncertainty_upper"]),
            logical_content_hash=str(revision["logical_content_hash"]),
        )
        if base["score"] is not None or base["grade"] is not None:
            raise P4P5PersistenceError(
                "P4_NUMERIC_OUTCOME_NOT_AUTHORIZED",
                actor_assessment_id,
            )
        if value.logical_content_hash != _p4_hash(value):
            raise P4P5PersistenceError(
                "P4_LOGICAL_HASH_MISMATCH",
                actor_assessment_id,
            )
        return value

    def exact_p4_revision(self, actor_assessment_id: str) -> P4AssessmentRevision:
        value = self._try_exact_p4_revision(actor_assessment_id)
        if value is None:
            raise P4P5PersistenceError("P4_REVISION_NOT_FOUND", actor_assessment_id)
        return value

    def register_p4(self, revision: P4AssessmentRevision) -> None:
        """M8AssessmentRepository port: persist an immutable P4 revision."""
        subject = self.exact_p4_subject(revision.subject_context_id)
        annotations = tuple(
            self.exact_annotation(annotation_id)
            for annotation_id in revision.instructor_annotation_ids
        )
        self.register_p4_revision(
            subject,
            revision,
            annotations=annotations,
        )

    def exact_p4(self, revision_id: str) -> P4AssessmentRevision:
        """M8AssessmentRepository port: return an exact P4 revision."""
        return self.exact_p4_revision(revision_id)

    def exact_p4_annotation(
        self,
        actor_assessment_id: str,
        annotation_id: str,
    ) -> InstructorAnnotationRevision:
        revision = self.exact_p4_revision(actor_assessment_id)
        if annotation_id not in revision.instructor_annotation_ids:
            raise P4P5PersistenceError(
                "P4_ANNOTATION_NOT_BOUND",
                annotation_id,
            )
        annotation = self.exact_annotation(annotation_id)
        if annotation.subject_context_id != revision.subject_context_id:
            raise P4P5PersistenceError(
                "P4_ANNOTATION_CONTEXT_MISMATCH",
                annotation_id,
            )
        return annotation

    def register_p5_composition(self, value: P5CompositionSnapshot) -> None:
        assert_composition_identity(value)
        current = self._try_exact_p5_composition(value.composition_id)
        if current is not None:
            if current != value:
                raise P4P5PersistenceError(
                    "P4_P5_IMMUTABLE_CONFLICT",
                    value.composition_id,
                )
            return
        self._rows.insert(
            "assessment.p5_composition_snapshot",
            {
                "composition_id": value.composition_id,
                "session_id": value.session_id,
                "mission_episode_id": value.mission_episode_id,
                "team_id": value.team_id,
                "world_snapshot_refs": value.world_snapshot_refs,
                "scenario_context_artifact_id": value.scenario_context_artifact_id,
                "role_model_context_artifact_id": value.role_model_context_artifact_id,
                "assessment_spec_id": value.assessment_spec_id,
                "assessment_spec_version": value.assessment_spec_version,
                "as_of_utc": value.as_of_utc,
                "composition_hash": value.composition_hash,
            },
            field_kinds={"world_snapshot_refs": "text_array"},
        )
        for index, participant in enumerate(value.participant_bindings):
            self._rows.insert(
                "assessment.p5_composition_participant",
                {
                    "composition_id": value.composition_id,
                    "ref_order": index,
                    "subject_key": participant.subject_key,
                    "role_code": participant.role_code,
                    "aircraft_id": participant.aircraft_id,
                    "twin_revision_id": participant.twin_revision_id,
                    "p4_revision_id": participant.p4_revision_id,
                },
            )

    def _try_exact_p5_composition(
        self,
        composition_id: str,
    ) -> P5CompositionSnapshot | None:
        row = self._rows.one(
            "assessment.p5_composition_snapshot",
            where={"composition_id": composition_id},
            columns=(
                "composition_id",
                "session_id",
                "mission_episode_id",
                "team_id",
                "world_snapshot_refs",
                "scenario_context_artifact_id",
                "role_model_context_artifact_id",
                "assessment_spec_id",
                "assessment_spec_version",
                "as_of_utc",
                "composition_hash",
            ),
        )
        if row is None:
            return None
        participant_rows = self._rows.many(
            "assessment.p5_composition_participant",
            where={"composition_id": composition_id},
            columns=(
                "ref_order",
                "subject_key",
                "role_code",
                "aircraft_id",
                "twin_revision_id",
                "p4_revision_id",
            ),
            order_by=("ref_order",),
        )
        participants = tuple(
            P5ParticipantBinding(
                subject_key=str(item["subject_key"]),
                role_code=str(item["role_code"]),
                aircraft_id=_optional_text(item["aircraft_id"]),
                twin_revision_id=_optional_text(item["twin_revision_id"]),
                p4_revision_id=str(item["p4_revision_id"]),
            )
            for item in participant_rows
        )
        value = P5CompositionSnapshot(
            composition_id=str(row["composition_id"]),
            session_id=str(row["session_id"]),
            mission_episode_id=str(row["mission_episode_id"]),
            team_id=_optional_text(row["team_id"]),
            participant_subject_keys=tuple(item.subject_key for item in participants),
            participant_bindings=participants,
            world_snapshot_refs=_text_array(
                row["world_snapshot_refs"],
                "p5_composition.world_snapshot_refs",
            ),
            scenario_context_artifact_id=_optional_text(
                row["scenario_context_artifact_id"]
            ),
            role_model_context_artifact_id=str(
                row["role_model_context_artifact_id"]
            ),
            assessment_spec_id=str(row["assessment_spec_id"]),
            assessment_spec_version=str(row["assessment_spec_version"]),
            as_of_utc=_time_text(row["as_of_utc"]),
            composition_hash=str(row["composition_hash"]),
        )
        assert_composition_identity(value)
        return value

    def exact_p5_composition(self, composition_id: str) -> P5CompositionSnapshot:
        value = self._try_exact_p5_composition(composition_id)
        if value is None:
            raise P4P5PersistenceError("P5_COMPOSITION_NOT_FOUND", composition_id)
        return value

    def register_p5_revision(
        self,
        composition: P5CompositionSnapshot,
        value: P5AssessmentRevision,
    ) -> None:
        self.register_p5_composition(composition)
        current = self._try_exact_p5_revision(value.mission_assessment_id)
        if current is not None:
            if current != value:
                raise P4P5PersistenceError(
                    "P4_P5_IMMUTABLE_CONFLICT",
                    value.mission_assessment_id,
                )
            return
        if (
            value.composition_id != composition.composition_id
            or value.session_id != composition.session_id
            or value.mission_episode_id != composition.mission_episode_id
            or value.team_id != composition.team_id
            or value.assessment_spec_id != composition.assessment_spec_id
            or value.assessment_spec_version != composition.assessment_spec_version
            or value.participant_subject_keys != composition.participant_subject_keys
            or value.world_snapshot_refs != composition.world_snapshot_refs
        ):
            raise P4P5PersistenceError(
                "P5_COMPOSITION_REVISION_MISMATCH",
                value.mission_assessment_id,
            )
        if (
            value.aggregation_profile_ref is not None
            or value.overall_score is not None
            or value.grade is not None
        ):
            raise P4P5PersistenceError(
                "P5_NUMERIC_OUTCOME_NOT_AUTHORIZED",
                value.mission_assessment_id,
            )
        if value.logical_content_hash != _p5_hash(value):
            raise P4P5PersistenceError(
                "P5_LOGICAL_HASH_MISMATCH",
                value.mission_assessment_id,
            )
        participant_ids: list[str] = []
        for participant in composition.participant_bindings:
            p4 = self.exact_p4_revision(participant.p4_revision_id)
            if p4.subject_key != participant.subject_key:
                raise P4P5PersistenceError(
                    "P5_PARTICIPANT_P4_MISMATCH",
                    participant.subject_key,
                )
            participant_ids.append(p4.actor_id)
        # Exact text world/objective identities live in the DB 1.9 companion
        # relations. Legacy UUID[] columns retain only genuine UUID projections.
        self._rows.insert(
            "assessment.mission_assessment",
            {
                "mission_assessment_id": value.mission_assessment_id,
                "session_id": value.session_id,
                "mission_episode_id": value.mission_episode_id,
                "team_id": value.team_id,
                "assessment_spec_id": value.assessment_spec_id,
                "assessment_spec_version": value.assessment_spec_version,
                "participant_ids": tuple(participant_ids),
                "world_snapshot_refs": (),
                "adjudication_refs": (),
                "overall_score": None,
                "grade": None,
                "status": value.status,
                "confidence": value.confidence,
                "evidence_set_id": value.evidence_set_id,
                "created_at": value.created_at_utc,
                "supersedes_id": value.supersedes_id,
            },
            field_kinds={
                "participant_ids": "uuid_array",
                "world_snapshot_refs": "uuid_array",
                "adjudication_refs": "uuid_array",
            },
        )
        self._rows.insert(
            "assessment.mission_assessment_revision",
            {
                "mission_assessment_id": value.mission_assessment_id,
                "composition_id": value.composition_id,
                "team_performance_evidence_id": value.team_performance_evidence_id,
                "approval_state": value.approval_state,
                "claim_level": value.claim_level,
                "validity_status": value.validity_status,
                "as_of_utc": value.as_of_utc,
                "logical_content_hash": value.logical_content_hash,
            },
        )
        for index, objective_ref in enumerate(value.objective_result_refs):
            self._rows.insert(
                "assessment.mission_assessment_objective_ref",
                {
                    "mission_assessment_id": value.mission_assessment_id,
                    "ref_order": index,
                    "objective_ref": objective_ref,
                },
            )

    def _try_exact_p5_revision(
        self,
        mission_assessment_id: str,
    ) -> P5AssessmentRevision | None:
        base = self._rows.one(
            "assessment.mission_assessment",
            where={"mission_assessment_id": mission_assessment_id},
            columns=(
                "mission_assessment_id",
                "session_id",
                "mission_episode_id",
                "team_id",
                "assessment_spec_id",
                "assessment_spec_version",
                "participant_ids",
                "overall_score",
                "grade",
                "status",
                "confidence",
                "evidence_set_id",
                "created_at",
                "supersedes_id",
            ),
        )
        if base is None:
            return None
        revision = self._rows.one(
            "assessment.mission_assessment_revision",
            where={"mission_assessment_id": mission_assessment_id},
            columns=(
                "composition_id",
                "team_performance_evidence_id",
                "approval_state",
                "claim_level",
                "validity_status",
                "as_of_utc",
                "logical_content_hash",
            ),
        )
        if revision is None:
            raise P4P5PersistenceError(
                "P5_REVISION_METADATA_MISSING",
                mission_assessment_id,
            )
        composition = self.exact_p5_composition(str(revision["composition_id"]))
        objective_rows = self._rows.many(
            "assessment.mission_assessment_objective_ref",
            where={"mission_assessment_id": mission_assessment_id},
            columns=("ref_order", "objective_ref"),
            order_by=("ref_order",),
        )
        participant_ids = _uuid_array(
            base["participant_ids"],
            "mission_assessment.participant_ids",
        )
        expected_participant_ids = tuple(
            self.exact_p4_revision(item.p4_revision_id).actor_id
            for item in composition.participant_bindings
        )
        if participant_ids != expected_participant_ids:
            raise P4P5PersistenceError(
                "P5_PARTICIPANT_ID_PROJECTION_MISMATCH",
                mission_assessment_id,
            )
        if (
            str(base["session_id"]) != composition.session_id
            or str(base["mission_episode_id"]) != composition.mission_episode_id
            or _optional_text(base["team_id"]) != composition.team_id
            or str(base["assessment_spec_id"]) != composition.assessment_spec_id
            or str(base["assessment_spec_version"])
            != composition.assessment_spec_version
        ):
            raise P4P5PersistenceError(
                "P5_COMPOSITION_REVISION_MISMATCH",
                mission_assessment_id,
            )
        value = P5AssessmentRevision(
            mission_assessment_id=str(base["mission_assessment_id"]),
            composition_id=composition.composition_id,
            session_id=composition.session_id,
            mission_episode_id=composition.mission_episode_id,
            team_id=composition.team_id,
            assessment_spec_id=composition.assessment_spec_id,
            assessment_spec_version=composition.assessment_spec_version,
            participant_subject_keys=composition.participant_subject_keys,
            world_snapshot_refs=composition.world_snapshot_refs,
            objective_result_refs=tuple(
                str(row["objective_ref"]) for row in objective_rows
            ),
            team_performance_evidence_id=str(
                revision["team_performance_evidence_id"]
            ),
            aggregation_profile_ref=None,
            overall_score=None,
            grade=None,
            status=str(base["status"]),
            confidence=_required_float(
                base["confidence"],
                "mission_assessment.confidence",
            ),
            evidence_set_id=str(base["evidence_set_id"]),
            created_at_utc=_time_text(base["created_at"]),
            supersedes_id=_optional_text(base["supersedes_id"]),
            approval_state=str(revision["approval_state"]),
            claim_level=str(revision["claim_level"]),
            validity_status=str(revision["validity_status"]),
            as_of_utc=_time_text(revision["as_of_utc"]),
            logical_content_hash=str(revision["logical_content_hash"]),
        )
        if base["overall_score"] is not None or base["grade"] is not None:
            raise P4P5PersistenceError(
                "P5_NUMERIC_OUTCOME_NOT_AUTHORIZED",
                mission_assessment_id,
            )
        if value.logical_content_hash != _p5_hash(value):
            raise P4P5PersistenceError(
                "P5_LOGICAL_HASH_MISMATCH",
                mission_assessment_id,
            )
        return value

    def exact_p5_revision(self, mission_assessment_id: str) -> P5AssessmentRevision:
        value = self._try_exact_p5_revision(mission_assessment_id)
        if value is None:
            raise P4P5PersistenceError("P5_REVISION_NOT_FOUND", mission_assessment_id)
        return value

    def register_p5(self, revision: P5AssessmentRevision) -> None:
        """M8AssessmentRepository port: persist an immutable P5 revision."""
        composition = self.exact_p5_composition(revision.composition_id)
        self.register_p5_revision(composition, revision)

    def exact_p5(self, revision_id: str) -> P5AssessmentRevision:
        """M8AssessmentRepository port: return an exact P5 revision."""
        return self.exact_p5_revision(revision_id)

