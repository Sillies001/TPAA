from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_ROOT = REPO_ROOT / "docs" / "baseline" / "PIQB-1.0"
B2_SHA = "4b6e7c1e40d857b859b7fd322af9943706e79354"


def _load(name: str) -> dict[str, object]:
    return json.loads((BASELINE_ROOT / name).read_text(encoding="utf-8"))


def test_b2_formal_state_is_bound_to_run_611_protected_main() -> None:
    state = _load("B2_IMPLEMENTATION_STATE.json")

    assert state["b2_qualified"] is True
    qualification = state["qualification"]
    assert isinstance(qualification, dict)
    assert qualification["protected_main_sha"] == B2_SHA
    assert qualification["run_number"] == 611
    assert qualification["required_jobs_success"] == 14
    assert qualification["required_jobs_total"] == 14
    assert qualification["decision"] == "GO"
    assert qualification["qualification"] == "PIQB_B2_QUALIFIED"

    task_state = state["task_state"]
    assert isinstance(task_state, dict)
    assert {item["state"] for item in task_state.values()} == {"COMPLETE"}


def test_b3_task_baseline_freezes_exact_scope_and_entry_authority() -> None:
    baseline = _load("B3_TASK_BASELINE.json")

    assert baseline["schema"] == "TPAA_PIQB_B3_TASK_BASELINE_V1"
    assert baseline["batch"] == "B3"
    assert baseline["source_b2_protected_main_sha"] == B2_SHA
    assert baseline["source_b2_qualification"] == "PIQB_B2_QUALIFIED"
    assert baseline["db_schema_version"] == "1.9.0"
    assert baseline["task_count"] == 8
    tasks = baseline["tasks"]
    assert isinstance(tasks, list)
    assert [item["task_id"] for item in tasks] == [
        f"PIQB-B3-{index:03d}" for index in range(1, 9)
    ]
    scope = baseline["scope"]
    assert isinstance(scope, dict)
    assert scope["source_families"] == [
        "FLIGHT",
        "MISSION_AVIONICS",
        "TDL",
        "RANGE_ACMI",
        "SCENARIO",
        "AUDIO_VIDEO",
    ]
    assert scope["no_db_schema_change"] is True
    assert scope["no_shadow_schema"] is True
    assert scope["no_b4_api_security_work"] is True
    assert scope["proprietary_decoder_is_external_adapter"] is True


def test_b3_foundation_state_does_not_claim_compute_plane_completion() -> None:
    state = _load("B3_IMPLEMENTATION_STATE.json")

    assert state["b3_qualified"] is False
    task_state = state["task_state"]
    assert isinstance(task_state, dict)
    assert task_state["PIQB-B3-001"]["state"] == "IMPLEMENTED_PENDING_CI"
    assert task_state["PIQB-B3-002"]["state"] == "IMPLEMENTED_PENDING_CI"
    assert task_state["PIQB-B3-003"]["state"] == "IMPLEMENTED_PENDING_CI"
    assert task_state["PIQB-B3-004"]["state"] == "NOT_STARTED"
    assert task_state["PIQB-B3-008"]["state"] == "NOT_STARTED"
