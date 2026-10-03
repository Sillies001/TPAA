from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "baseline/CB-1.4.0/canonical/CORE_LOGICAL_MODEL.json"
HISTORICAL = ROOT / "migrations/authority/CORE_LOGICAL_MODEL_DB_1_7_0.json"


def test_acp_219_db_1_8_exact_additive_inventory() -> None:
    current = json.loads(CORE.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    assert current["db_schema_version"] == "1.8.0"
    assert historical["db_schema_version"] == "1.7.0"
    assert len(current["tables"]) == 94
    assert len(historical["tables"]) == 92
    assert (
        hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()
        == "dd8461ff572338006455f7b6eac5325900c60640f5d163c3b61c3f5bd5767f74"
    )
    assert set(current["tables"]) - set(historical["tables"]) == {
        "assessment.actor_assessment_machine_evidence_ref",
        "assessment.mission_assessment_objective_ref",
    }


def test_acp_219_ordered_text_relations_are_not_uuid_shadow_projections() -> None:
    current = json.loads(CORE.read_text(encoding="utf-8"))
    p4 = current["tables"]["assessment.actor_assessment_machine_evidence_ref"]
    p5 = current["tables"]["assessment.mission_assessment_objective_ref"]
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
    assert p4["constraints"] == [
        "PRIMARY KEY (actor_assessment_id, ref_order)",
        "UNIQUE (actor_assessment_id, evidence_ref)",
    ]
    assert p5["constraints"] == [
        "PRIMARY KEY (mission_assessment_id, ref_order)",
        "UNIQUE (mission_assessment_id, objective_ref)",
    ]


def test_acp_219_preserves_all_db_1_7_table_semantics() -> None:
    current = json.loads(CORE.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    for name, old in historical["tables"].items():
        new = current["tables"][name]
        assert {k: v for k, v in old.items() if k != "schema_version"} == {
            k: v for k, v in new.items() if k != "schema_version"
        }
        assert new["schema_version"] == "1.8.0"
