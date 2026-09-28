"""Immutable release-bound snapshot substrate for the exact M3 116-metric set.

M3-OBS-002 extends the qualified M2 immutable Release model to the integrated
116-metric plan. It freezes Definition, Evidence, Context, World, identity and
provenance bindings into one deterministic SESSION Release snapshot. Historical
reads operate only on the frozen snapshot and never resolve current/latest
authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid5

from tpaa_metric import M2MetricExecutionBatch, M2MetricExecutionPlan

from .m2_release import (
    M2ReleaseBindingSnapshot,
    M2ReleaseDefinitionSnapshot,
    M2ReleaseExecutionSnapshot,
)
from .m3_publication import M3PublicationRoutingPlan

M3_RELEASE_NAMESPACE = UUID("4a43f84d-7dd7-4868-963c-f58336604327")
M3_RELEASE_STATUS = "VALIDATED"
M3_RELEASE_METRIC_COUNT = 116


class M3ReleaseSnapshotError(RuntimeError):
    """Deterministic fail-closed error for immutable M3 Release snapshots."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _canonical_uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_UUID_INVALID",
            f"{field}={value!r}",
        )
    return canonical


def _require_hash(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_HASH_INVALID",
            f"{field}={value!r}",
        )
    return value


def _canonical_json(value: Mapping[str, object], *, field: str) -> str:
    if not value:
        raise M3ReleaseSnapshotError("M3_RELEASE_BINDING_EMPTY", field)
    try:
        return json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_BINDING_NOT_CANONICAL_JSON",
            field,
        ) from exc


def _hash_json_text(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class M3ReleaseEvidenceSnapshot:
    """One release-bound Evidence payload tied to exact Definition/execution."""

    metric_code: str
    definition_hash: str
    execution_record_hash: str
    evidence_json: str
    evidence_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "metric_code": self.metric_code,
            "definition_hash": self.definition_hash,
            "execution_record_hash": self.execution_record_hash,
            "evidence_json": self.evidence_json,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True)
class M3ImmutableReleaseSnapshot:
    release_id: str
    release_no: int
    parent_release_id: str | None
    session_id: str
    request_hash: str
    catalog_id: str
    catalog_version: str
    catalog_hash: str
    metric_execution_plan_hash: str
    publication_routing_plan_hash: str
    execution_batch_hash: str
    plugin_manifest_hash: str
    bindings: M2ReleaseBindingSnapshot
    definitions: tuple[M2ReleaseDefinitionSnapshot, ...]
    execution_records: tuple[M2ReleaseExecutionSnapshot, ...]
    evidence_bindings: tuple[M3ReleaseEvidenceSnapshot, ...]
    manifest_hash: str
    status: str = M3_RELEASE_STATUS

    def __post_init__(self) -> None:
        _canonical_uuid(self.release_id, field="release_id")
        _canonical_uuid(self.session_id, field="session_id")
        if self.parent_release_id is not None:
            _canonical_uuid(self.parent_release_id, field="parent_release_id")
        if self.release_no < 1:
            raise M3ReleaseSnapshotError(
                "M3_RELEASE_NO_INVALID",
                str(self.release_no),
            )
        if (self.release_no == 1) != (self.parent_release_id is None):
            raise M3ReleaseSnapshotError(
                "M3_RELEASE_PARENT_CHAIN_INVALID",
                f"release_no={self.release_no} parent={self.parent_release_id}",
            )
        if self.parent_release_id == self.release_id:
            raise M3ReleaseSnapshotError(
                "M3_RELEASE_PARENT_CHAIN_INVALID",
                self.release_id,
            )
        for field in (
            "request_hash",
            "catalog_hash",
            "metric_execution_plan_hash",
            "publication_routing_plan_hash",
            "execution_batch_hash",
            "plugin_manifest_hash",
            "manifest_hash",
        ):
            _require_hash(str(getattr(self, field)), field=field)
        if self.status != M3_RELEASE_STATUS:
            raise M3ReleaseSnapshotError(
                "M3_RELEASE_STATUS_INVALID",
                self.status,
            )
        counts = (
            len(self.definitions),
            len(self.execution_records),
            len(self.evidence_bindings),
        )
        if counts != (
            M3_RELEASE_METRIC_COUNT,
            M3_RELEASE_METRIC_COUNT,
            M3_RELEASE_METRIC_COUNT,
        ):
            raise M3ReleaseSnapshotError(
                "M3_RELEASE_MEMBERSHIP_INVALID",
                repr(counts),
            )
        definition_codes = tuple(item.metric_code for item in self.definitions)
        execution_codes = tuple(item.metric_code for item in self.execution_records)
        evidence_codes = tuple(item.metric_code for item in self.evidence_bindings)
        if (
            definition_codes != execution_codes
            or definition_codes != evidence_codes
            or len(set(definition_codes)) != M3_RELEASE_METRIC_COUNT
        ):
            raise M3ReleaseSnapshotError(
                "M3_RELEASE_MEMBERSHIP_INVALID",
                repr((definition_codes, execution_codes, evidence_codes)),
            )

    @property
    def metric_codes(self) -> tuple[str, ...]:
        return tuple(item.metric_code for item in self.definitions)

    def definition(self, metric_code: str) -> M2ReleaseDefinitionSnapshot:
        for item in self.definitions:
            if item.metric_code == metric_code:
                return item
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_DEFINITION_MISSING",
            metric_code,
        )

    def evidence(self, metric_code: str) -> M3ReleaseEvidenceSnapshot:
        for item in self.evidence_bindings:
            if item.metric_code == metric_code:
                return item
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_EVIDENCE_MISSING",
            metric_code,
        )

    def logical_membership(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "release_no": self.release_no,
            "parent_release_id": self.parent_release_id,
            "session_id": self.session_id,
            "request_hash": self.request_hash,
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "catalog_hash": self.catalog_hash,
            "metric_execution_plan_hash": self.metric_execution_plan_hash,
            "publication_routing_plan_hash": self.publication_routing_plan_hash,
            "execution_batch_hash": self.execution_batch_hash,
            "plugin_manifest_hash": self.plugin_manifest_hash,
            "bindings": self.bindings.projection(),
            "definitions": [item.projection() for item in self.definitions],
            "execution_records": [
                item.projection() for item in self.execution_records
            ],
            "evidence_bindings": [
                item.projection() for item in self.evidence_bindings
            ],
            "manifest_hash": self.manifest_hash,
            "status": self.status,
        }


def allocate_m3_release_id(*, session_id: str, request_hash: str) -> str:
    canonical_session_id = _canonical_uuid(session_id, field="session_id")
    canonical_request_hash = _require_hash(request_hash, field="request_hash")
    return str(
        uuid5(
            M3_RELEASE_NAMESPACE,
            f"{canonical_session_id}|{canonical_request_hash}",
        )
    )


def build_m3_release_snapshot(
    *,
    session_id: str,
    request_hash: str,
    release_no: int,
    parent_release_id: str | None,
    plan: M2MetricExecutionPlan,
    routing: M3PublicationRoutingPlan,
    batch: M2MetricExecutionBatch,
    evidence_by_metric: Mapping[str, Mapping[str, object]],
    context_snapshot: Mapping[str, object],
    world_snapshot: Mapping[str, object],
    identity_snapshot: Mapping[str, object],
    provenance_snapshot: Mapping[str, object],
) -> M3ImmutableReleaseSnapshot:
    """Freeze one exact 116-metric release without persistence/latest lookup."""

    canonical_session_id = _canonical_uuid(session_id, field="session_id")
    canonical_request_hash = _require_hash(request_hash, field="request_hash")
    release_id = allocate_m3_release_id(
        session_id=canonical_session_id,
        request_hash=canonical_request_hash,
    )

    if routing.metric_execution_plan_hash != plan.logical_hash:
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_ROUTING_PLAN_MISMATCH",
            routing.metric_execution_plan_hash,
        )
    if routing.catalog_hash != plan.catalog_sha256:
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_CATALOG_MISMATCH",
            routing.catalog_hash,
        )
    if batch.plan_hash != plan.logical_hash:
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_BATCH_PLAN_MISMATCH",
            batch.plan_hash,
        )
    if (
        plan.metric_codes != routing.metric_codes
        or plan.metric_codes != batch.metric_codes
        or len(plan.metric_codes) != M3_RELEASE_METRIC_COUNT
    ):
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_MEMBERSHIP_INVALID",
            repr((plan.metric_codes, routing.metric_codes, batch.metric_codes)),
        )
    if (
        len(evidence_by_metric) != M3_RELEASE_METRIC_COUNT
        or set(evidence_by_metric) != set(plan.metric_codes)
    ):
        raise M3ReleaseSnapshotError(
            "M3_RELEASE_EVIDENCE_MEMBERSHIP_INVALID",
            repr(tuple(sorted(evidence_by_metric))),
        )

    bindings = M2ReleaseBindingSnapshot.freeze(
        context=context_snapshot,
        world=world_snapshot,
        identity=identity_snapshot,
        provenance=provenance_snapshot,
    )
    records_by_code = {record.metric_code: record for record in batch.records}

    definitions: list[M2ReleaseDefinitionSnapshot] = []
    execution_records: list[M2ReleaseExecutionSnapshot] = []
    evidence_bindings: list[M3ReleaseEvidenceSnapshot] = []
    for definition in plan.definitions:
        target = routing.target(definition.metric_code)
        record = records_by_code[definition.metric_code]
        if (
            target.definition_hash != definition.definition_hash
            or record.semantic_id != definition.semantic_id
            or record.semantic_version != definition.semantic_version
            or record.algorithm_id != definition.algorithm_id
            or record.algorithm_version != definition.algorithm_version
            or record.definition_hash != definition.definition_hash
            or record.authority_lineage_hash != definition.authority_lineage_hash
            or record.plan_hash != plan.logical_hash
        ):
            raise M3ReleaseSnapshotError(
                "M3_RELEASE_EXECUTION_BINDING_MISMATCH",
                definition.metric_code,
            )
        definitions.append(
            M2ReleaseDefinitionSnapshot(
                metric_code=definition.metric_code,
                semantic_id=definition.semantic_id,
                semantic_version=definition.semantic_version,
                definition_hash=definition.definition_hash,
                authority_lineage_hash=definition.authority_lineage_hash,
                subject_type=definition.subject_type,
                observation_lane=definition.observation_lane,
                publication_route=definition.publication_route,
                value_kind=definition.value_kind,
                structured_output_schema_id=(
                    definition.structured_output_schema_id
                ),
                p1_longitudinal_trend_eligibility=(
                    definition.p1_longitudinal_trend_eligibility
                ),
            )
        )
        execution_records.append(
            M2ReleaseExecutionSnapshot(
                metric_code=record.metric_code,
                semantic_id=record.semantic_id,
                semantic_version=record.semantic_version,
                algorithm_id=record.algorithm_id,
                algorithm_version=record.algorithm_version,
                definition_hash=record.definition_hash,
                authority_lineage_hash=record.authority_lineage_hash,
                plan_hash=record.plan_hash,
                input_payload_hash=record.input_payload_hash,
                plugin_id=record.plugin_id,
                dependency_manifest_hash=record.dependency_manifest_hash,
                upstream_result_hashes=record.upstream_result_hashes,
                plugin_output_hash=record.plugin_output_hash,
                record_logical_hash=record.logical_hash,
            )
        )
        evidence_json = _canonical_json(
            evidence_by_metric[definition.metric_code],
            field=f"evidence[{definition.metric_code}]",
        )
        evidence_bindings.append(
            M3ReleaseEvidenceSnapshot(
                metric_code=definition.metric_code,
                definition_hash=definition.definition_hash,
                execution_record_hash=record.logical_hash,
                evidence_json=evidence_json,
                evidence_hash=_hash_json_text(evidence_json),
            )
        )

    definition_tuple = tuple(definitions)
    execution_tuple = tuple(execution_records)
    evidence_tuple = tuple(evidence_bindings)
    manifest_payload = {
        "release_id": release_id,
        "release_no": release_no,
        "parent_release_id": parent_release_id,
        "session_id": canonical_session_id,
        "request_hash": canonical_request_hash,
        "catalog_id": plan.catalog_id,
        "catalog_version": plan.catalog_version,
        "catalog_hash": plan.catalog_sha256,
        "metric_execution_plan_hash": plan.logical_hash,
        "publication_routing_plan_hash": routing.logical_hash,
        "execution_batch_hash": batch.logical_hash,
        "plugin_manifest_hash": batch.plugin_manifest_hash,
        "bindings": bindings.projection(),
        "definitions": [item.projection() for item in definition_tuple],
        "execution_records": [item.projection() for item in execution_tuple],
        "evidence_bindings": [item.projection() for item in evidence_tuple],
    }
    manifest_hash = _canonical_hash(manifest_payload)
    return M3ImmutableReleaseSnapshot(
        release_id=release_id,
        release_no=release_no,
        parent_release_id=parent_release_id,
        session_id=canonical_session_id,
        request_hash=canonical_request_hash,
        catalog_id=plan.catalog_id,
        catalog_version=plan.catalog_version,
        catalog_hash=plan.catalog_sha256,
        metric_execution_plan_hash=plan.logical_hash,
        publication_routing_plan_hash=routing.logical_hash,
        execution_batch_hash=batch.logical_hash,
        plugin_manifest_hash=batch.plugin_manifest_hash,
        bindings=bindings,
        definitions=definition_tuple,
        execution_records=execution_tuple,
        evidence_bindings=evidence_tuple,
        manifest_hash=manifest_hash,
    )
