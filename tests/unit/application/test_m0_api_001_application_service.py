from __future__ import annotations

from tpaa_application import ApplicationService, GetStorageBaselineStatus, StorageBaselineStatus
from tpaa_storage.ports import RepositoryBaselineMetadata


class _MetadataRepository:
    def __init__(self, metadata: RepositoryBaselineMetadata) -> None:
        self._metadata = metadata
        self.reads = 0

    def get(self) -> RepositoryBaselineMetadata:
        self.reads += 1
        return self._metadata


class _UnitOfWork:
    def __init__(self, metadata: RepositoryBaselineMetadata) -> None:
        self.metadata = _MetadataRepository(metadata)
        self.entered = False
        self.exited = False
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self) -> _UnitOfWork:
        self.entered = True
        return self

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.exited = True


class _Factory:
    def __init__(self, unit_of_work: _UnitOfWork) -> None:
        self.unit_of_work = unit_of_work
        self.calls = 0

    def __call__(self) -> _UnitOfWork:
        self.calls += 1
        return self.unit_of_work


def _metadata() -> RepositoryBaselineMetadata:
    return RepositoryBaselineMetadata(
        engine_profile="sqlite-desktop",
        schema_version="1.6.0",
        core_baseline="CB-1.4.0",
        authority_artifact_id="CORE_LOGICAL_MODEL",
        authority_sha256="authority",
        baseline_lock_sha256="lock",
        physical_schema_sha256="schema",
    )


def test_application_service_reads_storage_metadata_through_uow_port() -> None:
    uow = _UnitOfWork(_metadata())
    factory = _Factory(uow)
    service = ApplicationService(
        get_storage_baseline_status=GetStorageBaselineStatus(factory)
    )

    actual = service.storage_baseline_status()

    assert actual == StorageBaselineStatus(
        engine_profile="sqlite-desktop",
        schema_version="1.6.0",
        core_baseline="CB-1.4.0",
        authority_artifact_id="CORE_LOGICAL_MODEL",
        authority_sha256="authority",
        baseline_lock_sha256="lock",
        physical_schema_sha256="schema",
    )
    assert factory.calls == 1
    assert uow.entered is True
    assert uow.exited is True
    assert uow.metadata.reads == 1
    assert uow.commits == 0
    assert uow.rollbacks == 0


def test_application_service_integrates_with_real_sqlite_repository(tmp_path) -> None:
    from tpaa_storage.bootstrap import bootstrap_sqlite
    from tpaa_storage.sqlite_repository import SQLiteDesktopUnitOfWork

    database = tmp_path / "application-service.sqlite3"
    bootstrap_sqlite(database)
    service = ApplicationService(
        get_storage_baseline_status=GetStorageBaselineStatus(
            lambda: SQLiteDesktopUnitOfWork(database)
        )
    )

    actual = service.storage_baseline_status()

    assert actual.engine_profile == "sqlite-desktop"
    assert actual.schema_version == "1.6.0"
    assert actual.core_baseline == "CB-1.4.0"
    assert actual.authority_artifact_id == "CORE_LOGICAL_MODEL"
