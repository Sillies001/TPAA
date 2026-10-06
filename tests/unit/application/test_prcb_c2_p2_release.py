from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_application import (
    P2ReleaseError,
    P2ReleaseRepository,
    allocate_p2_release_id,
    p2_release_scope_key,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

SESSION = "c2200000-0000-4000-8000-000000000001"
SOURCE_JOB = "c2200000-0000-4000-8000-000000000002"
SOURCE_RELEASE = "c2200000-0000-4000-8000-000000000003"
P2_JOB_1 = "c2200000-0000-4000-8000-000000000004"
P2_JOB_2 = "c2200000-0000-4000-8000-000000000005"
OBSERVATION = "c2200000-0000-4000-8000-000000000006"
REQUEST_HASH_1 = "1" * 64
REQUEST_HASH_2 = "2" * 64
CATALOG_HASH = "3" * 64
CONTEXT_HASH = "4" * 64
SOURCE_MANIFEST = "5" * 64
MANIFEST_1 = "6" * 64
MANIFEST_2 = "7" * 64
WHEN = "2026-10-06T00:00:00Z"


def _seed(database: Path) -> None:
    bootstrap_sqlite(database)
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        uow.canonical_rows.insert(
            "registry.training_session",
            {
                "session_id": SESSION,
                "session_code": "PRCB-C2-P2-RELEASE",
                "session_type": "SIM",
                "start_session_time_us": 0,
                "end_session_time_us": 1,
                "training_type_set": (),
                "data_status": "READY",
                "source_count": 1,
                "schema_version": "1.9.0",
            },
            field_kinds={"training_type_set": "text_array"},
        )
        for job_id, job_key, request_hash, status in (
            (SOURCE_JOB, "source-job", "8" * 64, "SUCCEEDED"),
            (P2_JOB_1, "p2-job-1", REQUEST_HASH_1, "RUNNING"),
            (P2_JOB_2, "p2-job-2", REQUEST_HASH_2, "RUNNING"),
        ):
            uow.canonical_rows.insert(
                "registry.compute_job",
                {
                    "job_id": job_id,
                    "job_type": "P2_ATTRIBUTION",
                    "session_id": SESSION if job_id == SOURCE_JOB else None,
                    "episode_id": None,
                    "job_key": job_key,
                    "status": status,
                    "component_version": "PRCB-C2",
                    "input_hash": request_hash,
                    "progress": 1.0 if status == "SUCCEEDED" else 0.5,
                    "reason_codes": (),
                    "error_detail": None,
                    "started_at": WHEN,
                    "finished_at": WHEN if status == "SUCCEEDED" else None,
                },
                field_kinds={"reason_codes": "text_array"},
            )
        uow.canonical_rows.insert(
            "registry.analysis_release",
            {
                "release_id": SOURCE_RELEASE,
                "scope_type": "SESSION",
                "scope_key": SESSION,
                "session_id": SESSION,
                "longitudinal_scope_id": None,
                "release_no": 1,
                "compute_job_id": SOURCE_JOB,
                "catalog_version": "1.4.0",
                "catalog_hash": CATALOG_HASH,
                "context_binding_hash": CONTEXT_HASH,
                "status": "PUBLISHED",
                "parent_release_id": None,
                "manifest_hash": SOURCE_MANIFEST,
                "created_at": WHEN,
                "published_at": WHEN,
            },
        )
        uow.commit()


def test_prcb_c2_p2_release_uses_existing_job_and_cas(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.db"
    _seed(database)
    scope_key = p2_release_scope_key(OBSERVATION)
    release_1 = allocate_p2_release_id(
        job_id=P2_JOB_1,
        request_hash=REQUEST_HASH_1,
        scope_key=scope_key,
    )
    release_2 = allocate_p2_release_id(
        job_id=P2_JOB_2,
        request_hash=REQUEST_HASH_2,
        scope_key=scope_key,
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repository = P2ReleaseRepository(uow.canonical_rows)
        lineage = repository.source_lineage(SOURCE_RELEASE)
        first = repository.publish(
            job_id=P2_JOB_1,
            release_id=release_1,
            scope_key=scope_key,
            lineage=lineage,
            expected_version_token=0,
            manifest_hash=MANIFEST_1,
            published_at_utc=WHEN,
        )
        assert first.version_token == 1
        assert first.parent_release_id is None
        job = uow.canonical_rows.one(
            "registry.compute_job",
            where={"job_id": P2_JOB_1},
            columns=("session_id", "status"),
        )
        assert job == {"session_id": SESSION, "status": "RUNNING"}
        release = uow.canonical_rows.one(
            "registry.analysis_release",
            where={"release_id": release_1},
            columns=("compute_job_id", "release_no", "parent_release_id", "status"),
        )
        assert release == {
            "compute_job_id": P2_JOB_1,
            "release_no": 1,
            "parent_release_id": None,
            "status": "PUBLISHED",
        }
        uow.commit()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repository = P2ReleaseRepository(uow.canonical_rows)
        second = repository.publish(
            job_id=P2_JOB_2,
            release_id=release_2,
            scope_key=scope_key,
            lineage=repository.source_lineage(SOURCE_RELEASE),
            expected_version_token=1,
            manifest_hash=MANIFEST_2,
            published_at_utc=WHEN,
        )
        assert second.version_token == 2
        assert second.parent_release_id == release_1
        pointer = uow.canonical_rows.one(
            "registry.release_scope_pointer",
            where={"scope_type": "SESSION", "scope_key": scope_key},
            columns=("current_release_id", "version_token"),
        )
        assert pointer == {
            "current_release_id": release_2,
            "version_token": 2,
        }
        uow.commit()


def test_prcb_c2_p2_release_rejects_stale_cas(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.db"
    _seed(database)
    scope_key = p2_release_scope_key(OBSERVATION)
    release_1 = allocate_p2_release_id(
        job_id=P2_JOB_1,
        request_hash=REQUEST_HASH_1,
        scope_key=scope_key,
    )
    release_2 = allocate_p2_release_id(
        job_id=P2_JOB_2,
        request_hash=REQUEST_HASH_2,
        scope_key=scope_key,
    )
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repository = P2ReleaseRepository(uow.canonical_rows)
        lineage = repository.source_lineage(SOURCE_RELEASE)
        repository.publish(
            job_id=P2_JOB_1,
            release_id=release_1,
            scope_key=scope_key,
            lineage=lineage,
            expected_version_token=0,
            manifest_hash=MANIFEST_1,
            published_at_utc=WHEN,
        )
        uow.commit()

    with pytest.raises(P2ReleaseError, match="P2_RELEASE_CAS_CONFLICT"):
        with SQLiteDesktopUnitOfWork(database, write=True) as uow:
            repository = P2ReleaseRepository(uow.canonical_rows)
            repository.publish(
                job_id=P2_JOB_2,
                release_id=release_2,
                scope_key=scope_key,
                lineage=repository.source_lineage(SOURCE_RELEASE),
                expected_version_token=0,
                manifest_hash=MANIFEST_2,
                published_at_utc=WHEN,
            )
