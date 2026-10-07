from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PRCB-1.0"
SOURCE = "0ed48a85944699e0bbac1fe76b84c88a319121c1"


def _load(name: str) -> dict[str, object]:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def test_prcb_task_baseline_freezes_post_piqb_scope() -> None:
    baseline = _load("PRCB_TASK_BASELINE.json")
    assert baseline["schema"] == "TPAA_PRCB_TASK_BASELINE_V1"
    assert baseline["source_piqb_protected_main_sha"] == SOURCE
    assert baseline["source_piqb_qualification"] == "PIQB_1_0_QUALIFIED"
    assert baseline["historical_product_version"] == "1.0.0"
    assert baseline["target_product_version"] == "1.0.1"
    assert baseline["db_schema_version"] == "1.9.0"
    assert [item["batch"] for item in baseline["batches"]] == [f"C{i}" for i in range(6)]
    invariants = baseline["invariants"]
    assert invariants["no_m10_p7"] is True
    assert invariants["no_piqb_history_rewrite"] is True
    assert invariants["exact_fourteen_required_job_topology"] is True
    assert invariants["production_test_fixture_dependency_forbidden"] is True
    assert invariants["production_inmemory_authority_forbidden"] is True


def test_prcb_acceptance_contract_captures_four_blockers() -> None:
    contract = _load("PRCB_ACCEPTANCE_CONTRACT.json")
    assert contract["schema"] == "TPAA_PRCB_ACCEPTANCE_CONTRACT_V1"
    assert contract["target_product_version"] == "1.0.1"
    blockers = contract["blockers"]
    assert [item["id"] for item in blockers] == [
        "PRCB-BLK-001",
        "PRCB-BLK-002",
        "PRCB-BLK-003",
        "PRCB-BLK-004",
    ]
    order = contract["installed_package_e2e_order"]
    assert order[0] == "INSTALL"
    assert "WORKER_COMPUTE" in order
    assert "P6" in order
    assert order[-1] == "AUDIT_VERIFY"


def test_prcb_state_does_not_claim_premature_qualification() -> None:
    state = _load("PRCB_IMPLEMENTATION_STATE.json")
    assert state["qualification"] == {
        "status": "NOT_YET_QUALIFIED",
        "formal_release_claimed": False,
    }
    assert state["active_batch"] == "C5"
    assert state["task_state"]["C0"]["state"] == "COMPLETE"
    assert state["task_state"]["C1"]["state"] == "COMPLETE"
    assert state["task_state"]["C2"]["state"] == "COMPLETE"
    assert state["task_state"]["C3"]["state"] == "COMPLETE"
    assert state["task_state"]["C4"]["state"] == "COMPLETE"
    assert state["task_state"]["C5"]["state"] == "ACTIVE"
