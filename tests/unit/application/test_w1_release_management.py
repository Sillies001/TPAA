from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tpaa_admin.__main__ import main
from tpaa_application import ReleaseManagementError, ReleaseManagementService
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.5.0" / "canonical"
R1 = "a1000000-0000-4000-8000-000000000001"
R2 = "a1000000-0000-4000-8000-000000000002"
JOB1 = "a1000000-0000-4000-8000-000000000011"
JOB2 = "a1000000-0000-4000-8000-000000000012"
SCOPE = "W1:RELEASE:SUBJECT"


def _seed(database: Path) -> None:
    bootstrap_sqlite(database, authority_root=AUTHORITY)
    with sqlite3.connect(database) as connection:
        for job, key in ((JOB1, "W1-JOB-1"), (JOB2, "W1-JOB-2")):
            connection.execute(
                '''INSERT INTO "registry.compute_job" (
                       job_id, job_type, session_id, episode_id, job_key,
                       status, component_version, input_hash, progress,
                       reason_codes, error_detail, created_at, started_at, finished_at
                   ) VALUES (?, 'W1_RELEASE', NULL, NULL, ?, 'SUCCEEDED',
                             'W1', ?, 1.0, '[]', NULL, CURRENT_TIMESTAMP,
                             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                (job, key, "1" * 64),
            )
        connection.execute(
            '''INSERT INTO "registry.analysis_release" (
                   release_id, scope_type, scope_key, session_id,
                   longitudinal_scope_id, release_no, compute_job_id,
                   catalog_version, catalog_hash, context_binding_hash,
                   status, parent_release_id, manifest_hash, created_at,
                   published_at
               ) VALUES (?, 'LONGITUDINAL', ?, NULL, NULL, 1, ?, '1', ?, ?,
                         'PUBLISHED', NULL, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
            (R1, SCOPE, JOB1, "2" * 64, "3" * 64, "4" * 64),
        )
        connection.execute(
            '''INSERT INTO "registry.analysis_release" (
                   release_id, scope_type, scope_key, session_id,
                   longitudinal_scope_id, release_no, compute_job_id,
                   catalog_version, catalog_hash, context_binding_hash,
                   status, parent_release_id, manifest_hash, created_at,
                   published_at
               ) VALUES (?, 'LONGITUDINAL', ?, NULL, NULL, 2, ?, '1', ?, ?,
                         'PUBLISHED', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
            (R2, SCOPE, JOB2, "2" * 64, "3" * 64, R1, "5" * 64),
        )
        connection.execute(
            '''INSERT INTO "registry.release_scope_pointer" (
                   scope_type, scope_key, current_release_id, version_token, updated_at
               ) VALUES ('LONGITUDINAL', ?, ?, 2, CURRENT_TIMESTAMP)''',
            (SCOPE, R2),
        )
        connection.commit()


def _service(database: Path) -> ReleaseManagementService:
    def read_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, authority_root=AUTHORITY)

    def write_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, write=True, authority_root=AUTHORITY)

    return ReleaseManagementService(read_uow, write_uow)


def test_release_list_supersede_withdraw_and_audit(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    _seed(database)
    service = _service(database)

    listed = service.list(scope_type="LONGITUDINAL", scope_key=SCOPE)
    assert [item.release_id for item in listed] == [R1, R2]
    assert [item.current for item in listed] == [False, True]

    superseded = service.supersede(
        R1,
        successor_release_id=R2,
        expected_version_token=2,
        principal_key="LOCAL_ADMIN",
        request_id="w1-supersede",
        reason="approved successor",
    )
    assert superseded.status == "SUPERSEDED"
    assert superseded.current_release_id == R2

    withdrawn = service.withdraw(
        R2,
        expected_version_token=2,
        principal_key="LOCAL_ADMIN",
        request_id="w1-withdraw",
        reason="withdraw qualification candidate",
    )
    assert withdrawn.status == "WITHDRAWN"
    assert withdrawn.version_token == 3
    assert [item.status for item in service.list(scope_type="LONGITUDINAL", scope_key=SCOPE)] == [
        "SUPERSEDED",
        "WITHDRAWN",
    ]

    with SQLiteDesktopUnitOfWork(database, authority_root=AUTHORITY) as uow:
        actions = [row.action for row in uow.audit_log.rows()]
    assert actions == ["RELEASE_SUPERSEDE", "RELEASE_WITHDRAW"]


def test_release_management_rejects_stale_cas(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    _seed(database)
    with pytest.raises(ReleaseManagementError) as failure:
        _service(database).withdraw(
            R2,
            expected_version_token=1,
            principal_key="LOCAL_ADMIN",
            reason="stale",
        )
    assert failure.value.code == "RELEASE_CAS_CONFLICT"


def test_admin_release_list_is_public_and_path_safe(tmp_path: Path, capsys) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    _seed(data_root / "tpaa.sqlite3")
    (data_root / "objects").mkdir()
    assert (
        main(
            [
                "release",
                "list",
                "--data-root",
                str(data_root),
                "--scope-type",
                "LONGITUDINAL",
                "--scope-key",
                SCOPE,
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "COMPLETE"
    assert [item["release_id"] for item in payload["items"]] == [R1, R2]
