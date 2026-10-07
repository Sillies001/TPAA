"""M7 exact-revision P3 twin/estimate Application read projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from tpaa_capability import (
    P3AircraftTwinRevision,
    P3CapabilityEstimate,
    P3TwinComponentBinding,
)
from tpaa_longitudinal import (
    P3AdmissionEvidence,
    P3GovernanceError,
    assert_capability_claim_allowed,
    assert_p3_claim_level,
)


class M7ApplicationError(RuntimeError):
    """Fail-closed M7 exact-revision read-model error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class M7TwinQuery:
    twin_revision_id: str


@dataclass(frozen=True, slots=True)
class M7EstimateQuery:
    twin_revision_id: str
    estimate_id: str


@dataclass(frozen=True, slots=True)
class M7WorkspaceQuery:
    twin_revision_id: str
    estimate_id: str


@dataclass(frozen=True, slots=True)
class M7LayerEvidence:
    layer: str
    release_id: str
    logical_hash: str
    projection: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class M7P3TwinSnapshot:
    twin: P3AircraftTwinRevision
    components: tuple[P3TwinComponentBinding, ...]


@dataclass(frozen=True, slots=True)
class M7P3WorkspaceSnapshot:
    observed: M7LayerEvidence
    adjusted: M7LayerEvidence
    twin: P3AircraftTwinRevision
    estimate: P3CapabilityEstimate
    components: tuple[P3TwinComponentBinding, ...]


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M7ApplicationError("M7_DTO_UUID_INVALID", field) from exc
    if str(parsed) != value or parsed.int == 0:
        raise M7ApplicationError("M7_DTO_UUID_INVALID", field)
    return value


def _hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M7ApplicationError("M7_DTO_HASH_INVALID", field)
    return value


def _canonical_hash(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise M7ApplicationError(
            "M7_DTO_CANONICAL_JSON_INVALID",
            type(exc).__name__,
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _validate_layer(
    value: M7LayerEvidence,
    *,
    expected_layer: str,
) -> None:
    if value.layer != expected_layer:
        raise M7ApplicationError(
            "M7_LAYER_IDENTITY_MISMATCH",
            f"{value.layer}:{expected_layer}",
        )
    _uuid(value.release_id, field=f"{expected_layer}.release_id")
    _hash64(value.logical_hash, field=f"{expected_layer}.logical_hash")
    actual = _canonical_hash(dict(value.projection))
    if actual != value.logical_hash:
        raise M7ApplicationError(
            "M7_LAYER_LOGICAL_HASH_MISMATCH",
            expected_layer,
        )


def _validate_twin_snapshot(value: M7P3TwinSnapshot) -> None:
    _uuid(value.twin.twin_revision_id, field="twin_revision_id")
    if value.twin.status != "PUBLISHED":
        raise M7ApplicationError(
            "M7_TWIN_STATUS_INVALID",
            value.twin.twin_revision_id,
        )
    component_ids = tuple(
        component.model_build.model.capability_model_id
        for component in value.components
    )
    if component_ids != value.twin.component_model_refs:
        raise M7ApplicationError(
            "M7_TWIN_COMPONENT_ORDER_MISMATCH",
            value.twin.twin_revision_id,
        )


def _validate_snapshot(value: M7P3WorkspaceSnapshot) -> None:
    _validate_layer(value.observed, expected_layer="P1_OBSERVED")
    _validate_layer(value.adjusted, expected_layer="P2_ADJUSTED")
    _validate_twin_snapshot(
        M7P3TwinSnapshot(
            twin=value.twin,
            components=value.components,
        )
    )
    _uuid(value.estimate.estimate_id, field="estimate_id")
    if value.estimate.twin_revision_id != value.twin.twin_revision_id:
        raise M7ApplicationError(
            "M7_TWIN_ESTIMATE_MISMATCH",
            value.estimate.estimate_id,
        )
    try:
        assert_p3_claim_level(value.estimate.claim_level)
    except P3GovernanceError as exc:
        raise M7ApplicationError(exc.code, exc.detail) from exc
    matching = [
        component
        for component in value.components
        if component.model_build.model.capability_type
        == value.estimate.capability_type
    ]
    if len(matching) != 1:
        raise M7ApplicationError(
            "M7_ESTIMATE_COMPONENT_MISMATCH",
            value.estimate.capability_type,
        )


class M7P3WorkspaceRepository(Protocol):
    """Engine-neutral exact P3 twin/estimate repository port."""

    def exact_twin(self, twin_revision_id: str) -> M7P3TwinSnapshot:
        """Return one immutable exact twin revision plus ordered components."""

    def exact_estimate(self, estimate_id: str) -> M7P3WorkspaceSnapshot:
        """Return one immutable exact estimate snapshot."""


class InMemoryM7P3WorkspaceRepository:
    """Immutable exact-identity M7 read repository used by Application/API tests."""

    def __init__(self) -> None:
        self._snapshots_by_estimate: dict[str, M7P3WorkspaceSnapshot] = {}
        self._snapshots_by_twin: dict[str, M7P3TwinSnapshot] = {}

    def register(self, snapshot: M7P3WorkspaceSnapshot) -> None:
        _validate_snapshot(snapshot)
        estimate_id = snapshot.estimate.estimate_id
        twin_revision_id = snapshot.twin.twin_revision_id
        existing_estimate = self._snapshots_by_estimate.get(estimate_id)
        if existing_estimate is not None and existing_estimate != snapshot:
            raise M7ApplicationError("M7_P3_IMMUTABLE_CONFLICT", estimate_id)
        twin_snapshot = M7P3TwinSnapshot(
            twin=snapshot.twin,
            components=snapshot.components,
        )
        existing_twin = self._snapshots_by_twin.get(twin_revision_id)
        if existing_twin is not None and existing_twin != twin_snapshot:
            raise M7ApplicationError(
                "M7_P3_IMMUTABLE_CONFLICT",
                twin_revision_id,
            )
        self._snapshots_by_estimate[estimate_id] = snapshot
        self._snapshots_by_twin[twin_revision_id] = twin_snapshot

    def exact_twin(self, twin_revision_id: str) -> M7P3TwinSnapshot:
        _uuid(twin_revision_id, field="twin_revision_id")
        try:
            return self._snapshots_by_twin[twin_revision_id]
        except KeyError as exc:
            raise M7ApplicationError(
                "M7_P3_TWIN_NOT_FOUND",
                twin_revision_id,
            ) from exc

    def exact_estimate(self, estimate_id: str) -> M7P3WorkspaceSnapshot:
        _uuid(estimate_id, field="estimate_id")
        try:
            return self._snapshots_by_estimate[estimate_id]
        except KeyError as exc:
            raise M7ApplicationError(
                "M7_P3_ESTIMATE_NOT_FOUND",
                estimate_id,
            ) from exc


class M7WorkspaceService:
    """Admission-gated exact P3 reads; never recomputes model/twin/estimate."""

    def __init__(
        self,
        repository: M7P3WorkspaceRepository,
        *,
        admission_evidence: P3AdmissionEvidence | None = None,
    ) -> None:
        self._repository = repository
        self._admission_evidence = admission_evidence

    def _assert_admitted(self) -> None:
        try:
            assert_capability_claim_allowed(
                "P3",
                evidence=self._admission_evidence,
            )
        except P3GovernanceError as exc:
            raise M7ApplicationError("M7_P3_NOT_ADMITTED", exc.detail) from exc

    def _exact_twin(
        self,
        twin_revision_id: str,
    ) -> M7P3TwinSnapshot:
        self._assert_admitted()
        snapshot = self._repository.exact_twin(twin_revision_id)
        if snapshot.twin.twin_revision_id != twin_revision_id:
            raise M7ApplicationError(
                "M7_TWIN_IDENTITY_MISMATCH",
                twin_revision_id,
            )
        _validate_twin_snapshot(snapshot)
        return snapshot

    def _exact_estimate(
        self,
        *,
        twin_revision_id: str,
        estimate_id: str,
    ) -> M7P3WorkspaceSnapshot:
        self._assert_admitted()
        snapshot = self._repository.exact_estimate(estimate_id)
        if snapshot.twin.twin_revision_id != twin_revision_id:
            raise M7ApplicationError(
                "M7_TWIN_ESTIMATE_MISMATCH",
                f"{twin_revision_id}:{estimate_id}",
            )
        _validate_snapshot(snapshot)
        return snapshot

    @staticmethod
    def _components(
        snapshot: M7P3TwinSnapshot | M7P3WorkspaceSnapshot,
    ) -> list[dict[str, object]]:
        return [
            {
                **component.projection(),
                "model": component.model_build.model.projection(),
                "surface": component.surface_build.surface.projection(),
            }
            for component in snapshot.components
        ]

    def twin(self, query: M7TwinQuery) -> dict[str, object]:
        snapshot = self._exact_twin(query.twin_revision_id)
        product = {
            "twin": snapshot.twin.projection(),
            "components": self._components(snapshot),
        }
        return {
            **product,
            "logical_product_hash": _canonical_hash(product),
        }

    def estimate(self, query: M7EstimateQuery) -> dict[str, object]:
        snapshot = self._exact_estimate(
            twin_revision_id=query.twin_revision_id,
            estimate_id=query.estimate_id,
        )
        product = {
            "identity": {
                "twin_revision_id": snapshot.twin.twin_revision_id,
                "estimate_id": snapshot.estimate.estimate_id,
                "aircraft_id": snapshot.twin.aircraft_id,
                "capability_type": snapshot.estimate.capability_type,
            },
            "estimate": snapshot.estimate.projection(),
        }
        return {
            **product,
            "logical_product_hash": _canonical_hash(product),
        }

    def workspace(self, query: M7WorkspaceQuery) -> dict[str, object]:
        snapshot = self._exact_estimate(
            twin_revision_id=query.twin_revision_id,
            estimate_id=query.estimate_id,
        )
        observed_projection = dict(snapshot.observed.projection)
        adjusted_projection = dict(snapshot.adjusted.projection)
        p3_projection = {
            "layer": "P3_REFERENCE_CONDITION_LONGITUDINAL",
            "twin": snapshot.twin.projection(),
            "estimate": snapshot.estimate.projection(),
            "components": self._components(snapshot),
        }
        product = {
            "identity": {
                "twin_revision_id": snapshot.twin.twin_revision_id,
                "estimate_id": snapshot.estimate.estimate_id,
                "aircraft_id": snapshot.twin.aircraft_id,
                "capability_type": snapshot.estimate.capability_type,
                "p1_release_id": snapshot.observed.release_id,
                "p2_release_id": snapshot.adjusted.release_id,
            },
            "observed": {
                "layer": snapshot.observed.layer,
                "release_id": snapshot.observed.release_id,
                "logical_hash": snapshot.observed.logical_hash,
                "projection": observed_projection,
            },
            "adjusted": {
                "layer": snapshot.adjusted.layer,
                "release_id": snapshot.adjusted.release_id,
                "logical_hash": snapshot.adjusted.logical_hash,
                "projection": adjusted_projection,
            },
            "p3": p3_projection,
        }
        return {
            **product,
            "logical_product_hash": _canonical_hash(product),
        }
