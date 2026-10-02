"""TPAA storage bootstrap and Repository boundary primitives."""

from .bootstrap import (
    EXPECTED_DB_SCHEMA_VERSION,
    BootstrapError,
    BootstrapVerification,
    bootstrap_sqlite,
    postgres_create_statements,
    verify_sqlite,
)
from .ports import BaselineMetadataRepository, RepositoryBaselineMetadata, RepositoryUnitOfWork
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
    recover_sealed_orphans,
)
from .sqlite_repository import (
    SQLiteBaselineMetadataRepository,
    SQLiteDesktopUnitOfWork,
    SQLiteRepositoryError,
    sqlite_repository_smoke,
)

__all__ = [
    "EXPECTED_DB_SCHEMA_VERSION",
    "BaselineMetadataRepository",
    "BootstrapError",
    "BootstrapVerification",
    "RepositoryBaselineMetadata",
    "RepositoryUnitOfWork",
    "OrphanRecoveryReport",
    "ProductPublicationCoordinator",
    "ProductPublicationError",
    "ProductPublicationLedger",
    "ProductPublicationReceipt",
    "ProductPublicationRegistration",
    "ProductPublicationRequest",
    "ProductPublicationResult",
    "ProductPublicationUnitOfWork",
    "SQLiteBaselineMetadataRepository",
    "SQLiteDesktopUnitOfWork",
    "SQLiteRepositoryError",
    "bootstrap_sqlite",
    "postgres_create_statements",
    "recover_sealed_orphans",
    "sqlite_repository_smoke",
    "verify_sqlite",
]
