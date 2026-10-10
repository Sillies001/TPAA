"""Durable ED2 assessment-result snapshots over DB 1.9."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid5

from tpaa_assessment.ed2_profile import (
    ED2AssessmentGate,
    ED2AssessmentProfileResult,
    evaluate_ed2_training_assessment,
)
from tpaa_storage.canonical_rows import CanonicalRowRepository

_NAMESPACE = UUID("30259233-e152-4ae4-8e92-1c53a4343e72")
_SNAPSHOT_TYPE = "ED2_TRAINING_ASSESSMENT_RESULT"
_SCHEMA_VERSION = "TPAA_ED2_ASSESSMENT_RESULT_V1"


class ED2AssessmentResultError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ED2AssessmentResult:
    dataset_snapshot_id: str
    revision_kind: str
    revision_id: str
    profile_id: str
    profile_version: str
    availability_status: str
    competency_code: str
    competency_state: str
    critical_gates: tuple[ED2AssessmentGate, ...]
    qualification_status: str
    reason_codes: tuple[str, ...]
    numeric_score: None
    grade: None
    logical_content_hash: str


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _gate_payload(gate: ED2AssessmentGate) -> dict[str, object]:
    return {
        "gate_code": gate.gate_code,
        "achieved": gate.achieved,
        "reason_codes": list(gate.reason_codes),
    }


def _manifest(
    *,
    revision_kind: str,
    revision_id: str,
    result: ED2AssessmentProfileResult,
) -> dict[str, object]:
    return {
        "schema": _SCHEMA_VERSION,
        "revision_kind": revision_kind,
        "revision_id": revision_id,
        "profile_id": result.profile_id,
        "profile_version": result.profile_version,
        "availability_status": result.availability_status,
        "competency_code": result.competency_code,
        "competency_state": result.competency_state,
        "critical_gates": [_gate_payload(gate) for gate in result.critical_gates],
        "qualification_status": result.qualification_status,
        "reason_codes": list(result.reason_codes),
        "numeric_score": None,
        "grade": None,
    }


def assessment_result_from_profile(
    *,
    revision_kind: str,
    revision_id: str,
    result: ED2AssessmentProfileResult,
) -> ED2AssessmentResult:
    if revision_kind not in {"P4", "P5"}:
        raise ED2AssessmentResultError(
            "ED2_ASSESSMENT_RESULT_KIND_INVALID",
            revision_kind,
        )
    try:
        parsed = UUID(revision_id)
    except ValueError as exc:
        raise ED2AssessmentResultError(
            "ED2_ASSESSMENT_RESULT_REVISION_INVALID",
            revision_id,
        ) from exc
    if parsed.int == 0 or str(parsed) != revision_id:
        raise ED2AssessmentResultError(
            "ED2_ASSESSMENT_RESULT_REVISION_INVALID",
            revision_id,
        )
    manifest = _manifest(
        revision_kind=revision_kind,
        revision_id=revision_id,
        result=result,
    )
    digest = _canonical_hash(manifest)
    snapshot_id = str(uuid5(_NAMESPACE, f"{revision_kind}:{revision_id}:{digest}"))
    return ED2AssessmentResult(
        dataset_snapshot_id=snapshot_id,
        revision_kind=revision_kind,
        revision_id=revision_id,
        profile_id=result.profile_id,
        profile_version=result.profile_version,
        availability_status=result.availability_status,
        competency_code=result.competency_code,
        competency_state=result.competency_state,
        critical_gates=result.critical_gates,
        qualification_status=result.qualification_status,
        reason_codes=result.reason_codes,
        numeric_score=None,
        grade=None,
        logical_content_hash=digest,
    )


class ED2AssessmentResultRepository:
    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows

    @staticmethod
    def _manifest(value: ED2AssessmentResult) -> dict[str, object]:
        profile_result = ED2AssessmentProfileResult(
            profile_id=value.profile_id,
            profile_version=value.profile_version,
            availability_status=value.availability_status,
            competency_code=value.competency_code,
            competency_state=value.competency_state,
            critical_gates=value.critical_gates,
            qualification_status=value.qualification_status,
            reason_codes=value.reason_codes,
        )
        return _manifest(
            revision_kind=value.revision_kind,
            revision_id=value.revision_id,
            result=profile_result,
        )

    def register(
        self,
        value: ED2AssessmentResult,
        *,
        created_at_utc: str,
    ) -> None:
        manifest = self._manifest(value)
        digest = _canonical_hash(manifest)
        if (
            digest != value.logical_content_hash
            or value.numeric_score is not None
            or value.grade is not None
        ):
            raise ED2AssessmentResultError(
                "ED2_ASSESSMENT_RESULT_IDENTITY_DRIFT",
                value.revision_id,
            )
        current = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": value.dataset_snapshot_id},
            columns=(
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        expected_refs = (value.revision_id,)
        if current is None:
            self._rows.insert(
                "registry.dataset_snapshot",
                {
                    "dataset_snapshot_id": value.dataset_snapshot_id,
                    "snapshot_type": _SNAPSHOT_TYPE,
                    "query_or_manifest": manifest,
                    "input_refs": expected_refs,
                    "data_hash": digest,
                    "schema_version": _SCHEMA_VERSION,
                    "created_at": created_at_utc,
                    "frozen": True,
                },
                field_kinds={
                    "query_or_manifest": "json",
                    "input_refs": "uuid_array",
                },
            )
            return
        raw_manifest = current["query_or_manifest"]
        if isinstance(raw_manifest, str):
            parsed: object = json.loads(raw_manifest)
        else:
            parsed = raw_manifest
        refs_raw = current["input_refs"]
        if isinstance(refs_raw, str):
            refs_obj: object = json.loads(refs_raw)
        else:
            refs_obj = refs_raw
        refs = tuple(str(item) for item in cast(list[object] | tuple[object, ...], refs_obj))
        frozen = current["frozen"]
        if isinstance(frozen, int) and not isinstance(frozen, bool):
            frozen = bool(frozen)
        if (
            parsed != manifest
            or refs != expected_refs
            or str(current["snapshot_type"]) != _SNAPSHOT_TYPE
            or str(current["data_hash"]) != digest
            or str(current["schema_version"]) != _SCHEMA_VERSION
            or frozen is not True
        ):
            raise ED2AssessmentResultError(
                "ED2_ASSESSMENT_RESULT_IMMUTABLE_CONFLICT",
                value.revision_id,
            )

    def exact(self, revision_id: str) -> ED2AssessmentResult:
        rows = self._rows.many(
            "registry.dataset_snapshot",
            where={"snapshot_type": _SNAPSHOT_TYPE},
            columns=(
                "dataset_snapshot_id",
                "query_or_manifest",
                "data_hash",
                "schema_version",
                "frozen",
            ),
            order_by=("dataset_snapshot_id",),
        )
        matched: list[dict[str, object]] = []
        for row in rows:
            raw = row["query_or_manifest"]
            manifest = json.loads(raw) if isinstance(raw, str) else raw
            if (
                isinstance(manifest, dict)
                and manifest.get("revision_id") == revision_id
            ):
                matched.append({**row, "query_or_manifest": manifest})
        if len(matched) != 1:
            raise ED2AssessmentResultError(
                "ED2_ASSESSMENT_RESULT_NOT_FOUND",
                revision_id,
            )
        row = matched[0]
        manifest = cast(dict[str, object], row["query_or_manifest"])
        gates_raw = manifest.get("critical_gates")
        if not isinstance(gates_raw, list):
            raise ED2AssessmentResultError(
                "ED2_ASSESSMENT_RESULT_INTEGRITY_FAILED",
                revision_id,
            )
        gates: list[ED2AssessmentGate] = []
        for raw_gate in gates_raw:
            if not isinstance(raw_gate, dict):
                raise ED2AssessmentResultError(
                    "ED2_ASSESSMENT_RESULT_INTEGRITY_FAILED",
                    revision_id,
                )
            achieved = raw_gate.get("achieved")
            if achieved is not None and not isinstance(achieved, bool):
                raise ED2AssessmentResultError(
                    "ED2_ASSESSMENT_RESULT_INTEGRITY_FAILED",
                    revision_id,
                )
            reasons = raw_gate.get("reason_codes")
            if not isinstance(reasons, list) or not all(
                isinstance(item, str) for item in reasons
            ):
                raise ED2AssessmentResultError(
                    "ED2_ASSESSMENT_RESULT_INTEGRITY_FAILED",
                    revision_id,
                )
            gates.append(
                ED2AssessmentGate(
                    gate_code=str(raw_gate.get("gate_code")),
                    achieved=achieved,
                    reason_codes=tuple(cast(list[str], reasons)),
                )
            )
        profile_result = ED2AssessmentProfileResult(
            profile_id=str(manifest["profile_id"]),
            profile_version=str(manifest["profile_version"]),
            availability_status=str(manifest["availability_status"]),
            competency_code=str(manifest["competency_code"]),
            competency_state=str(manifest["competency_state"]),
            critical_gates=tuple(gates),
            qualification_status=str(manifest["qualification_status"]),
            reason_codes=tuple(
                cast(list[str], manifest.get("reason_codes", []))
            ),
        )
        rebuilt = assessment_result_from_profile(
            revision_kind=str(manifest["revision_kind"]),
            revision_id=revision_id,
            result=profile_result,
        )
        if (
            rebuilt.dataset_snapshot_id != str(row["dataset_snapshot_id"])
            or rebuilt.logical_content_hash != str(row["data_hash"])
            or str(row["schema_version"]) != _SCHEMA_VERSION
            or row["frozen"] not in (True, 1)
        ):
            raise ED2AssessmentResultError(
                "ED2_ASSESSMENT_RESULT_INTEGRITY_FAILED",
                revision_id,
            )
        return rebuilt

    def successor(
        self,
        *,
        previous_revision_id: str,
        revision_kind: str,
        revision_id: str,
        approval_state: str,
        created_at_utc: str,
    ) -> ED2AssessmentResult:
        previous = self.exact(previous_revision_id)
        p3_gate = next(
            gate
            for gate in previous.critical_gates
            if gate.gate_code == "ED2_GATE_P3_IN_DOMAIN"
        )
        if p3_gate.achieved is True:
            p3_statuses = ("IN_DOMAIN",)
        elif p3_gate.achieved is False:
            p3_statuses = ("OUT_OF_DOMAIN",)
        else:
            p3_statuses = ("UNAVAILABLE",)
        result = evaluate_ed2_training_assessment(
            evidence_availability=(previous.availability_status,),
            p3_validity_statuses=p3_statuses,
            approval_states=(approval_state,),
        )
        value = assessment_result_from_profile(
            revision_kind=revision_kind,
            revision_id=revision_id,
            result=result,
        )
        self.register(value, created_at_utc=created_at_utc)
        return value
