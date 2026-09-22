"""TPAA storage bootstrap and Repository boundary primitives."""

from .bootstrap import (
    EXPECTED_DB_SCHEMA_VERSION,
    BootstrapError,
    BootstrapVerification,
    bootstrap_sqlite,
    postgres_create_statements,
    verify_sqlite,
)

__all__ = [
    "EXPECTED_DB_SCHEMA_VERSION",
    "BootstrapError",
    "BootstrapVerification",
    "bootstrap_sqlite",
    "postgres_create_statements",
    "verify_sqlite",
]

from .ports import BaselineMetadataRepository, RepositoryBaselineMetadata, RepositoryUnitOfWork
from .sqlite_repository import (
    SQLiteBaselineMetadataRepository,
    SQLiteDesktopUnitOfWork,
    SQLiteRepositoryError,
    sqlite_repository_smoke,
)

__all__.extend([
    "BaselineMetadataRepository",
    "RepositoryBaselineMetadata",
    "RepositoryUnitOfWork",
    "SQLiteBaselineMetadataRepository",
    "SQLiteDesktopUnitOfWork",
    "SQLiteRepositoryError",
    "sqlite_repository_smoke",
])
