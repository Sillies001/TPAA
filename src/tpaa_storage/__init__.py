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
from .ports import BaselineMetadataRepository, RepositoryBaselineMetadata, RepositoryUnitOfWork
from .publication import (
    InMemorySessionPublicationRepository,
    PublishedReleaseConflict,
    PublishedSessionRelease,
    PublicationRepositoryError,
    PublishCASConflict,
    PublishIdempotencyConflict,
    PublishResult,
    ReleaseNotFound,
    SessionPublicationRepository,
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
    "InMemorySessionPublicationRepository",
    "LocalSealedObjectFlow",
    "ObjectSealError",
    "PublicationRepositoryError",
    "PublishedReleaseConflict",
    "PublishedSessionRelease",
    "PublishCASConflict",
    "PublishIdempotencyConflict",
    "PublishResult",
    "ReleaseNotFound",
    "RepositoryBaselineMetadata",
    "RepositoryUnitOfWork",
    "SQLiteBaselineMetadataRepository",
    "SQLiteDesktopUnitOfWork",
    "SQLiteRepositoryError",
    "SessionPublicationRepository",
    "StagedObject",
    "bootstrap_sqlite",
    "postgres_create_statements",
    "sqlite_repository_smoke",
    "verify_sqlite",
]
