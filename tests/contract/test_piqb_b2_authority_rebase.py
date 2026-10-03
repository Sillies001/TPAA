from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_b2_authority_rebase_preserves_history_and_anchors_db_1_7() -> None:
    base = ROOT / "docs/baseline/PIQB-1.0"
    rebase = json.loads((base / "B2_AUTHORITY_REBASE.json").read_text(encoding="utf-8"))
    state = json.loads((base / "B2_IMPLEMENTATION_STATE.json").read_text(encoding="utf-8"))
    historical = json.loads((base / "B2_SCHEMA_PERSISTENCE_FIT.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "baseline/CB-1.4.0/BASELINE_LOCK.json").read_text(encoding="utf-8"))
    assert historical["db_schema_version"] == "1.6.0"
    assert historical["authority_change_proposal_status"] == "PROPOSED_NOT_ADOPTED"
    assert rebase["historical_fit_audit"]["preserved_as_pre_adoption_evidence"] is True
    assert rebase["adopted_authority"]["protected_main_sha"] == "d5be58189d7fbd81f7fb3e49506eb0a61544db46"
    assert rebase["adopted_authority"]["run_number"] == 576
    assert rebase["adopted_authority"]["qualification"] == "ACP216_DB_1_7_0_ADOPTED"
    assert state["db_schema_version"] == "1.7.0"
    assert state["authority_change_proposal_status"] == "ADOPTED_PROTECTED_MAIN"
    assert state["production_activation"]["authority_blocked"] == []
    assert lock["baseline"]["db_schema"] == "1.7.0"
