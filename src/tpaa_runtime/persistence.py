"""PIQB B2 persistence composition for Desktop and Service profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tpaa_storage import (
    LocalObjectStore,
    LocalSealedObjectFlow,
    OrphanRecoveryReport,
    PostgreSQLServiceUnitOfWork,
    ProductPersistenceFitGate,
    ProductPublicationCoordinator,
    ProductPublicationLedger,
    SQLiteDesktopUnitOfWork,
    StagingRecoveryReport,
    recover_registered_product_orphans,
    recover_staging_orphans,
    verify_sqlite,
)


class _ProductPublicationReadUnitOfWork(Protocol):
    product_publication: ProductPublicationLedger

    def __enter__(self) -> _ProductPublicationReadUnitOfWork: ...
    def commit(self) -> None: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


@dataclass(frozen=True, slots=True)
class DesktopPersistenceConfig:
    database_path: Path
    object_root: Path

    def __post_init__(self) -> None:
        if not self.database_path.is_file():
            raise ValueError("Desktop database_path must be an existing DB 1.6.0 file")


@dataclass(frozen=True, slots=True)
class ServicePersistenceConfig:
    conninfo: str
    object_root: Path

    def __post_init__(self) -> None:
        if not self.conninfo.strip():
            raise ValueError("Service conninfo must be non-empty")


@dataclass(frozen=True, slots=True)
class ProductPersistenceRuntime:
    """Durable storage composition independent from domain repository availability."""

    fit_gate: ProductPersistenceFitGate
    object_store: LocalObjectStore
    publication: ProductPublicationCoordinator
    _read_uow_factory: object

    def recover_registered_objects(
        self,
        *,
        logical_prefix: str,
        dry_run: bool = True,
    ) -> OrphanRecoveryReport:
        factory = self._read_uow_factory
        if not callable(factory):
            raise RuntimeError("read UoW factory is not callable")
        uow = factory()
        if not isinstance(uow, _ProductPublicationReadUnitOfWork):
            # Structural protocols with data attributes are not reliably runtime-checkable.
            if not (
                hasattr(uow, "__enter__")
                and hasattr(uow, "__exit__")
                and hasattr(uow, "commit")
            ):
                raise RuntimeError("read UoW factory returned invalid unit of work")
        with uow as active:
            report = recover_registered_product_orphans(
                self.object_store,
                active.product_publication,
                logical_prefix=logical_prefix,
                dry_run=dry_run,
            )
            active.commit()
        return report

    def recover_staging(
        self,
        *,
        scheme: str,
        active_operation_ids: tuple[str, ...] = (),
        dry_run: bool = True,
    ) -> StagingRecoveryReport:
        return recover_staging_orphans(
            self.object_store,
            scheme=scheme,
            active_operation_ids=active_operation_ids,
            dry_run=dry_run,
        )


def build_desktop_persistence(
    config: DesktopPersistenceConfig,
) -> ProductPersistenceRuntime:
    """Compose SQLite WAL + local object storage without domain shadow state."""

    verify_sqlite(config.database_path)
    fit_gate = ProductPersistenceFitGate.from_baseline()
    store = LocalObjectStore(config.object_root)
    store.filesystem.ensure_root()

    def write_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(config.database_path, write=True)

    def read_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(config.database_path)

    return ProductPersistenceRuntime(
        fit_gate=fit_gate,
        object_store=store,
        publication=ProductPublicationCoordinator(
            object_flow=LocalSealedObjectFlow(store),
            unit_of_work_factory=write_uow,
        ),
        _read_uow_factory=read_uow,
    )


def build_service_persistence(
    config: ServicePersistenceConfig,
) -> ProductPersistenceRuntime:
    """Compose PostgreSQL + object storage over the same product publication port."""

    fit_gate = ProductPersistenceFitGate.from_baseline()
    store = LocalObjectStore(config.object_root)
    store.filesystem.ensure_root()

    def write_uow() -> PostgreSQLServiceUnitOfWork:
        return PostgreSQLServiceUnitOfWork(config.conninfo)

    def read_uow() -> PostgreSQLServiceUnitOfWork:
        return PostgreSQLServiceUnitOfWork(config.conninfo, read_only=True)

    return ProductPersistenceRuntime(
        fit_gate=fit_gate,
        object_store=store,
        publication=ProductPublicationCoordinator(
            object_flow=LocalSealedObjectFlow(store),
            unit_of_work_factory=write_uow,
        ),
        _read_uow_factory=read_uow,
    )
