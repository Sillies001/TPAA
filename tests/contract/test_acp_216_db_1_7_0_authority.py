from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.storage.acp216_migration import target_authority

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "migrations/authority/CORE_LOGICAL_MODEL_DB_1_6_0.json"
TARGET = ROOT / "migrations/authority/CORE_LOGICAL_MODEL_DB_1_7_0.json"
PROPOSAL = ROOT / "docs/proposals/ACP-216_EXACT_PERSISTENCE_SCHEMA_PROPOSAL.json"
ADOPTION = ROOT / "docs/baseline/PIQB-1.0/ACP_216_DB_1_7_0_ADOPTION.json"
REVISION = ROOT / "migrations/versions/0001_acp216_db_1_7_0.py"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_acp_216_historical_authority_is_exact_additive_1_7_0() -> None:
    source = _load(SOURCE)
    target = _load(TARGET)
    proposal = _load(PROPOSAL)
    adoption = _load(ADOPTION)
    source_tables = source["tables"]
    target_tables = target["tables"]
    assert isinstance(source_tables, dict)
    assert isinstance(target_tables, dict)
    assert source["db_schema_version"] == "1.6.0"
    assert target["db_schema_version"] == "1.7.0"
    assert len(source_tables) == 77
    assert len(target_tables) == 92
    assert _sha(TARGET) == adoption["target_core_sha256"]
    new_relations = [row["relation"] for row in proposal["changes"]]
    assert new_relations == adoption["additive_relations"]
    assert set(target_tables) - set(source_tables) == set(new_relations)
    for name, old in source_tables.items():
        new = target_tables[name]
        assert isinstance(old, dict)
        assert isinstance(new, dict)
        assert {k: v for k, v in old.items() if k != "schema_version"} == {
            k: v for k, v in new.items() if k != "schema_version"
        }


def test_acp_216_migration_target_is_pinned_to_historical_1_7_snapshot() -> None:
    authority = target_authority()
    assert authority.schema_version == "1.7.0"
    assert len(authority.tables) == 92
    assert authority.authority_sha256 == (
        "dd8461ff572338006455f7b6eac5325900c60640f5d163c3b61c3f5bd5767f74"
    )
    assert authority.baseline_lock_sha256 == (
        "a55ccc5f75d128c4dc3c3208064596eeb2dda7ffaf340d87726a22d4b62f93c6"
    )


def test_acp_216_first_governed_revision_remains_archived_and_exact() -> None:
    adoption = _load(ADOPTION)
    text = REVISION.read_text(encoding="utf-8")
    assert 'revision = "0001_acp216_db_1_7_0"' in text
    assert "ACP216_DOWNGRADE_NONEMPTY" in text
    for relation in adoption["additive_relations"]:
        assert relation in text
