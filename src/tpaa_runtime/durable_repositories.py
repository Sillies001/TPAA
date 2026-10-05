"""PRCB transaction-scoped durable adapters for production Application repositories."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, Self, TypeVar

from tpaa_application.m6_workspace import (
    M6ApplicationError,
    M6P2WorkspaceSnapshot,
)
from tpaa_application.m7_workspace import (
    M7ApplicationError,
    M7P3WorkspaceSnapshot,
)
from tpaa_application.m8_workspace import M8ApplicationError
from tpaa_application.m9_workspace import M9ApplicationError
from tpaa_application.p2_persistence import (
    P2PersistenceError,
    P2PersistenceRepository,
)
from tpaa_application.p3_persistence import (
    CanonicalP3WorkspaceLayerResolver,
    DurableM7P3WorkspaceRepository,
    P3PersistenceError,
    P3PersistenceRepository,
)
from tpaa_application.p4_p5_persistence import (
    P4P5PersistenceError,
    P4P5PersistenceRepository,
)
from tpaa_application.p6_persistence import (
    DurableP6ModelBuildResolver,
    P6PersistenceError,
    P6PersistenceRepository,
)
from tpaa_assessment import (
    InstructorAnnotationRevision,
    P4AssessmentRevision,
    P5AssessmentRevision,
)
from tpaa_assessment.p6_recommendation import P6RecommendationRevision
from tpaa_capability.p6_counterfactual import P6CounterfactualRevision
from tpaa_capability.p6_forecast import (
    P6ForecastRevision,
    P6ManagedModelObject,
    P6ModelBuild,
    P6ModelRevision,
)
from tpaa_capability.p6_input import (
    P6CounterfactualRequestBinding,
    P6ForecastRequestBinding,
    P6InputSnapshot,
)
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.object_store import LocalObjectStore
from tpaa_storage.ports import RepositoryUnitOfWork

_T = TypeVar("_T")


class RuntimePublicationLedger(Protocol):
    """Exact Core Release membership read surface shared by SQLite/PostgreSQL."""

    def logical_membership(self, release_id: str) -> dict[str, object]: ...


class RuntimeCanonicalUnitOfWork(RepositoryUnitOfWork, Protocol):
    """Existing Repository UoW plus DB 1.9 canonical/publication access."""

    canonical_rows: CanonicalRowRepository
    publication: RuntimePublicationLedger

    def __enter__(self) -> Self: ...


RuntimeUnitOfWorkFactory = Callable[[], RuntimeCanonicalUnitOfWork]


class DurableM6P2RuntimeRepository:
    """M6 port backed by exact durable P2 and Core DB 1.9 authorities."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        *,
        object_store: LocalObjectStore,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._object_store = object_store

    def exact(self, estimate_id: str) -> M6P2WorkspaceSnapshot:
        try:
            with self._read_uow_factory() as uow:
                material = P2PersistenceRepository(
                    uow.canonical_rows,
                    object_store=self._object_store,
                ).exact_workspace_material(estimate_id)
                uow.commit()
        except P2PersistenceError as exc:
            raise M6ApplicationError(exc.code, exc.detail) from exc
        return M6P2WorkspaceSnapshot(
            p2_release_id=material.p2_release_id,
            p2_release_status=material.p2_release_status,
            p2_release_sealed=material.p2_release_sealed,
            p2_published_at_utc=material.p2_published_at_utc,
            input_bundle=material.input_bundle,
            target_feature_set=material.target_feature_set,
            attribution_run=material.attribution_run,
            adjusted_estimate=material.adjusted_estimate,
            model_artifact_json=material.model_artifact_json,
        )


class DurableM7P3RuntimeRepository:
    """Long-lived M7 port backed by a fresh durable read transaction per call."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        *,
        object_store: LocalObjectStore,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._object_store = object_store

    def _repository(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> DurableM7P3WorkspaceRepository:
        p2 = P2PersistenceRepository(
            uow.canonical_rows,
            object_store=self._object_store,
        )
        p3 = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=self._object_store,
        )
        return DurableM7P3WorkspaceRepository(
            p3,
            CanonicalP3WorkspaceLayerResolver(uow.canonical_rows, p3, p2),
        )

    def exact_twin(self, twin_revision_id: str) -> M7P3WorkspaceSnapshot:
        try:
            with self._read_uow_factory() as uow:
                value = self._repository(uow).exact_twin(twin_revision_id)
                uow.commit()
                return value
        except P3PersistenceError as exc:
            raise M7ApplicationError(exc.code, exc.detail) from exc

    def exact_estimate(self, estimate_id: str) -> M7P3WorkspaceSnapshot:
        try:
            with self._read_uow_factory() as uow:
                value = self._repository(uow).exact_estimate(estimate_id)
                uow.commit()
                return value
        except P3PersistenceError as exc:
            raise M7ApplicationError(exc.code, exc.detail) from exc


class DurableM8AssessmentRuntimeRepository:
    """M8 repository port over fresh DB 1.9 read/write transactions."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        write_uow_factory: RuntimeUnitOfWorkFactory,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._write_uow_factory = write_uow_factory

    def _read(
        self,
        loader: Callable[[P4P5PersistenceRepository], _T],
    ) -> _T:
        try:
            with self._read_uow_factory() as uow:
                value = loader(P4P5PersistenceRepository(uow.canonical_rows))
                uow.commit()
                return value
        except P4P5PersistenceError as exc:
            raise M8ApplicationError(exc.code, exc.detail) from exc

    def _write(
        self,
        writer: Callable[[P4P5PersistenceRepository], None],
    ) -> None:
        try:
            with self._write_uow_factory() as uow:
                writer(P4P5PersistenceRepository(uow.canonical_rows))
                uow.commit()
        except P4P5PersistenceError as exc:
            raise M8ApplicationError(exc.code, exc.detail) from exc

    def register_p4(self, revision: P4AssessmentRevision) -> None:
        self._write(lambda repository: repository.register_p4(revision))

    def register_p5(self, revision: P5AssessmentRevision) -> None:
        self._write(lambda repository: repository.register_p5(revision))

    def register_annotation(self, revision: InstructorAnnotationRevision) -> None:
        self._write(lambda repository: repository.register_annotation(revision))

    def exact_p4(self, revision_id: str) -> P4AssessmentRevision:
        return self._read(lambda repository: repository.exact_p4(revision_id))

    def exact_p5(self, revision_id: str) -> P5AssessmentRevision:
        return self._read(lambda repository: repository.exact_p5(revision_id))

    def exact_annotation(self, annotation_id: str) -> InstructorAnnotationRevision:
        return self._read(
            lambda repository: repository.exact_annotation(annotation_id)
        )


class DurableM9P6RuntimeRepository:
    """M9 P6 repository port over DB 1.9 plus the governed object store."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        write_uow_factory: RuntimeUnitOfWorkFactory,
        *,
        object_store: LocalObjectStore,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._write_uow_factory = write_uow_factory
        self._object_store = object_store

    def _repository(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> P6PersistenceRepository:
        return P6PersistenceRepository(
            uow.canonical_rows,
            object_store=self._object_store,
            model_build_resolver=DurableP6ModelBuildResolver(uow.canonical_rows),
        )

    def _read(
        self,
        loader: Callable[[P6PersistenceRepository], _T],
    ) -> _T:
        try:
            with self._read_uow_factory() as uow:
                value = loader(self._repository(uow))
                uow.commit()
                return value
        except P6PersistenceError as exc:
            raise M9ApplicationError(exc.code, exc.detail) from exc

    def _write(
        self,
        writer: Callable[[P6PersistenceRepository], None],
    ) -> None:
        try:
            with self._write_uow_factory() as uow:
                writer(self._repository(uow))
                uow.commit()
        except P6PersistenceError as exc:
            raise M9ApplicationError(exc.code, exc.detail) from exc

    def register_input(self, value: P6InputSnapshot) -> None:
        self._write(lambda repository: repository.register_input(value))

    def register_forecast_request(self, value: P6ForecastRequestBinding) -> None:
        self._write(lambda repository: repository.register_forecast_request(value))

    def register_counterfactual_request(
        self,
        value: P6CounterfactualRequestBinding,
    ) -> None:
        self._write(
            lambda repository: repository.register_counterfactual_request(value)
        )

    def register_model_build(
        self,
        build: P6ModelBuild,
        managed_object: P6ManagedModelObject,
    ) -> None:
        self._write(
            lambda repository: repository.register_model_build(
                build,
                managed_object,
            )
        )

    def register_forecast(self, value: P6ForecastRevision) -> None:
        self._write(lambda repository: repository.register_forecast(value))

    def register_counterfactual(self, value: P6CounterfactualRevision) -> None:
        self._write(lambda repository: repository.register_counterfactual(value))

    def register_recommendation(self, value: P6RecommendationRevision) -> None:
        self._write(lambda repository: repository.register_recommendation(value))

    def replace_model_release(self, model: P6ModelRevision) -> None:
        self._write(lambda repository: repository.replace_model_release(model))

    def exact_input(self, object_id: str) -> P6InputSnapshot:
        return self._read(lambda repository: repository.exact_input(object_id))

    def exact_forecast_request(self, object_id: str) -> P6ForecastRequestBinding:
        return self._read(
            lambda repository: repository.exact_forecast_request(object_id)
        )

    def exact_counterfactual_request(
        self,
        object_id: str,
    ) -> P6CounterfactualRequestBinding:
        return self._read(
            lambda repository: repository.exact_counterfactual_request(object_id)
        )

    def exact_model_build(self, object_id: str) -> P6ModelBuild:
        return self._read(
            lambda repository: repository.exact_model_build(object_id)
        )

    def exact_managed_object(self, model_id: str) -> P6ManagedModelObject:
        return self._read(
            lambda repository: repository.exact_managed_object(model_id)
        )

    def exact_forecast(self, object_id: str) -> P6ForecastRevision:
        return self._read(lambda repository: repository.exact_forecast(object_id))

    def exact_counterfactual(self, object_id: str) -> P6CounterfactualRevision:
        return self._read(
            lambda repository: repository.exact_counterfactual(object_id)
        )

    def exact_recommendation(self, object_id: str) -> P6RecommendationRevision:
        return self._read(
            lambda repository: repository.exact_recommendation(object_id)
        )
