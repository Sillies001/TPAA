"""M8 Batch 1 exact immutable P4 subject/context projection."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_context.m8_p4_p5 import (
    M8AuthorityPolicy,
    M8GovernanceError,
    M8RoleModelBinding,
    canonical_hash,
    exact_text,
    exact_uuid,
    pseudonymous_subject_key,
    utc,
    validate_role_model_binding,
)


@dataclass(frozen=True)
class P4SubjectSource:
    actor_id: str
    role_code: str
    seat_code: str | None
    function_code: str | None
    session_id: str
    episode_id: str
    stage_id: str | None
    aircraft_id: str | None
    twin_revision_id: str
    p3_estimate_id: str | None
    p3_source_episode_ids: tuple[str, ...]
    assessment_spec_id: str
    assessment_spec_version: str
    world_refs: tuple[str, ...]
    evidence_set_id: str
    as_of_utc: str
    knowledge_time_utc: str


@dataclass(frozen=True)
class P4SubjectContext:
    subject_context_id: str
    subject_key: str
    actor_id: str
    role_code: str
    seat_code: str | None
    function_code: str | None
    session_id: str
    episode_id: str
    stage_id: str | None
    aircraft_id: str | None
    twin_revision_id: str
    p3_estimate_id: str | None
    assessment_spec_id: str
    assessment_spec_version: str
    role_model_context_artifact_id: str
    role_model_version: str
    world_refs: tuple[str, ...]
    evidence_set_id: str
    as_of_utc: str
    knowledge_time_utc: str

    def projection(self) -> dict[str, object]:
        return {
            "subject_context_id": self.subject_context_id,
            "subject_key": self.subject_key,
            "actor_id": self.actor_id,
            "role_code": self.role_code,
            "seat_code": self.seat_code,
            "function_code": self.function_code,
            "session_id": self.session_id,
            "episode_id": self.episode_id,
            "stage_id": self.stage_id,
            "aircraft_id": self.aircraft_id,
            "twin_revision_id": self.twin_revision_id,
            "p3_estimate_id": self.p3_estimate_id,
            "assessment_spec_id": self.assessment_spec_id,
            "assessment_spec_version": self.assessment_spec_version,
            "role_model_context_artifact_id": self.role_model_context_artifact_id,
            "role_model_version": self.role_model_version,
            "world_refs": list(self.world_refs),
            "evidence_set_id": self.evidence_set_id,
            "as_of_utc": self.as_of_utc,
            "knowledge_time_utc": self.knowledge_time_utc,
        }


def _stable_exact_refs(
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


def build_p4_subject_context(
    source: P4SubjectSource,
    *,
    role_model: M8RoleModelBinding,
    policy: M8AuthorityPolicy | None = None,
) -> P4SubjectContext:
    p = policy or M8AuthorityPolicy.from_canonical()
    exact_uuid(source.actor_id, field="actor_id", policy=p)
    exact_uuid(source.session_id, field="session_id", policy=p)
    exact_uuid(source.episode_id, field="episode_id", policy=p)
    exact_uuid(source.twin_revision_id, field="twin_revision_id", policy=p)
    exact_uuid(source.evidence_set_id, field="evidence_set_id", policy=p)
    if source.stage_id is not None:
        exact_uuid(source.stage_id, field="stage_id", policy=p)
    if source.aircraft_id is not None:
        exact_uuid(source.aircraft_id, field="aircraft_id", policy=p)
    if source.p3_estimate_id is not None:
        exact_uuid(source.p3_estimate_id, field="p3_estimate_id", policy=p)

    rule = p.role_rule(source.role_code)
    if rule.role != source.role_code:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_ROLE_MODEL_REQUIRED",
            source.role_code,
        )
    if source.seat_code is not None:
        exact_text(source.seat_code, field="seat_code", policy=p)
    if source.function_code is not None:
        exact_text(source.function_code, field="function_code", policy=p)
    exact_text(source.assessment_spec_id, field="assessment_spec_id", policy=p)
    exact_text(
        source.assessment_spec_version,
        field="assessment_spec_version",
        policy=p,
    )

    as_of = utc(source.as_of_utc, field="as_of_utc")
    knowledge = utc(source.knowledge_time_utc, field="knowledge_time_utc")
    if knowledge > as_of:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_FUTURE_INFORMATION",
            "knowledge_time_utc exceeds as_of_utc",
        )

    p3_episode_ids: list[str] = []
    for index, episode_id in enumerate(source.p3_source_episode_ids):
        p3_episode_ids.append(
            exact_uuid(
                episode_id,
                field=f"p3_source_episode_ids[{index}]",
                policy=p,
            )
        )
    if source.episode_id in p3_episode_ids:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_SAME_EPISODE_LEAKAGE",
            source.episode_id,
        )

    validate_role_model_binding(role_model, as_of_utc=source.as_of_utc, policy=p)
    world_refs = _stable_exact_refs(source.world_refs, field="world_refs", policy=p)
    subject_key = pseudonymous_subject_key(source.actor_id, policy=p)

    identity = {
        "subject_key": subject_key,
        "role_code": source.role_code,
        "seat_code": source.seat_code,
        "function_code": source.function_code,
        "session_id": source.session_id,
        "episode_id": source.episode_id,
        "stage_id": source.stage_id,
        "aircraft_id": source.aircraft_id,
        "twin_revision_id": source.twin_revision_id,
        "p3_estimate_id": source.p3_estimate_id,
        "assessment_spec_id": source.assessment_spec_id,
        "assessment_spec_version": source.assessment_spec_version,
        "role_model_context_artifact_id": role_model.context_artifact_id,
        "as_of_utc": source.as_of_utc,
    }
    subject_context_id = f"P4_SUBJECT_CONTEXT_SHA256:{canonical_hash(identity)}"

    return P4SubjectContext(
        subject_context_id=subject_context_id,
        subject_key=subject_key,
        actor_id=source.actor_id,
        role_code=source.role_code,
        seat_code=source.seat_code,
        function_code=source.function_code,
        session_id=source.session_id,
        episode_id=source.episode_id,
        stage_id=source.stage_id,
        aircraft_id=source.aircraft_id,
        twin_revision_id=source.twin_revision_id,
        p3_estimate_id=source.p3_estimate_id,
        assessment_spec_id=source.assessment_spec_id,
        assessment_spec_version=source.assessment_spec_version,
        role_model_context_artifact_id=role_model.context_artifact_id,
        role_model_version=role_model.artifact_version,
        world_refs=world_refs,
        evidence_set_id=source.evidence_set_id,
        as_of_utc=source.as_of_utc,
        knowledge_time_utc=source.knowledge_time_utc,
    )


def assert_p4_subject_context_identity(
    context: P4SubjectContext,
) -> None:
    identity = {
        "subject_key": context.subject_key,
        "role_code": context.role_code,
        "seat_code": context.seat_code,
        "function_code": context.function_code,
        "session_id": context.session_id,
        "episode_id": context.episode_id,
        "stage_id": context.stage_id,
        "aircraft_id": context.aircraft_id,
        "twin_revision_id": context.twin_revision_id,
        "p3_estimate_id": context.p3_estimate_id,
        "assessment_spec_id": context.assessment_spec_id,
        "assessment_spec_version": context.assessment_spec_version,
        "role_model_context_artifact_id": context.role_model_context_artifact_id,
        "as_of_utc": context.as_of_utc,
    }
    expected = f"P4_SUBJECT_CONTEXT_SHA256:{canonical_hash(identity)}"
    if context.subject_context_id != expected:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "P4 subject context identity drift",
        )
