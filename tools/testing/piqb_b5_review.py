"""PIQB B5 Desktop/replay/visualization qualification review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
TASK_BASELINE = BASE / "B5_TASK_BASELINE.json"
IMPLEMENTATION_STATE = BASE / "B5_IMPLEMENTATION_STATE.json"
NAVIGATION_CONTRACT = BASE / "B5_DESKTOP_NAVIGATION_CONTRACT.json"
SOURCE_B4_SHA = "7130978fc14c2714a9135de285a2c74aeaa33804"
EXPECTED_TASKS = tuple(f"PIQB-B5-{index:03d}" for index in range(1, 9))


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _qualification_passes(
    value: dict[str, Any],
    *,
    platform: str,
    expected_revision: str,
) -> bool:
    acceptance = value.get("acceptance")
    return (
        value.get("schema")
        == "TPAA_PIQB_B5_DESKTOP_REPLAY_VISUALIZATION_QUALIFICATION_V1"
        and value.get("platform") == platform
        and value.get("source_revision") == expected_revision
        and value.get("status") == "PASS"
        and value.get("qualification_passed") is True
        and value.get("failed_acceptance") == []
        and isinstance(acceptance, dict)
        and bool(acceptance)
        and all(item is True for item in acceptance.values())
    )


def review(
    *,
    expected_revision: str,
    checked_out_revision: str,
    event_name: str,
    git_ref: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
    windows_qualification: dict[str, Any],
    linux_qualification: dict[str, Any],
) -> dict[str, object]:
    baseline = _json(TASK_BASELINE)
    state = _json(IMPLEMENTATION_STATE)
    navigation = _json(NAVIGATION_CONTRACT)
    tasks = baseline.get("tasks")
    task_ids = tuple(
        item.get("task_id")
        for item in tasks
        if isinstance(tasks, list) and isinstance(item, dict)
    ) if isinstance(tasks, list) else ()
    task_state = state.get("task_state")
    states = (
        tuple(task_state.get(task, {}).get("state") for task in EXPECTED_TASKS)
        if isinstance(task_state, dict)
        else ()
    )
    scope = baseline.get("scope")
    nav_rules = navigation.get("rules")
    nav_slots = navigation.get("slots")
    workflow = _text(".github/workflows/cross-platform-ci.yml")
    shell = _text("src/tpaa_gui/shell.py")
    desktop = _text("src/tpaa_gui/desktop.py")
    local_backend = _text("src/tpaa_gui/local_backend.py")
    product_shell = _text("src/tpaa_gui/product_shell.py")
    visualization = _text("src/tpaa_gui/visualization.py")

    formal_qualification = state.get("protected_main_qualification")
    formal_state_consistent = (
        (
            state.get("b5_qualified") is False
            and state.get("b6_blocked") is True
        )
        or (
            state.get("b5_qualified") is True
            and state.get("b6_blocked") is False
            and isinstance(formal_qualification, dict)
            and formal_qualification.get("qualification") == "PIQB_B5_QUALIFIED"
            and formal_qualification.get("required_jobs_success") == 14
            and formal_qualification.get("required_jobs_total") == 14
        )
    )
    windows_ok = _qualification_passes(
        windows_qualification,
        platform="windows",
        expected_revision=expected_revision,
    )
    linux_ok = _qualification_passes(
        linux_qualification,
        platform="linux",
        expected_revision=expected_revision,
    )
    acceptance = {
        "b4_entry_exact": (
            baseline.get("source_b4_protected_main_sha") == SOURCE_B4_SHA
            and baseline.get("source_b4_qualification") == "PIQB_B4_QUALIFIED"
            and baseline.get("source_b4_run_number") == 624
        ),
        "task_inventory_exact_8": (
            baseline.get("task_count") == 8
            and task_ids == EXPECTED_TASKS
        ),
        "all_tasks_complete_candidate": (
            len(states) == 8
            and all(item in {"COMPLETE_CANDIDATE", "COMPLETE"} for item in states)
            and state.get("candidate_complete") is True
        ),
        "formal_state_consistent": formal_state_consistent,
        "db_1_9_no_authority_change": (
            baseline.get("db_schema_version") == "1.9.0"
            and isinstance(scope, dict)
            and scope.get("no_db_schema_change") is True
            and scope.get("no_shadow_schema") is True
            and scope.get("gui_direct_database_write_forbidden") is True
            and scope.get("gui_business_recompute_forbidden") is True
        ),
        "p01_p13_navigation_exact": (
            navigation.get("schema")
            == "TPAA_PIQB_B5_DESKTOP_NAVIGATION_CONTRACT_V1"
            and isinstance(nav_slots, list)
            and len(nav_slots) == 13
            and [item.get("slot") for item in nav_slots if isinstance(item, dict)]
            == [f"P{index:02d}" for index in range(1, 14)]
            and navigation.get("spine")
            == [
                "session_id",
                "episode_id",
                "stage_id",
                "scope",
                "subject",
                "session_time",
                "release_id",
            ]
            and isinstance(nav_rules, dict)
            and nav_rules.get("exact_revision_only") is True
            and nav_rules.get("latest_alias_forbidden") is True
            and nav_rules.get("business_recompute") is False
            and nav_rules.get("persistence_access") is False
        ),
        "production_desktop_composition_present": all(
            token in product_shell
            for token in (
                "create_m1_workspace",
                "create_m3_workspace_navigation",
                "create_m4_workspace",
                "create_m6_workspace",
                "create_m7_workspace",
                "create_m8_workspace",
                "create_m9_workspace",
                "tpaaB5ProductNavigation",
                "tpaaB5ProductSpine",
                "tpaaB5SemanticLegend",
            )
        ) and all(
            token in shell
            for token in (
                "ProductDesktopTransport",
                "create_product_workspace",
                "product_transport",
            )
        ) and "product_transport=controller" in desktop,
        "unified_local_transport_present": all(
            f"def {method}" in local_backend
            for method in (
                "m3_request_json",
                "m4_request_json",
                "m6_request_json",
                "m7_request_json",
                "m8_request_json",
                "m9_request_json",
                "runtime_request_json",
            )
        ) and all(
            token in local_backend
            for token in (
                '"/runtime/qualification"',
                '"/runtime/observability"',
                "LOCAL_HTTP_PATH_FORBIDDEN",
            )
        ),
        "trajectory_media_adapter_present": all(
            token in visualization
            for token in (
                "TPAA_TRAJECTORY_PRESENTATION_V1",
                "build_2d_polyline",
                "build_cesium_trajectory_packets",
                "SESSION_TIME_RELATIVE_ONLY",
                "VIS_BUSINESS_RECOMPUTE_FORBIDDEN",
                "VIS_PERSISTENCE_ACCESS_FORBIDDEN",
                "VIS_MUTABLE_ALIAS_FORBIDDEN",
            )
        ),
        "windows_real_qt_qualification_passed": windows_ok,
        "linux_real_qt_qualification_passed": linux_ok,
        "cross_platform_logical_fingerprint_equal": (
            windows_ok
            and linux_ok
            and windows_qualification.get("logical_fingerprint")
            == linux_qualification.get("logical_fingerprint")
        ),
        "workflow_keeps_fourteen_job_topology": (
            "Execute PIQB B5 Desktop replay visualization qualification" in workflow
            and "Review PIQB B5 Desktop replay and visualization" in workflow
            and "\n  piqb-b5-review:" not in workflow
        ),
        "candidate_revision_exact": expected_revision == checked_out_revision,
        "required_jobs_exact": (
            required_jobs_success == 14 and required_jobs_total == 14
        ),
        "run_conclusion_success": run_conclusion == "success",
    }
    failed = sorted(key for key, ok in acceptance.items() if not ok)
    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    status = "PASS" if not failed else "FAIL"
    decision = (
        "GO"
        if status == "PASS" and protected_main
        else "PENDING_PROTECTED_MAIN"
        if status == "PASS"
        else "NO_GO"
    )
    qualified = status == "PASS" and protected_main
    return {
        "schema": "TPAA_PIQB_B5_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "source_b4_protected_main_sha": SOURCE_B4_SHA,
        "expected_revision": expected_revision,
        "checked_out_revision": checked_out_revision,
        "event_name": event_name,
        "git_ref": git_ref,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "status": status,
        "decision": decision,
        "failed_acceptance": failed,
        "acceptance": acceptance,
        "tasks": {task: status == "PASS" for task in EXPECTED_TASKS},
        "implementation_complete": status == "PASS",
        "formal_completion_blocked_by_protected_main": not qualified,
        "desktop_replay_visualization_qualified": qualified,
        "qualification": (
            "PIQB_B5_QUALIFIED"
            if qualified
            else "PIQB_B5_CANDIDATE"
            if status == "PASS"
            else "PIQB_B5_NOT_QUALIFIED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows-qualification", type=Path, required=True)
    parser.add_argument("--linux-qualification", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", type=int, required=True)
    parser.add_argument("--required-jobs-total", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = review(
        expected_revision=args.expected_revision,
        checked_out_revision=args.checked_out_revision,
        event_name=args.event_name,
        git_ref=args.git_ref,
        run_conclusion=args.run_conclusion,
        required_jobs_success=args.required_jobs_success,
        required_jobs_total=args.required_jobs_total,
        windows_qualification=_json(args.windows_qualification),
        linux_qualification=_json(args.linux_qualification),
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
