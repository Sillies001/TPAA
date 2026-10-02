"""TPAA storage bootstrap and Repository boundary primitives."""

from .bootstrap import (
    EXPECTED_DB_SCHEMA_VERSION,
    BootstrapError,
    BootstrapVerification,
    bootstrap_sqlite,
    postgres_create_statements,
    verify_sqlite,
)
from .object_seal import LocalSealedObjectFlow, ObjectSealError, StagedObject
from .object_store import LocalObjectStore, ObjectStoreError, StoredObject
from .ports import BaselineMetadataRepository, RepositoryBaselineMetadata, RepositoryUnitOfWork
from .postgres_product_repository import PostgreSQLProductPublicationLedger
from .postgres_repository import (
    PostgreSQLBaselineMetadataRepository,
    PostgreSQLRepositoryError,
    PostgreSQLServiceUnitOfWork,
)
from .product_publication import (
    OrphanRecoveryReport,
    ProductPublicationCoordinator,
    ProductPublicationError,
    ProductPublicationLedger,
    ProductPublicationReceipt,
    ProductPublicationRegistration,
    ProductPublicationRequest,
    ProductPublicationResult,
    ProductPublicationUnitOfWork,
    ProductReleaseIdentity,
    recover_sealed_orphans,
)
from .sqlite_product_repository import SQLiteProductPublicationLedger
from .sqlite_repository import (
    SQLiteBaselineMetadataRepository,
    SQLiteDesktopUnitOfWork,
    SQLiteRepositoryError,
    sqlite_repository_smoke,
)

__all__ = [
    "EXPECTED_DB_SCHEMA_VERSION",
    "BaselineMetadataRepository",
    "LocalObjectStore",
    "LocalSealedObjectFlow",
    "ObjectSealError",
    "ObjectStoreError",
    "StagedObject",
    "StoredObject",
    "BootstrapError",
    "BootstrapVerification",
    "RepositoryBaselineMetadata",
    "RepositoryUnitOfWork",
    "OrphanRecoveryReport",
    "PostgreSQLBaselineMetadataRepository",
    "PostgreSQLProductPublicationLedger",
    "PostgreSQLRepositoryError",
    "PostgreSQLServiceUnitOfWork",
    "ProductPublicationCoordinator",
    "ProductPublicationError",
    "ProductPublicationLedger",
    "ProductPublicationReceipt",
    "ProductPublicationRegistration",
    "ProductPublicationRequest",
    "ProductPublicationResult",
    "ProductPublicationUnitOfWork",
    "ProductReleaseIdentity",
    "SQLiteBaselineMetadataRepository",
    "SQLiteProductPublicationLedger",
    "SQLiteDesktopUnitOfWork",
    "SQLiteRepositoryError",
    "bootstrap_sqlite",
    "postgres_create_statements",
    "recover_sealed_orphans",
    "sqlite_repository_smoke",
    "verify_sqlite",
]
