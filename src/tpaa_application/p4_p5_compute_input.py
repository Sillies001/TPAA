"""PRCB C2 durable pre-compute authority for P4/P5 governed workers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid5

from tpaa_assessment import P4AssessmentRevision
from tpaa_context import canonical_hash
from tpaa_storage import CanonicalRowRepository
from tpaa_world import (
    M8EvidenceRef,
    M8WorldFactRef,
    P4InteractionScopeSnapshot,
    P5CompositionSnapshot,
    build_p4_interaction_scope_snapshot,
)

from .p4_p5_persistence import P4P5PersistenceRepository

_P4_SCHEMA = "TPAA_P4_DURABLE_COMPUTE_INPUT_V1"
_P5_SCHEMA = "TPAA_P5_DURABLE_COMPUTE_INPUT_V1"
_P4_SNAPSHOT_TYPE = "P4_INTERACTION_SCOPE"
_P5_SNAPSHOT_TYPE = "P5_TEAM_MISSION_COMPUTE_INPUT"
_SNAPSHOT_SCHEMA_VERSION = "1.0.0"
_P4_NAMESPACE = UUID("f3c3874d-dfd6-4e60-ae02-73e429ea2646")
_P5_NAMESPACE = UUID("0a1e4620-7341-4459-a81a-7e94d2274a18")


class P4P5ComputeInputError(RuntimeError):
    """Fail-closed durable compute-input persistence error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class P5DurableComputeInput:
    composition: P5CompositionSnapshot
    p4_revisions: tuple[P4AssessmentRevision, ...]
    objective_result_refs: tuple[str, ...]
    evidence_set_id: str
    as_of_utc: str


def _json_object(value: object, field: str) -> dict[str, object]:
    decoded = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P4P5ComputeInputError(
                "P4_P5_COMPUTE_INPUT_JSON_INVALID",
                field,
            ) from exc
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) for key in decoded
    ):
        raise P4P5ComputeInputError(
            "P4_P5_COMPUTE_INPUT_JSON_INVALID",
            field,
        )
    return {str(key): item for key, item in decoded.items()}


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise P4P5ComputeInputError(
            "P4_P5_COMPUTE_INPUT_TEXT_INVALID",
            field,
        )
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise P4P5ComputeInputError(
            "P4_P5_COMPUTE_INPUT_ARRAY_INVALID",
            field,
        )
    return tuple(value)


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise P4P5ComputeInputError(
            "P4_P5_COMPUTE_INPUT_UUID_INVALID",
            field,
        ) from exc
    canonical = str(parsed)
    if canonical != value or parsed.int == 0:
        raise P4P5ComputeInputError(
            "P4_P5_COMPUTE_INPUT_UUID_INVALID",
            field,
        )
    return canonical


def _uuid_refs(values: tuple[str | None, ...]) -> tuple[str, ...]:
    refs = {_uuid(value, "input_ref") for value in values if value is not None}
    return tuple(sorted(refs))


def _numeric(value: object, field: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P4P5ComputeInputError(
            "P4_P5_COMPUTE_INPUT_NUMERIC_INVALID",
            field,
        )
    return value


def _fact_projection(value: M8WorldFactRef) -> dict[str, object]:
    return {
        "ref_id": value.ref_id,
        "world_layer": value.world_layer,
        "episode_id": value.episode_id,
        "stage_id": value.stage_id,
        "source_hash": value.source_hash,
        "knowledge_time_utc": value.knowledge_time_utc,
    }


def _evidence_projection(value: M8EvidenceRef) -> dict[str, object]:
    return {
        "evidence_id": value.evidence_id,
        "origin": value.origin,
        "evidence_family": value.evidence_family,
        "evidence_set_id": value.evidence_set_id,
        "episode_id": value.episode_id,
        "world_refs": list(value.world_refs),
        "source_refs": list(value.source_refs),
        "availability_status": value.availability_status,
        "numeric_value": value.numeric_value,
        "knowledge_time_utc": value.knowledge_time_utc,
    }


class P4P5ComputeInputRepository:
    """Immutable DB 1.9 snapshots consumed by P4/P5 production workers."""

    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows
        self._products = P4P5PersistenceRepository(rows)

    def _register_snapshot(
        self,
        *,
        snapshot_id: str,
        snapshot_type: str,
        manifest: dict[str, object],
        input_refs: tuple[str, ...],
        data_hash: str,
        created_at: str,
    ) -> None:
        current = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": snapshot_id},
            columns=(
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if current is None:
            self._rows.insert(
                "registry.dataset_snapshot",
                {
                    "dataset_snapshot_id": snapshot_id,
                    "snapshot_type": snapshot_type,
                    "query_or_manifest": manifest,
                    "input_refs": input_refs,
                    "data_hash": data_hash,
                    "schema_version": _SNAPSHOT_SCHEMA_VERSION,
                    "created_at": created_at,
                    "frozen": True,
                },
                field_kinds={
                    "query_or_manifest": "json",
                    "input_refs": "uuid_array",
                },
            )
            return

        existing = _json_object(
            current["query_or_manifest"],
            "dataset_snapshot.query_or_manifest",
        )
        refs = _strings(current["input_refs"], "dataset_snapshot.input_refs")
        frozen = current["frozen"]
        if isinstance(frozen, int) and not isinstance(frozen, bool):
            frozen = bool(frozen)
        if (
            str(current["snapshot_type"]) != snapshot_type
            or existing != manifest
            or refs != input_refs
            or str(current["data_hash"]) != data_hash
            or str(current["schema_version"]) != _SNAPSHOT_SCHEMA_VERSION
            or frozen is not True
        ):
            raise P4P5ComputeInputError(
                "P4_P5_COMPUTE_INPUT_IMMUTABLE_CONFLICT",
                snapshot_id,
            )

    def _snapshot(
        self,
        snapshot_id: str,
        *,
        snapshot_type: str,
        schema: str,
        namespace: UUID,
    ) -> dict[str, object]:
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": snapshot_id},
            columns=(
                "snapshot_type",
                "query_or_manifest",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if row is None:
            raise P4P5ComputeInputError(
                "P4_P5_COMPUTE_INPUT_NOT_FOUND",
                snapshot_id,
            )
        manifest = _json_object(
            row["query_or_manifest"],
            "dataset_snapshot.query_or_manifest",
        )
        frozen = row["frozen"]
        if isinstance(frozen, int) and not isinstance(frozen, bool):
            frozen = bool(frozen)
        data_hash = canonical_hash(manifest)
        if (
            str(row["snapshot_type"]) != snapshot_type
            or manifest.get("schema") != schema
            or str(row["schema_version"]) != _SNAPSHOT_SCHEMA_VERSION
            or frozen is not True
            or str(row["data_hash"]) != data_hash
            or snapshot_id != str(uuid5(namespace, data_hash))
        ):
            raise P4P5ComputeInputError(
                "P4_P5_COMPUTE_INPUT_INTEGRITY_FAILED",
                snapshot_id,
            )
        return manifest

    def register_p4_scope(
        self,
        scope: P4InteractionScopeSnapshot,
    ) -> str:
        subject = self._products.exact_p4_subject(scope.subject_context_id)
        if (
            subject.episode_id != scope.episode_id
            or subject.as_of_utc != scope.as_of_utc
        ):
            raise P4P5ComputeInputError(
                "P4_COMPUTE_INPUT_SUBJECT_SCOPE_MISMATCH",
                scope.subject_context_id,
            )
        manifest: dict[str, object] = {
            "schema": _P4_SCHEMA,
            "subject_context_id": scope.subject_context_id,
            "episode_id": scope.episode_id,
            "as_of_utc": scope.as_of_utc,
            "fact_refs": [_fact_projection(item) for item in scope.fact_refs],
            "machine_evidence": [
                _evidence_projection(item) for item in scope.machine_evidence
            ],
            "instructor_evidence": [
                _evidence_projection(item)
                for item in scope.instructor_evidence
            ],
            "scope_hash": scope.scope_hash,
        }
        data_hash = canonical_hash(manifest)
        snapshot_id = str(uuid5(_P4_NAMESPACE, data_hash))
        evidence_refs = tuple(
            item.evidence_set_id
            for item in (*scope.machine_evidence, *scope.instructor_evidence)
        )
        input_refs = _uuid_refs(
            (
                subject.actor_id,
                subject.session_id,
                subject.episode_id,
                subject.stage_id,
                subject.aircraft_id,
                subject.twin_revision_id,
                subject.p3_estimate_id,
                subject.role_model_context_artifact_id,
                subject.evidence_set_id,
                *evidence_refs,
            )
        )
        self._register_snapshot(
            snapshot_id=snapshot_id,
            snapshot_type=_P4_SNAPSHOT_TYPE,
            manifest=manifest,
            input_refs=input_refs,
            data_hash=data_hash,
            created_at=scope.as_of_utc,
        )
        return snapshot_id

    def exact_p4_scope(self, snapshot_id: str) -> P4InteractionScopeSnapshot:
        manifest = self._snapshot(
            snapshot_id,
            snapshot_type=_P4_SNAPSHOT_TYPE,
            schema=_P4_SCHEMA,
            namespace=_P4_NAMESPACE,
        )

        def facts() -> tuple[M8WorldFactRef, ...]:
            raw = manifest.get("fact_refs")
            if not isinstance(raw, list):
                raise P4P5ComputeInputError(
                    "P4_COMPUTE_INPUT_MANIFEST_INVALID",
                    "fact_refs",
                )
            result: list[M8WorldFactRef] = []
            for index, item in enumerate(raw):
                value = _json_object(item, f"fact_refs[{index}]")
                result.append(
                    M8WorldFactRef(
                        ref_id=_text(value.get("ref_id"), "fact.ref_id"),
                        world_layer=_text(
                            value.get("world_layer"),
                            "fact.world_layer",
                        ),
                        episode_id=_text(
                            value.get("episode_id"),
                            "fact.episode_id",
                        ),
                        stage_id=_optional_text(
                            value.get("stage_id"),
                            "fact.stage_id",
                        ),
                        source_hash=_text(
                            value.get("source_hash"),
                            "fact.source_hash",
                        ),
                        knowledge_time_utc=_text(
                            value.get("knowledge_time_utc"),
                            "fact.knowledge_time_utc",
                        ),
                    )
                )
            return tuple(result)

        def evidence(field: str) -> tuple[M8EvidenceRef, ...]:
            raw = manifest.get(field)
            if not isinstance(raw, list):
                raise P4P5ComputeInputError(
                    "P4_COMPUTE_INPUT_MANIFEST_INVALID",
                    field,
                )
            result: list[M8EvidenceRef] = []
            for index, item in enumerate(raw):
                value = _json_object(item, f"{field}[{index}]")
                result.append(
                    M8EvidenceRef(
                        evidence_id=_text(
                            value.get("evidence_id"),
                            "evidence.evidence_id",
                        ),
                        origin=_text(value.get("origin"), "evidence.origin"),
                        evidence_family=_text(
                            value.get("evidence_family"),
                            "evidence.evidence_family",
                        ),
                        evidence_set_id=_text(
                            value.get("evidence_set_id"),
                            "evidence.evidence_set_id",
                        ),
                        episode_id=_text(
                            value.get("episode_id"),
                            "evidence.episode_id",
                        ),
                        world_refs=_strings(
                            value.get("world_refs"),
                            "evidence.world_refs",
                        ),
                        source_refs=_strings(
                            value.get("source_refs"),
                            "evidence.source_refs",
                        ),
                        availability_status=_text(
                            value.get("availability_status"),
                            "evidence.availability_status",
                        ),
                        numeric_value=_numeric(
                            value.get("numeric_value"),
                            "evidence.numeric_value",
                        ),
                        knowledge_time_utc=_text(
                            value.get("knowledge_time_utc"),
                            "evidence.knowledge_time_utc",
                        ),
                    )
                )
            return tuple(result)

        scope = build_p4_interaction_scope_snapshot(
            subject_context_id=_text(
                manifest.get("subject_context_id"),
                "subject_context_id",
            ),
            episode_id=_text(manifest.get("episode_id"), "episode_id"),
            as_of_utc=_text(manifest.get("as_of_utc"), "as_of_utc"),
            fact_refs=facts(),
            machine_evidence=evidence("machine_evidence"),
            instructor_evidence=evidence("instructor_evidence"),
        )
        if scope.scope_hash != _text(manifest.get("scope_hash"), "scope_hash"):
            raise P4P5ComputeInputError(
                "P4_COMPUTE_INPUT_SCOPE_HASH_MISMATCH",
                snapshot_id,
            )
        self._products.exact_p4_subject(scope.subject_context_id)
        return scope

    def register_p5_selection(
        self,
        composition: P5CompositionSnapshot,
        *,
        objective_result_refs: tuple[str, ...],
        evidence_set_id: str,
        as_of_utc: str,
    ) -> str:
        if as_of_utc != composition.as_of_utc:
            raise P4P5ComputeInputError(
                "P5_COMPUTE_INPUT_AS_OF_MISMATCH",
                composition.composition_id,
            )
        _uuid(evidence_set_id, "evidence_set_id")
        objectives = tuple(sorted(_strings(objective_result_refs, "objective_result_refs")))
        if len(set(objectives)) != len(objectives):
            raise P4P5ComputeInputError(
                "P5_COMPUTE_INPUT_OBJECTIVE_DUPLICATE",
                composition.composition_id,
            )
        self._products.register_p5_composition(composition)
        p4_ids: list[str] = []
        for participant in composition.participant_bindings:
            p4 = self._products.exact_p4_revision(participant.p4_revision_id)
            if (
                p4.subject_key != participant.subject_key
                or p4.aircraft_id != participant.aircraft_id
                or p4.twin_revision_id != participant.twin_revision_id
            ):
                raise P4P5ComputeInputError(
                    "P5_COMPUTE_INPUT_PARTICIPANT_MISMATCH",
                    participant.p4_revision_id,
                )
            p4_ids.append(p4.actor_assessment_id)
        manifest: dict[str, object] = {
            "schema": _P5_SCHEMA,
            "composition_id": composition.composition_id,
            "p4_revision_ids": p4_ids,
            "objective_result_refs": list(objectives),
            "evidence_set_id": evidence_set_id,
            "as_of_utc": as_of_utc,
        }
        data_hash = canonical_hash(manifest)
        snapshot_id = str(uuid5(_P5_NAMESPACE, data_hash))
        participant_refs: list[str | None] = []
        for participant in composition.participant_bindings:
            participant_refs.extend(
                (
                    participant.p4_revision_id,
                    participant.aircraft_id,
                    participant.twin_revision_id,
                )
            )
        input_refs = _uuid_refs(
            (
                composition.session_id,
                composition.mission_episode_id,
                composition.team_id,
                composition.scenario_context_artifact_id,
                composition.role_model_context_artifact_id,
                evidence_set_id,
                *participant_refs,
            )
        )
        self._register_snapshot(
            snapshot_id=snapshot_id,
            snapshot_type=_P5_SNAPSHOT_TYPE,
            manifest=manifest,
            input_refs=input_refs,
            data_hash=data_hash,
            created_at=as_of_utc,
        )
        return snapshot_id

    def exact_p5_selection(self, snapshot_id: str) -> P5DurableComputeInput:
        manifest = self._snapshot(
            snapshot_id,
            snapshot_type=_P5_SNAPSHOT_TYPE,
            schema=_P5_SCHEMA,
            namespace=_P5_NAMESPACE,
        )
        composition_id = _text(
            manifest.get("composition_id"),
            "composition_id",
        )
        composition = self._products.exact_p5_composition(composition_id)
        p4_ids = _strings(
            manifest.get("p4_revision_ids"),
            "p4_revision_ids",
        )
        expected_ids = tuple(
            item.p4_revision_id for item in composition.participant_bindings
        )
        if p4_ids != expected_ids:
            raise P4P5ComputeInputError(
                "P5_COMPUTE_INPUT_PARTICIPANT_MISMATCH",
                snapshot_id,
            )
        p4_revisions = tuple(
            self._products.exact_p4_revision(value) for value in p4_ids
        )
        for participant, p4 in zip(
            composition.participant_bindings,
            p4_revisions,
            strict=True,
        ):
            if (
                p4.subject_key != participant.subject_key
                or p4.aircraft_id != participant.aircraft_id
                or p4.twin_revision_id != participant.twin_revision_id
            ):
                raise P4P5ComputeInputError(
                    "P5_COMPUTE_INPUT_PARTICIPANT_MISMATCH",
                    p4.actor_assessment_id,
                )
        as_of_utc = _text(manifest.get("as_of_utc"), "as_of_utc")
        if as_of_utc != composition.as_of_utc:
            raise P4P5ComputeInputError(
                "P5_COMPUTE_INPUT_AS_OF_MISMATCH",
                snapshot_id,
            )
        evidence_set_id = _uuid(
            _text(manifest.get("evidence_set_id"), "evidence_set_id"),
            "evidence_set_id",
        )
        return P5DurableComputeInput(
            composition=composition,
            p4_revisions=p4_revisions,
            objective_result_refs=_strings(
                manifest.get("objective_result_refs"),
                "objective_result_refs",
            ),
            evidence_set_id=evidence_set_id,
            as_of_utc=as_of_utc,
        )
