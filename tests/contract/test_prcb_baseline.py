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


def test_prcb_state_records_final_protected_main_qualification() -> None:
    state = _load("PRCB_IMPLEMENTATION_STATE.json")
    assert state["active_batch"] is None
    assert all(
        state["task_state"][f"C{i}"]["state"] == "COMPLETE"
        for i in range(6)
    )
    assert state["qualification"] == {
        "status": "TPAA_1_0_1_QUALIFIED",
        "formal_release_claimed": True,
        "implementation_complete": True,
        "protected_main_exact": True,
        "failed_acceptance": [],
    }

    candidate = state["candidate_qualification"]
    assert candidate["exact_head_sha"] == "4402f44780e330fe659b2a2014017ea4d231f519"
    assert candidate["run_number"] == 695
    assert candidate["actions_run_id"] == 37612699340
    assert candidate["decision"] == "PENDING_PROTECTED_MAIN"
    assert candidate["qualification"] == "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED"
    assert candidate["formal_release_claimed"] is False

    protected = state["protected_main_qualification"]
    assert protected["protected_main_sha"] == "abf00eb44316c4f4927b5e7399bfe0ebab3a3f77"
    assert protected["run_number"] == 696
    assert protected["actions_run_id"] == 37619872063
    assert protected["required_jobs_success"] == 14
    assert protected["required_jobs_total"] == 14
    assert protected["reviewer_schema"] == "TPAA_PRCB_C5_EXIT_REVIEW_V1"
    assert protected["status"] == "PASS"
    assert protected["decision"] == "GO"
    assert protected["qualification"] == "TPAA_1_0_1_QUALIFIED"
    assert protected["formal_release_claimed"] is True
    assert protected["implementation_complete"] is True
    assert protected["protected_main_exact"] is True
    assert protected["failed_acceptance"] == []
    assert protected["detached_attestation_schema"] == (
        "TPAA_PRCB_C5_DETACHED_ATTESTATION_V1"
    )
    assert protected["detached_attestation_payload_sha256"] == (
        "4f1a4b5b40ad87913b88f572ab93c1070412637a26c3b916f2875bc6a3da2d2d"
    )
    assert set(protected["package_sha256_by_profile"]) == {
        "LINUX_DESKTOP_X64",
        "LINUX_SERVICE_X64",
        "WINDOWS_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
    }
    assert set(protected["installed_evidence_sha256_by_profile"]) == {
        "LINUX_DESKTOP_X64",
        "LINUX_SERVICE_X64",
        "WINDOWS_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
    }

    closure = state["post_qualification_governance_closure"]
    assert closure["source_protected_main_sha"] == protected["protected_main_sha"]
    assert closure["source_run_number"] == 696
    assert closure["change_class"] == "GOVERNANCE_ONLY"
    assert closure["runtime_modified"] is False
    assert closure["canonical_modified"] is False
    assert closure["db_authority_modified"] is False
    assert closure["ci_topology_modified"] is False
    assert closure["piqb_history_modified"] is False
