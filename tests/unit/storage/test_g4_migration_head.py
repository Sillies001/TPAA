from __future__ import annotations

from pathlib import Path

from tools.storage.g1_v33_migration import bootstrap_source_sqlite
from tpaa_storage.migration_service import SQLiteMigrationService


def test_g4_candidate_uses_db_1_10_as_governed_migration_head(tmp_path: Path) -> None:
    database = tmp_path / "g4.sqlite3"
    bootstrap_source_sqlite(database)
    repository = Path(__file__).resolve().parents[3]
    service = SQLiteMigrationService(
        database,
        current_authority_root=repository / "baseline" / "CB-1.9.0" / "canonical",
        migration_authority_root=repository / "migrations" / "authority",
        target_schema_version="1.10.0",
    )

    plan = service.plan()
    assert [hop.proposal for hop in plan.hops] == ["G1-V33-DB-1.10.0"]
    assert service.apply()["target_version"] == "1.10.0"

    status = service.status()
    assert status.schema_version == "1.10.0"
    assert status.target_version == "1.10.0"
    assert status.verified is True
    assert status.at_head is True
