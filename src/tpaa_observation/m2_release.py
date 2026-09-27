"""Immutable release-bound snapshot substrate for M2 publication.

M2-OBS-002 freezes the exact Catalog definition set, publication-routing plan,
execution-record hashes, and explicit Context/World/identity/provenance
bindings into one deterministic SESSION Release snapshot. The snapshot never
resolves "latest" authority and does not perform persistence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid5

from tpaa_metric import M2MetricExecutionBatch, M2MetricExecutionPlan

from .m2_publication import M2PublicationRoutingPlan

M2_RELEASE_NAMESPACE = UUID("a77843b3-44ab-4da9-b650-07bc77f8a541")
M2_RELEASE_STATUS = "VALIDATED"


class M2ReleaseSnapshotError(RuntimeError):
    """Deterministic fail-closed error for immutable M2 Release snapshots."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _canonical_uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_UUID_INVALID",
            f"{field}={value!r}",
        )
    return canonical


def _require_hash(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_HASH_INVALID",
            f"{field}={value!r}",
        )
    return value


def _canonical_json(value: Mapping[str, object], *, field: str) -> str:
    if not value:
        raise M2ReleaseSnapshotError("M2_RELEASE_BINDING_EMPTY", field)
    try:
        return json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_BINDING_NOT_CANONICAL_JSON",
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
class M2ReleaseBindingSnapshot:
    context_json: str
    context_hash: str
    world_json: str
    world_hash: str
    identity_json: str
    identity_hash: str
    provenance_json: str
    provenance_hash: str

    @classmethod
    def freeze(
        cls,
        *,
        context: Mapping[str, object],
        world: Mapping[str, object],
        identity: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> M2ReleaseBindingSnapshot:
        context_json = _canonical_json(context, field="context")
        world_json = _canonical_json(world, field="world")
        identity_json = _canonical_json(identity, field="identity")
        provenance_json = _canonical_json(provenance, field="provenance")
        return cls(
            context_json=context_json,
            context_hash=_hash_json_text(context_json),
            world_json=world_json,
            world_hash=_hash_json_text(world_json),
            identity_json=identity_json,
            identity_hash=_hash_json_text(identity_json),
            provenance_json=provenance_json,
            provenance_hash=_hash_json_text(provenance_json),
        )

    def projection(self) -> dict[str, object]:
        return {
            "context_json": self.context_json,
            "context_hash": self.context_hash,
            "world_json": self.world_json,
            "world_hash": self.world_hash,
            "identity_json": self.identity_json,
            "identity_hash": self.identity_hash,
            "provenance_json": self.provenance_json,
            "provenance_hash": self.provenance_hash,
        }


@dataclass(frozen=True)
class M2ReleaseDefinitionSnapshot:
    metric_code: str
    semantic_id: str
    semantic_version: int
    definition_hash: str
    authority_lineage_hash: str
    subject_type: str
    observation_lane: str
    publication_route: str
    value_kind: str
    structured_output_schema_id: str | None
    p1_longitudinal_trend_eligibility: bool

    def projection(self) -> dict[str, object]:
        return {
            "metric_code": self.metric_code,
            "semantic_id": self.semantic_id,
            "semantic_version": self.semantic_version,
            "definition_hash": self.definition_hash,
            "authority_lineage_hash": self.authority_lineage_hash,
            "subject_type": self.subject_type,
            "observation_lane": self.observation_lane,
            "publication_route": self.publication_route,
            "value_kind": self.value_kind,
            "structured_output_schema_id": self.structured_output_schema_id,
            "p1_longitudinal_trend_eligibility": (
                self.p1_longitudinal_trend_eligibility
            ),
        }


@dataclass(frozen=True)
class M2ReleaseExecutionSnapshot:
    metric_code: str
    semantic_id: str
    semantic_version: int
    algorithm_id: str
    algorithm_version: str
    definition_hash: str
    authority_lineage_hash: str
    plan_hash: str
    input_payload_hash: str
    plugin_id: str
    dependency_manifest_hash: str
    upstream_result_hashes: tuple[tuple[str, str], ...]
    plugin_output_hash: str
    record_logical_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "metric_code": self.metric_code,
            "semantic_id": self.semantic_id,
            "semantic_version": self.semantic_version,
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "definition_hash": self.definition_hash,
            "authority_lineage_hash": self.authority_lineage_hash,
            "plan_hash": self.plan_hash,
            "input_payload_hash": self.input_payload_hash,
            "plugin_id": self.plugin_id,
            "dependency_manifest_hash": self.dependency_manifest_hash,
            "upstream_result_hashes": [
                [code, logical_hash]
                for code, logical_hash in self.upstream_result_hashes
            ],
            "plugin_output_hash": self.plugin_output_hash,
            "record_logical_hash": self.record_logical_hash,
        }


@dataclass(frozen=True)
class M2ImmutableReleaseSnapshot:
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
    manifest_hash: str
    status: str = M2_RELEASE_STATUS

    def __post_init__(self) -> None:
        _canonical_uuid(self.release_id, field="release_id")
        _canonical_uuid(self.session_id, field="session_id")
        if self.parent_release_id is not None:
            _canonical_uuid(self.parent_release_id, field="parent_release_id")
        if self.release_no < 1:
            raise M2ReleaseSnapshotError(
                "M2_RELEASE_NO_INVALID",
                str(self.release_no),
            )
        if (self.release_no == 1) != (self.parent_release_id is None):
            raise M2ReleaseSnapshotError(
                "M2_RELEASE_PARENT_CHAIN_INVALID",
                f"release_no={self.release_no} parent={self.parent_release_id}",
            )
        if self.parent_release_id == self.release_id:
            raise M2ReleaseSnapshotError(
                "M2_RELEASE_PARENT_CHAIN_INVALID",
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
        if self.status != M2_RELEASE_STATUS:
            raise M2ReleaseSnapshotError(
                "M2_RELEASE_STATUS_INVALID",
                self.status,
            )
        if len(self.definitions) != 32 or len(self.execution_records) != 32:
            raise M2ReleaseSnapshotError(
                "M2_RELEASE_FOUNDATION_MEMBERSHIP_INVALID",
                f"{len(self.definitions)}/{len(self.execution_records)}",
            )

    @property
    def metric_codes(self) -> tuple[str, ...]:
        return tuple(item.metric_code for item in self.definitions)

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
            "manifest_hash": self.manifest_hash,
            "status": self.status,
        }


def allocate_m2_release_id(*, session_id: str, request_hash: str) -> str:
    canonical_session_id = _canonical_uuid(session_id, field="session_id")
    canonical_request_hash = _require_hash(request_hash, field="request_hash")
    return str(
        uuid5(
            M2_RELEASE_NAMESPACE,
            f"{canonical_session_id}|{canonical_request_hash}",
        )
    )


def build_m2_release_snapshot(
    *,
    session_id: str,
    request_hash: str,
    release_no: int,
    parent_release_id: str | None,
    plan: M2MetricExecutionPlan,
    routing: M2PublicationRoutingPlan,
    batch: M2MetricExecutionBatch,
    context_snapshot: Mapping[str, object],
    world_snapshot: Mapping[str, object],
    identity_snapshot: Mapping[str, object],
    provenance_snapshot: Mapping[str, object],
) -> M2ImmutableReleaseSnapshot:
    """Freeze one exact, release-bound M2 SESSION product without persistence."""

    canonical_session_id = _canonical_uuid(session_id, field="session_id")
    canonical_request_hash = _require_hash(request_hash, field="request_hash")
    release_id = allocate_m2_release_id(
        session_id=canonical_session_id,
        request_hash=canonical_request_hash,
    )

    if routing.metric_execution_plan_hash != plan.logical_hash:
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_ROUTING_PLAN_MISMATCH",
            routing.metric_execution_plan_hash,
        )
    if routing.catalog_hash != plan.catalog_sha256:
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_CATALOG_MISMATCH",
            routing.catalog_hash,
        )
    if batch.plan_hash != plan.logical_hash:
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_BATCH_PLAN_MISMATCH",
            batch.plan_hash,
        )
    if (
        plan.metric_codes != routing.metric_codes
        or plan.metric_codes != batch.metric_codes
        or len(plan.metric_codes) != 32
    ):
        raise M2ReleaseSnapshotError(
            "M2_RELEASE_FOUNDATION_MEMBERSHIP_INVALID",
            repr((plan.metric_codes, routing.metric_codes, batch.metric_codes)),
        )

    bindings = M2ReleaseBindingSnapshot.freeze(
        context=context_snapshot,
        world=world_snapshot,
        identity=identity_snapshot,
        provenance=provenance_snapshot,
    )
    records_by_code = {
        record.metric_code: record
        for record in batch.records
    }

    definitions: list[M2ReleaseDefinitionSnapshot] = []
    execution_records: list[M2ReleaseExecutionSnapshot] = []
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
            raise M2ReleaseSnapshotError(
                "M2_RELEASE_EXECUTION_BINDING_MISMATCH",
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

    definition_tuple = tuple(definitions)
    execution_tuple = tuple(execution_records)
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
        "execution_records": [
            item.projection() for item in execution_tuple
        ],
    }
    manifest_hash = _canonical_hash(manifest_payload)
    return M2ImmutableReleaseSnapshot(
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
        manifest_hash=manifest_hash,
    )
