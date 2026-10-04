from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "baseline/CB-1.4.0/canonical/CORE_LOGICAL_MODEL.json"
HISTORICAL = ROOT / "migrations/authority/CORE_LOGICAL_MODEL_DB_1_8_0.json"


def test_acp_221_db_1_9_exact_additive_inventory() -> None:
    current = json.loads(CORE.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    assert current["db_schema_version"] == "1.9.0"
    assert historical["db_schema_version"] == "1.8.0"
    assert len(current["tables"]) == 95
    assert len(historical["tables"]) == 94
    assert (
        hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()
        == "cbb15c1e0029be45213e4d7ab57a78fac47d7cc09c4627a9c388fafdadd2d44e"
    )
    assert set(current["tables"]) - set(historical["tables"]) == {
        "assessment.annotation_subject_context"
    }


def test_acp_221_relation_preserves_exact_subject_context_text() -> None:
    current = json.loads(CORE.read_text(encoding="utf-8"))
    relation = current["tables"]["assessment.annotation_subject_context"]
    assert [(f["name"], f["type"], f["nullable"]) for f in relation["fields"]] == [
        ("annotation_id", "uuid", False),
        ("subject_context_id", "text", False),
    ]
    assert relation["fields"][0]["sql"] == (
        "annotation_id uuid PRIMARY KEY REFERENCES debrief.annotation(annotation_id)"
    )
    assert relation["fields"][1]["sql"] == (
        "subject_context_id text NOT NULL REFERENCES "
        "assessment.p4_subject_context(subject_context_id)"
    )
    assert relation.get("constraints", []) == []


def test_acp_221_preserves_all_db_1_8_table_semantics() -> None:
    current = json.loads(CORE.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    for name, old in historical["tables"].items():
        new = current["tables"][name]
        assert {k: v for k, v in old.items() if k != "schema_version"} == {
            k: v for k, v in new.items() if k != "schema_version"
        }
        assert new["schema_version"] == "1.9.0"
