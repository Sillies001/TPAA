from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.storage.acp219_migration import target_authority

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "migrations/authority/CORE_LOGICAL_MODEL_DB_1_7_0.json"
TARGET = ROOT / "migrations/authority/CORE_LOGICAL_MODEL_DB_1_8_0.json"


def test_acp_219_historical_db_1_8_exact_additive_inventory() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    assert source["db_schema_version"] == "1.7.0"
    assert target["db_schema_version"] == "1.8.0"
    assert len(source["tables"]) == 92
    assert len(target["tables"]) == 94
    assert (
        hashlib.sha256(TARGET.read_bytes()).hexdigest()
        == "cbb15c1e0029be45213e4d7ab57a78fac47d7cc09c4627a9c388fafdadd2d44e"
    )
    assert set(target["tables"]) - set(source["tables"]) == {
        "assessment.actor_assessment_machine_evidence_ref",
        "assessment.mission_assessment_objective_ref",
    }
    for name, old in source["tables"].items():
        new = target["tables"][name]
        assert {k: v for k, v in old.items() if k != "schema_version"} == {
            k: v for k, v in new.items() if k != "schema_version"
        }


def test_acp_219_migration_target_is_pinned_to_historical_1_8_snapshot() -> None:
    authority = target_authority()
    assert authority.schema_version == "1.8.0"
    assert len(authority.tables) == 94
    assert authority.authority_sha256 == (
        "cbb15c1e0029be45213e4d7ab57a78fac47d7cc09c4627a9c388fafdadd2d44e"
    )
    assert authority.baseline_lock_sha256 == (
        "2f3690d5e74e585a34ae35fdef9fb1e0cccb5504c6983d0c97417bb6a106b389"
    )


def test_acp_219_ordered_text_relations_remain_exact_in_history() -> None:
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    p4 = target["tables"]["assessment.actor_assessment_machine_evidence_ref"]
    p5 = target["tables"]["assessment.mission_assessment_objective_ref"]
    assert [(f["name"], f["type"]) for f in p4["fields"]] == [
        ("actor_assessment_id", "uuid"),
        ("ref_order", "integer"),
        ("evidence_ref", "text"),
    ]
    assert [(f["name"], f["type"]) for f in p5["fields"]] == [
        ("mission_assessment_id", "uuid"),
        ("ref_order", "integer"),
        ("objective_ref", "text"),
    ]
