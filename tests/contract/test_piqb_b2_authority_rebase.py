from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_b2_authority_rebase_preserves_history_and_anchors_db_1_9() -> None:
    base = ROOT / "docs" / "baseline" / "PIQB-1.0"
    rebase = json.loads((base / "B2_AUTHORITY_REBASE.json").read_text(encoding="utf-8"))
    state = json.loads((base / "B2_IMPLEMENTATION_STATE.json").read_text(encoding="utf-8"))
    historical = json.loads(
        (base / "B2_SCHEMA_PERSISTENCE_FIT.json").read_text(encoding="utf-8")
    )
    lock = json.loads(
        (ROOT / "baseline/CB-1.4.0/BASELINE_LOCK.json").read_text(encoding="utf-8")
    )
    assert historical["db_schema_version"] == "1.6.0"
    assert historical["authority_change_proposal_status"] == "PROPOSED_NOT_ADOPTED"
    assert rebase["historical_fit_audit"]["preserved_as_pre_adoption_evidence"] is True

    lineage = rebase["authority_lineage"]
    assert lineage[0]["proposal_id"] == "ACP-216"
    assert lineage[0]["db_schema_version"] == "1.7.0"
    assert lineage[0]["protected_main_sha"] == (
        "d5be58189d7fbd81f7fb3e49506eb0a61544db46"
    )
    assert lineage[0]["qualification"] == "ACP216_DB_1_7_0_ADOPTED"
    assert lineage[0]["historical"] is True

    lineage_1_8 = lineage[1]
    assert lineage_1_8["proposal_id"] == "ACP-219"
    assert lineage_1_8["db_schema_version"] == "1.8.0"
    assert lineage_1_8["protected_main_sha"] == (
        "a17eb1e5a0b961c7c555c6d900839df47165e245"
    )
    assert lineage_1_8["qualification"] == "ACP219_DB_1_8_0_ADOPTED"
    assert lineage_1_8["historical"] is True

    current = rebase["adopted_authority"]
    assert current["proposal_id"] == "ACP-221"
    assert current["db_schema_version"] == "1.9.0"
    assert current["protected_main_sha"] == (
        "24f504b9be762fa78618632f25c3f6cbc290c6c8"
    )
    assert current["run_number"] == 607
    assert current["qualification"] == "ACP221_DB_1_9_0_ADOPTED"

    assert state["db_schema_version"] == "1.9.0"
    assert state["authority_change_proposal_issue"] == 221
    assert state["authority_change_proposal_status"] == "ADOPTED_PROTECTED_MAIN"
    assert state["production_activation"]["authority_blocked"] == []
    assert lock["baseline"]["db_schema"] == "1.9.0"
