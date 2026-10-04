from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
B3_SHA = "08e223c8137eb261b43ed7c2ca3612e22770d8ba"


def _load(name: str) -> dict[str, object]:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def test_b3_formal_qualification_is_exact_b4_entry_authority() -> None:
    b3 = _load("B3_IMPLEMENTATION_STATE.json")

    assert b3["b3_qualified"] is True
    assert b3["b4_blocked"] is False
    qualification = b3["qualification"]
    assert isinstance(qualification, dict)
    assert qualification["protected_main_sha"] == B3_SHA
    assert qualification["run_number"] == 618
    assert qualification["actions_run_id"] == 37196871134
    assert qualification["required_jobs_success"] == 14
    assert qualification["required_jobs_total"] == 14
    assert qualification["status"] == "PASS"
    assert qualification["decision"] == "GO"
    assert qualification["qualification"] == "PIQB_B3_QUALIFIED"
    assert qualification["data_compute_plane_qualified"] is True

    task_state = b3["task_state"]
    assert isinstance(task_state, dict)
    assert {item["state"] for item in task_state.values()} == {"COMPLETE"}


def test_b4_task_baseline_freezes_exact_scope_and_eight_tasks() -> None:
    baseline = _load("B4_TASK_BASELINE.json")

    assert baseline["schema"] == "TPAA_PIQB_B4_TASK_BASELINE_V1"
    assert baseline["batch"] == "B4"
    assert baseline["source_b3_protected_main_sha"] == B3_SHA
    assert baseline["source_b3_qualification"] == "PIQB_B3_QUALIFIED"
    assert baseline["source_b3_run_number"] == 618
    assert baseline["db_schema_version"] == "1.9.0"
    assert baseline["task_count"] == 8
    tasks = baseline["tasks"]
    assert isinstance(tasks, list)
    assert [item["task_id"] for item in tasks] == [
        f"PIQB-B4-{index:03d}" for index in range(1, 9)
    ]

    scope = baseline["scope"]
    assert isinstance(scope, dict)
    assert scope["no_db_schema_change"] is True
    assert scope["no_shadow_schema"] is True
    assert scope["existing_audit_relation_required"] == "audit.audit_log"
    assert scope["service_identity_resolver_pluggable"] is True
    assert scope["default_deny_required"] is True
    assert scope["client_actor_header_not_authoritative_in_service"] is True
    assert scope["frozen_m8_p6_role_policies_remain_authoritative"] is True
    assert scope["exact_fourteen_job_topology_preserved"] is True


def test_b4_foundation_state_does_not_claim_candidate_completion_before_ci() -> None:
    state = _load("B4_IMPLEMENTATION_STATE.json")

    assert state["b4_qualified"] is False
    assert state["b5_blocked"] is True
    entry = state["entry_qualification"]
    assert isinstance(entry, dict)
    assert entry["protected_main_sha"] == B3_SHA
    assert entry["run_number"] == 618
    assert entry["qualification"] == "PIQB_B3_QUALIFIED"

    task_state = state["task_state"]
    assert isinstance(task_state, dict)
    for index in range(1, 4):
        assert task_state[f"PIQB-B4-{index:03d}"]["state"] == (
            "IMPLEMENTED_PENDING_CI"
        )
    for index in range(4, 9):
        assert task_state[f"PIQB-B4-{index:03d}"]["state"] == "NOT_STARTED"


def test_b4_unified_factory_has_no_transport_authorization_bypass() -> None:
    unified = (ROOT / "src" / "tpaa_api" / "unified.py").read_text(
        encoding="utf-8"
    )
    base = (ROOT / "src" / "tpaa_api" / "app.py").read_text(encoding="utf-8")
    desktop = (ROOT / "src" / "tpaa_api" / "desktop.py").read_text(
        encoding="utf-8"
    )
    composition = (
        ROOT / "src" / "tpaa_runtime" / "composition.py"
    ).read_text(encoding="utf-8")

    assert "register_unified_routes" in unified
    assert "create_unified_service_app" in unified
    assert "UnifiedPrincipalResolver" in unified
    assert "m8_viewer" in unified
    assert "m9_viewer" in unified
    assert "actor_resolver" in base
    assert "register_unified_routes" in desktop
    assert "principal_resolver: UnifiedPrincipalResolver | None" in composition
    assert "no development fallback is allowed" in composition
    assert "X-TPAA-Actor" in base
    assert "actor_resolver(request)" in base


def test_b4_first_block_does_not_change_db_or_required_job_topology() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "\n  piqb-b4-review:" not in workflow

    model = json.loads(
        (
            ROOT
            / "baseline"
            / "CB-1.4.0"
            / "canonical"
            / "CORE_LOGICAL_MODEL.json"
        ).read_text(encoding="utf-8")
    )
    assert model["db_schema_version"] == "1.9.0"
    assert "audit.audit_log" in model["tables"]
