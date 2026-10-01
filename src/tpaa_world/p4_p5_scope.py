"""M8 Batch 1 exact World/evidence boundary and P5 composition substrate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_context.m8_p4_p5 import (
    M8AuthorityPolicy,
    M8GovernanceError,
    canonical_hash,
    exact_hash64,
    exact_text,
    exact_uuid,
    utc,
    validate_availability_numeric,
)


@dataclass(frozen=True)
class M8WorldFactRef:
    ref_id: str
    world_layer: str
    episode_id: str
    stage_id: str | None
    source_hash: str
    knowledge_time_utc: str


@dataclass(frozen=True)
class M8EvidenceRef:
    evidence_id: str
    origin: str
    evidence_family: str
    evidence_set_id: str
    episode_id: str
    world_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    availability_status: str
    numeric_value: float | int | None
    knowledge_time_utc: str


@dataclass(frozen=True)
class P4InteractionScopeSnapshot:
    interaction_scope_id: str
    subject_context_id: str
    episode_id: str
    as_of_utc: str
    fact_refs: tuple[M8WorldFactRef, ...]
    machine_evidence: tuple[M8EvidenceRef, ...]
    instructor_evidence: tuple[M8EvidenceRef, ...]
    scope_hash: str


def _stable_texts(
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


def _validate_fact(
    fact: M8WorldFactRef,
    *,
    target_episode_id: str,
    as_of_utc: str,
    policy: M8AuthorityPolicy,
) -> None:
    exact_text(fact.ref_id, field="fact.ref_id", policy=policy)
    if fact.world_layer not in {"GROUND_TRUTH", "PERCEIVED_WORLD", "ACTION_WORLD"}:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"world_layer={fact.world_layer!r}",
        )
    exact_uuid(fact.episode_id, field="fact.episode_id", policy=policy)
    if fact.episode_id != target_episode_id:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "fact episode mismatch",
        )
    if fact.stage_id is not None:
        exact_uuid(fact.stage_id, field="fact.stage_id", policy=policy)
    exact_hash64(fact.source_hash, field="fact.source_hash")
    if utc(fact.knowledge_time_utc, field="fact.knowledge_time_utc") > utc(
        as_of_utc,
        field="as_of_utc",
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_FUTURE_INFORMATION",
            fact.ref_id,
        )


def _validate_evidence(
    evidence: M8EvidenceRef,
    *,
    target_episode_id: str,
    as_of_utc: str,
    expected_origin: str,
    policy: M8AuthorityPolicy,
) -> None:
    exact_text(evidence.evidence_id, field="evidence_id", policy=policy)
    exact_uuid(evidence.evidence_set_id, field="evidence_set_id", policy=policy)
    exact_uuid(evidence.episode_id, field="evidence.episode_id", policy=policy)
    if evidence.episode_id != target_episode_id:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "evidence episode mismatch",
        )
    if evidence.origin != expected_origin:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_MACHINE_HUMAN_EVIDENCE_CONFLATION",
            f"{evidence.evidence_id}:{evidence.origin}",
        )
    if evidence.evidence_family not in policy.approved_evidence_families:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"evidence_family={evidence.evidence_family!r}",
        )
    if (
        expected_origin == "MACHINE"
        and evidence.evidence_family == "INSTRUCTOR_ANNOTATION"
    ) or (
        expected_origin == "INSTRUCTOR"
        and evidence.evidence_family != "INSTRUCTOR_ANNOTATION"
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_MACHINE_HUMAN_EVIDENCE_CONFLATION",
            f"{evidence.evidence_id}:{evidence.evidence_family}",
        )
    _stable_texts(evidence.world_refs, field="evidence.world_refs", policy=policy)
    _stable_texts(evidence.source_refs, field="evidence.source_refs", policy=policy)
    validate_availability_numeric(
        status=evidence.availability_status,
        numeric_value=evidence.numeric_value,
        policy=policy,
    )
    if utc(evidence.knowledge_time_utc, field="evidence.knowledge_time_utc") > utc(
        as_of_utc,
        field="as_of_utc",
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_FUTURE_INFORMATION",
            evidence.evidence_id,
        )


def build_p4_interaction_scope_snapshot(
    *,
    subject_context_id: str,
    episode_id: str,
    as_of_utc: str,
    fact_refs: tuple[M8WorldFactRef, ...],
    machine_evidence: tuple[M8EvidenceRef, ...],
    instructor_evidence: tuple[M8EvidenceRef, ...],
    policy: M8AuthorityPolicy | None = None,
) -> P4InteractionScopeSnapshot:
    p = policy or M8AuthorityPolicy.from_canonical()
    exact_text(subject_context_id, field="subject_context_id", policy=p)
    exact_uuid(episode_id, field="episode_id", policy=p)
    utc(as_of_utc, field="as_of_utc")

    for fact in fact_refs:
        _validate_fact(
            fact,
            target_episode_id=episode_id,
            as_of_utc=as_of_utc,
            policy=p,
        )
    for evidence in machine_evidence:
        _validate_evidence(
            evidence,
            target_episode_id=episode_id,
            as_of_utc=as_of_utc,
            expected_origin="MACHINE",
            policy=p,
        )
    for evidence in instructor_evidence:
        _validate_evidence(
            evidence,
            target_episode_id=episode_id,
            as_of_utc=as_of_utc,
            expected_origin="INSTRUCTOR",
            policy=p,
        )

    fact_keys = [fact.ref_id for fact in fact_refs]
    evidence_keys = [
        evidence.evidence_id for evidence in (*machine_evidence, *instructor_evidence)
    ]
    if len(set(fact_keys)) != len(fact_keys) or len(set(evidence_keys)) != len(
        evidence_keys
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "duplicate fact/evidence identity",
        )
    if set(fact_keys) & set(evidence_keys):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_MACHINE_HUMAN_EVIDENCE_CONFLATION",
            "fact/evidence identity collision",
        )

    facts = tuple(sorted(fact_refs, key=lambda value: value.ref_id))
    machine = tuple(sorted(machine_evidence, key=lambda value: value.evidence_id))
    instructors = tuple(
        sorted(instructor_evidence, key=lambda value: value.evidence_id)
    )
    payload = {
        "subject_context_id": subject_context_id,
        "episode_id": episode_id,
        "as_of_utc": as_of_utc,
        "fact_refs": [
            {
                "ref_id": fact.ref_id,
                "world_layer": fact.world_layer,
                "episode_id": fact.episode_id,
                "stage_id": fact.stage_id,
                "source_hash": fact.source_hash,
                "knowledge_time_utc": fact.knowledge_time_utc,
            }
            for fact in facts
        ],
        "machine_evidence": [
            {
                "evidence_id": item.evidence_id,
                "origin": item.origin,
                "evidence_family": item.evidence_family,
                "evidence_set_id": item.evidence_set_id,
                "episode_id": item.episode_id,
                "world_refs": list(item.world_refs),
                "source_refs": list(item.source_refs),
                "availability_status": item.availability_status,
                "numeric_value": item.numeric_value,
                "knowledge_time_utc": item.knowledge_time_utc,
            }
            for item in machine
        ],
        "instructor_evidence": [
            {
                "evidence_id": item.evidence_id,
                "origin": item.origin,
                "evidence_family": item.evidence_family,
                "evidence_set_id": item.evidence_set_id,
                "episode_id": item.episode_id,
                "world_refs": list(item.world_refs),
                "source_refs": list(item.source_refs),
                "availability_status": item.availability_status,
                "numeric_value": item.numeric_value,
                "knowledge_time_utc": item.knowledge_time_utc,
            }
            for item in instructors
        ],
    }
    scope_hash = canonical_hash(payload)
    return P4InteractionScopeSnapshot(
        interaction_scope_id=f"P4_INTERACTION_SCOPE_SHA256:{scope_hash}",
        subject_context_id=subject_context_id,
        episode_id=episode_id,
        as_of_utc=as_of_utc,
        fact_refs=facts,
        machine_evidence=machine,
        instructor_evidence=instructors,
        scope_hash=scope_hash,
    )


def assert_world_facts_immutable(
    original: tuple[M8WorldFactRef, ...],
    candidate: tuple[M8WorldFactRef, ...],
) -> None:
    if original != candidate:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "World facts cannot be mutated by assessment",
        )


@dataclass(frozen=True)
class P5ParticipantBinding:
    subject_key: str
    role_code: str
    aircraft_id: str | None
    twin_revision_id: str | None
    p4_revision_id: str


@dataclass(frozen=True)
class P5CompositionSnapshot:
    composition_id: str
    session_id: str
    mission_episode_id: str
    team_id: str | None
    participant_subject_keys: tuple[str, ...]
    participant_bindings: tuple[P5ParticipantBinding, ...]
    world_snapshot_refs: tuple[str, ...]
    scenario_context_artifact_id: str | None
    role_model_context_artifact_id: str
    assessment_spec_id: str
    assessment_spec_version: str
    as_of_utc: str
    composition_hash: str


def _validate_participant(
    participant: P5ParticipantBinding,
    *,
    policy: M8AuthorityPolicy,
) -> None:
    exact_text(participant.subject_key, field="participant.subject_key", policy=policy)
    if not participant.subject_key.startswith(policy.subject_key_prefix):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "participant subject_key must be pseudonymous",
        )
    exact_text(participant.role_code, field="participant.role_code", policy=policy)
    exact_uuid(
        participant.p4_revision_id,
        field="participant.p4_revision_id",
        policy=policy,
    )
    if (participant.aircraft_id is None) != (participant.twin_revision_id is None):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "aircraft_id and twin_revision_id must be jointly present or absent",
        )
    if participant.aircraft_id is not None:
        exact_uuid(
            participant.aircraft_id,
            field="participant.aircraft_id",
            policy=policy,
        )
        assert participant.twin_revision_id is not None
        exact_uuid(
            participant.twin_revision_id,
            field="participant.twin_revision_id",
            policy=policy,
        )


def build_p5_composition_snapshot(
    *,
    session_id: str,
    mission_episode_id: str,
    team_id: str | None,
    participants: tuple[P5ParticipantBinding, ...],
    world_snapshot_refs: tuple[str, ...],
    scenario_context_artifact_id: str | None,
    role_model_context_artifact_id: str,
    assessment_spec_id: str,
    assessment_spec_version: str,
    as_of_utc: str,
    policy: M8AuthorityPolicy | None = None,
) -> P5CompositionSnapshot:
    p = policy or M8AuthorityPolicy.from_canonical()
    exact_uuid(session_id, field="session_id", policy=p)
    exact_uuid(mission_episode_id, field="mission_episode_id", policy=p)
    if team_id is not None:
        exact_uuid(team_id, field="team_id", policy=p)
    if scenario_context_artifact_id is not None:
        exact_uuid(
            scenario_context_artifact_id,
            field="scenario_context_artifact_id",
            policy=p,
        )
    exact_uuid(
        role_model_context_artifact_id,
        field="role_model_context_artifact_id",
        policy=p,
    )
    exact_text(assessment_spec_id, field="assessment_spec_id", policy=p)
    exact_text(
        assessment_spec_version,
        field="assessment_spec_version",
        policy=p,
    )
    utc(as_of_utc, field="as_of_utc")
    if not participants:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "composition requires at least one participant",
        )
    for participant in participants:
        _validate_participant(participant, policy=p)

    ordered = tuple(
        sorted(
            participants,
            key=lambda item: (
                item.subject_key,
                item.role_code,
                item.aircraft_id or "",
                item.twin_revision_id or "",
                item.p4_revision_id,
            ),
        )
    )
    subject_keys = tuple(item.subject_key for item in ordered)
    if len(set(subject_keys)) != len(subject_keys):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_COMPOSITION_DRIFT",
            "duplicate subject_key in one composition",
        )
    worlds = _stable_texts(
        world_snapshot_refs,
        field="world_snapshot_refs",
        policy=p,
    )
    participant_payload = [
        {
            "subject_key": item.subject_key,
            "role_code": item.role_code,
            "aircraft_id": item.aircraft_id,
            "twin_revision_id": item.twin_revision_id,
            "p4_revision_id": item.p4_revision_id,
        }
        for item in ordered
    ]
    identity = {
        "session_id": session_id,
        "mission_episode_id": mission_episode_id,
        "team_id": team_id,
        "participant_bindings": participant_payload,
        "world_snapshot_refs": list(worlds),
        "scenario_context_artifact_id": scenario_context_artifact_id,
        "role_model_context_artifact_id": role_model_context_artifact_id,
        "assessment_spec_id": assessment_spec_id,
        "assessment_spec_version": assessment_spec_version,
        "as_of_utc": as_of_utc,
    }
    digest = canonical_hash(identity)
    return P5CompositionSnapshot(
        composition_id=f"P5_COMPOSITION_SHA256:{digest}",
        session_id=session_id,
        mission_episode_id=mission_episode_id,
        team_id=team_id,
        participant_subject_keys=subject_keys,
        participant_bindings=ordered,
        world_snapshot_refs=worlds,
        scenario_context_artifact_id=scenario_context_artifact_id,
        role_model_context_artifact_id=role_model_context_artifact_id,
        assessment_spec_id=assessment_spec_id,
        assessment_spec_version=assessment_spec_version,
        as_of_utc=as_of_utc,
        composition_hash=digest,
    )


def assert_composition_identity(snapshot: P5CompositionSnapshot) -> None:
    participant_payload = [
        {
            "subject_key": item.subject_key,
            "role_code": item.role_code,
            "aircraft_id": item.aircraft_id,
            "twin_revision_id": item.twin_revision_id,
            "p4_revision_id": item.p4_revision_id,
        }
        for item in snapshot.participant_bindings
    ]
    identity = {
        "session_id": snapshot.session_id,
        "mission_episode_id": snapshot.mission_episode_id,
        "team_id": snapshot.team_id,
        "participant_bindings": participant_payload,
        "world_snapshot_refs": list(snapshot.world_snapshot_refs),
        "scenario_context_artifact_id": snapshot.scenario_context_artifact_id,
        "role_model_context_artifact_id": snapshot.role_model_context_artifact_id,
        "assessment_spec_id": snapshot.assessment_spec_id,
        "assessment_spec_version": snapshot.assessment_spec_version,
        "as_of_utc": snapshot.as_of_utc,
    }
    digest = canonical_hash(identity)
    if (
        snapshot.composition_hash != digest
        or snapshot.composition_id != f"P5_COMPOSITION_SHA256:{digest}"
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_COMPOSITION_DRIFT",
            snapshot.composition_id,
        )
