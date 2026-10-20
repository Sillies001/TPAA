from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tools.storage.acp216_migration import bootstrap_historical_sqlite
from tpaa_admin.__main__ import main
from tpaa_storage import MigrationServiceError, SQLiteMigrationService

REPO_ROOT = Path(__file__).resolve().parents[3]
CURRENT_AUTHORITY = REPO_ROOT / "baseline" / "CB-1.5.0" / "canonical"
MIGRATION_AUTHORITY = REPO_ROOT / "migrations" / "authority"


def _service(database: Path) -> SQLiteMigrationService:
    return SQLiteMigrationService(
        database,
        current_authority_root=CURRENT_AUTHORITY,
        migration_authority_root=MIGRATION_AUTHORITY,
    )


def test_formal_migration_service_plan_apply_rollback_and_reapply(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_historical_sqlite(database)
    service = _service(database)

    plan = service.plan()
    assert plan.observed_version == "1.6.0"
    assert plan.target_version == "1.9.0"
    assert [hop.proposal for hop in plan.hops] == ["ACP-216", "ACP-219", "ACP-221"]

    applied = service.apply()
    assert applied["status"] == "COMPLETE"
    assert applied["target_version"] == "1.9.0"
    assert service.status().payload()["status"] == "READY"

    rolled_back = service.rollback("1.6.0")
    assert rolled_back["status"] == "COMPLETE"
    assert rolled_back["target_version"] == "1.6.0"
    assert service.verify().schema_version == "1.6.0"

    reapplied = service.apply()
    assert reapplied["target_version"] == "1.9.0"
    assert service.verify().schema_version == "1.9.0"


def test_failed_migration_requires_and_supports_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_historical_sqlite(database)
    service = _service(database)
    original = service._apply_hop
    calls = 0

    def fail_second_hop(hop) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected failure")
        original(hop)

    monkeypatch.setattr(service, "_apply_hop", fail_second_hop)
    with pytest.raises(RuntimeError, match="injected failure"):
        service.apply()
    assert service.status().journal_state == "FAILED"
    assert service.status().schema_version == "1.7.0"

    with pytest.raises(MigrationServiceError) as blocked:
        service.apply()
    assert blocked.value.reason == "RESUME_REQUIRED"

    monkeypatch.setattr(service, "_apply_hop", original)
    resumed = service.resume()
    assert resumed["command"] == "resume"
    assert resumed["target_version"] == "1.9.0"
    assert service.status().journal_state == "COMPLETED"


def test_rollback_is_blocked_when_new_relation_contains_data(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_historical_sqlite(database)
    service = _service(database)
    service.apply()
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            'INSERT INTO "assessment.annotation_subject_context" '
            "(annotation_id, subject_context_id) VALUES (?, ?)",
            (
                "b0000000-0000-4000-8000-000000000001",
                "W1-NONEMPTY-PROBE",
            ),
        )
        connection.commit()

    with pytest.raises(MigrationServiceError) as blocked:
        service.rollback("1.8.0")
    assert blocked.value.reason == "ROLLBACK_BLOCKED_NONEMPTY_RELATION"
    assert service.status().schema_version == "1.9.0"
    assert service.status().journal_state == "FAILED"


def test_service_refuses_missing_database_without_silent_bootstrap(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing.sqlite3"
    service = _service(database)
    with pytest.raises(MigrationServiceError) as failure:
        service.apply()
    assert failure.value.reason == "DATABASE_NOT_FOUND"
    assert not database.exists()


def test_admin_exposes_governed_migrate_commands(
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    bootstrap_historical_sqlite(data_root / "tpaa.sqlite3")

    assert main(["migrate", "plan", "--data-root", str(data_root)]) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["status"] == "PLANNED"
    assert planned["target_version"] == "1.9.0"

    assert main(["migrate", "apply", "--data-root", str(data_root)]) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["status"] == "COMPLETE"

    assert main(["migrate", "verify", "--data-root", str(data_root)]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["status"] == "PASS"
    assert verified["schema_version"] == "1.9.0"

    assert main(["migrate", "status", "--data-root", str(data_root)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "READY"
    assert status["at_migration_head"] is True
