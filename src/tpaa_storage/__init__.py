"""TPAA storage bootstrap and Repository boundary primitives."""

from .bootstrap import (
    EXPECTED_DB_SCHEMA_VERSION,
    BootstrapError,
    BootstrapVerification,
    bootstrap_sqlite,
    postgres_create_statements,
    verify_sqlite,
)
from .canonical_rows import (
    CanonicalRowRepository,
    CanonicalRowRepositoryError,
    PostgreSQLCanonicalRowRepository,
    SQLiteCanonicalRowRepository,
)
from .object_seal import LocalSealedObjectFlow, ObjectSealError, StagedObject
from .object_store import LocalObjectStore, ObjectStoreError, StoredObject
from .parquet_plane import (
    ParquetColumn,
    ParquetDatasetArtifact,
    ParquetPartition,
    ParquetPlaneError,
    ParquetScalarType,
    ParquetSchema,
    ParquetWriteRequest,
    PolarsParquetPlane,
)
from .persistence_fit import (
    PersistenceFitError,
    PersistenceFitRecord,
    ProductPersistenceFitGate,
)
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
    StagingRecoveryReport,
    recover_registered_product_orphans,
    recover_sealed_orphans,
    recover_staging_orphans,
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
    "CanonicalRowRepository",
    "CanonicalRowRepositoryError",
    "ParquetColumn",
    "ParquetDatasetArtifact",
    "ParquetPartition",
    "ParquetPlaneError",
    "ParquetScalarType",
    "ParquetSchema",
    "ParquetWriteRequest",
    "PolarsParquetPlane",
    "OrphanRecoveryReport",
    "PostgreSQLBaselineMetadataRepository",
    "PostgreSQLCanonicalRowRepository",
    "PostgreSQLProductPublicationLedger",
    "PostgreSQLRepositoryError",
    "PostgreSQLServiceUnitOfWork",
    "PersistenceFitError",
    "PersistenceFitRecord",
    "ProductPersistenceFitGate",
    "ProductPublicationCoordinator",
    "ProductPublicationError",
    "ProductPublicationLedger",
    "ProductPublicationReceipt",
    "ProductPublicationRegistration",
    "ProductPublicationRequest",
    "ProductPublicationResult",
    "ProductPublicationUnitOfWork",
    "ProductReleaseIdentity",
    "StagingRecoveryReport",
    "SQLiteBaselineMetadataRepository",
    "SQLiteCanonicalRowRepository",
    "SQLiteProductPublicationLedger",
    "SQLiteDesktopUnitOfWork",
    "SQLiteRepositoryError",
    "bootstrap_sqlite",
    "postgres_create_statements",
    "recover_registered_product_orphans",
    "recover_sealed_orphans",
    "recover_staging_orphans",
    "sqlite_repository_smoke",
    "verify_sqlite",
]
