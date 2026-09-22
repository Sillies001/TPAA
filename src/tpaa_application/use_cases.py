"""M0 Application use cases.

These use cases depend only on engine-neutral ports. They do not own runtime READY
handshake semantics; M0-CORE-006 remains the authority for that later task.
"""

from __future__ import annotations

from .models import StorageBaselineStatus
from .ports import RepositoryUnitOfWorkFactory


class GetStorageBaselineStatus:
    """Read persisted bootstrap provenance through the Repository port."""

    def __init__(self, unit_of_work_factory: RepositoryUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def execute(self) -> StorageBaselineStatus:
        """Return engine-neutral persisted baseline metadata without committing."""

        with self._unit_of_work_factory() as unit_of_work:
            metadata = unit_of_work.metadata.get()
        return StorageBaselineStatus(
            engine_profile=metadata.engine_profile,
            schema_version=metadata.schema_version,
            core_baseline=metadata.core_baseline,
            authority_artifact_id=metadata.authority_artifact_id,
            authority_sha256=metadata.authority_sha256,
            baseline_lock_sha256=metadata.baseline_lock_sha256,
            physical_schema_sha256=metadata.physical_schema_sha256,
        )
