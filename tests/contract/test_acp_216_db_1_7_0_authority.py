from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from tpaa_canonical.loader import ArtifactExpectation, CanonicalArtifactLoader
from tpaa_storage.bootstrap import bootstrap_sqlite, verify_sqlite

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CORE = BASELINE / "canonical" / "CORE_LOGICAL_MODEL.json"
LOCK = BASELINE / "BASELINE_LOCK.json"
HISTORICAL = ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_6_0.json"
PROPOSAL = ROOT / "docs" / "proposals" / "ACP-216_EXACT_PERSISTENCE_SCHEMA_PROPOSAL.json"
ADOPTION = ROOT / "docs" / "baseline" / "PIQB-1.0" / "ACP_216_DB_1_7_0_ADOPTION.json"
REVISION = ROOT / "migrations" / "versions" / "0001_acp216_db_1_7_0.py"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_acp_216_core_authority_is_exact_additive_1_7_0() -> None:
    current = _load(CORE)
    historical = _load(HISTORICAL)
    proposal = _load(PROPOSAL)
    adoption = _load(ADOPTION)
    current_tables = current["tables"]
    historical_tables = historical["tables"]
    assert isinstance(current_tables, dict)
    assert isinstance(historical_tables, dict)
    assert current["db_schema_version"] == "1.7.0"
    assert historical["db_schema_version"] == "1.6.0"
    assert len(historical_tables) == 77
    assert len(current_tables) == 92
    assert all(
        isinstance(table, dict) and table.get("schema_version") == "1.7.0"
        for table in current_tables.values()
    )
    new_relations = [row["relation"] for row in proposal["changes"]]
    assert new_relations == adoption["additive_relations"]
    assert set(current_tables) - set(historical_tables) == set(new_relations)
    for name, old in historical_tables.items():
        assert isinstance(old, dict)
        new = current_tables[name]
        assert isinstance(new, dict)
        old_without_version = {k: v for k, v in old.items() if k != "schema_version"}
        new_without_version = {k: v for k, v in new.items() if k != "schema_version"}
        assert new_without_version == old_without_version


def test_acp_216_lock_trust_and_proposal_provenance_are_exact() -> None:
    lock = _load(LOCK)
    proposal = _load(PROPOSAL)
    adoption = _load(ADOPTION)
    assert proposal["status"] == "PROPOSED_NOT_ADOPTED"
    assert proposal["blocker_coverage"]["uncovered"] == []
    assert lock["baseline"]["db_schema"] == "1.7.0"
    assert adoption["source_core_sha256"] == _sha(HISTORICAL)
    assert adoption["target_core_sha256"] == _sha(CORE)
    assert adoption["target_baseline_lock_sha256"] == _sha(LOCK)
    assert adoption["source_baseline_lock_sha256"] in lock["baseline"]["lock_lineage_sha256"]
    core_entry = next(
        row for row in lock["artifacts"] if row["file"] == "CORE_LOGICAL_MODEL.json"
    )
    assert core_entry["sha256"] == _sha(CORE)
    assert core_entry["bytes"] == len(CORE.read_bytes())
    assert adoption["shadow_schema_created"] is False
    assert adoption["formal_adoption_claimed"] is False


def test_acp_216_loader_bootstrap_and_composite_constraints(tmp_path: Path) -> None:
    loader = CanonicalArtifactLoader()
    artifact = loader.load(
        "CORE_LOGICAL_MODEL",
        expectation=ArtifactExpectation(schema_version="1.7.0"),
    )
    assert artifact.schema_version == "1.7.0"
    database = tmp_path / "authority.sqlite3"
    bootstrap = bootstrap_sqlite(database)
    assert bootstrap.schema_version == "1.7.0"
    assert verify_sqlite(database) == bootstrap
    with sqlite3.connect(database) as connection:
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            ("registry.mutation_idempotency",),
        ).fetchone()
    assert sql is not None
    assert "PRIMARY KEY (operation_code, request_id)" in str(sql[0])


def test_acp_216_first_governed_revision_covers_all_new_relations() -> None:
    adoption = _load(ADOPTION)
    text = REVISION.read_text(encoding="utf-8")
    assert 'revision = "0001_acp216_db_1_7_0"' in text
    assert "def upgrade() -> None:" in text
    assert "def downgrade() -> None:" in text
    assert "ACP216_DOWNGRADE_NONEMPTY" in text
    for relation in adoption["additive_relations"]:
        assert relation in text
