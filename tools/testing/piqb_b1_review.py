"""PIQB B1 runtime-composition qualification review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
TASK_BASELINE = BASE / "B1_TASK_BASELINE.json"
SOURCE_B0_SHA = "cc4099c0780e092b33e8812373c62a44cb8ea0f6"
EXPECTED_TASKS = (
    "PIQB-B1-001",
    "PIQB-B1-002",
    "PIQB-B1-003",
    "PIQB-B1-004",
    "PIQB-B1-005",
    "PIQB-B1-006",
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def review(
    *,
    expected_revision: str,
    checked_out_revision: str,
    event_name: str,
    git_ref: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
) -> dict[str, object]:
    baseline = _json(TASK_BASELINE)
    tasks = baseline.get("tasks")
    task_ids = tuple(
        item.get("task_id")
        for item in tasks
        if isinstance(tasks, list) and isinstance(item, dict)
    ) if isinstance(tasks, list) else ()

    composition = _text("src/tpaa_runtime/composition.py")
    admission = _text("src/tpaa_runtime/admission.py")
    desktop = _text("src/tpaa_api/desktop.py")
    child = _text("src/tpaa_api/local_backend_child.py")
    gui_transport = _text("src/tpaa_gui/local_backend.py")
    m9 = _text("src/tpaa_application/m9_workspace.py")
    app_service = _text("src/tpaa_application/service.py")
    api_base = _text("src/tpaa_api/app.py")
    api_runtime = _text("src/tpaa_api/runtime.py")

    acceptance = {
        "b0_entry_exact": (
            baseline.get("source_b0_protected_main_sha") == SOURCE_B0_SHA
            and baseline.get("source_b0_qualification") == "PIQB_B0_QUALIFIED"
        ),
        "task_inventory_exact_6": (
            baseline.get("task_count") == 6
            and task_ids == EXPECTED_TASKS
        ),
        "db_schema_1_6_0_no_authority_change": (
            baseline.get("db_schema_version") == "1.6.0"
            and isinstance(baseline.get("scope"), dict)
            and baseline["scope"].get("no_db_schema_change") is True
            and baseline["scope"].get("no_canonical_mutation") is True
        ),
        "composition_root_present": all(
            token in composition
            for token in (
                "build_desktop_application",
                "build_service_application",
                "create_full_desktop_app",
                "create_full_service_app",
                "ApplicationService(",
            )
        ),
        "desktop_full_route_composition": all(
            token in desktop
            for token in (
                '"/m1/"',
                '"/m3/"',
                '"/m4/"',
                '"/m6/"',
                '"/m7/"',
                '"/m8/"',
                '"/m9/"',
                "register_m9_routes",
            )
        ),
        "local_child_uses_composition_root": (
            "build_desktop_application" in child
            and "create_full_desktop_app" in child
            and "M1PublicationService" not in child
            and "ApplicationService(" not in child
        ),
        "unified_desktop_transport": (
            "def request_json(" in gui_transport
            and "def m1_request_json(" in gui_transport
            and "LOCAL_HTTP_PATH_FORBIDDEN" in gui_transport
        ),
        "exact_admission_chain_present": all(
            token in admission
            for token in (
                "P1_M5_QUALIFIED",
                "P2_M6_QUALIFIED",
                "P3_M7_QUALIFIED",
                "P4_P5_M8_QUALIFIED",
                "P6_M9_QUALIFIED",
                "37000963653",
            )
        ),
        "p6_naked_boolean_removed": (
            "p6_admitted: bool" not in m9
            and "admission_evidence: P6AdmissionEvidence" in m9
            and 'assert_p6_claim_allowed("P6"' in m9
        ),
        "feature_availability_application_boundary": (
            "feature_availability" in app_service
            and '"/runtime/features"' in api_runtime
            and "register_product_runtime_routes" in desktop
            and "ProductFeatureAvailability" in admission
        ),
        "legacy_base_api_surface_not_extended_by_piqb": (
            '"/runtime/features"' not in api_base
        ),
        "b2_b3_not_pulled_forward": all(
            token not in composition
            for token in ("sqlite3", "psycopg", "polars", "pyarrow")
        ),
        "composition_contract_present": (
            ROOT / "tests" / "contract" / "test_piqb_b1_runtime_composition.py"
        ).is_file(),
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
    return {
        "schema": "TPAA_PIQB_B1_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "source_b0_protected_main_sha": SOURCE_B0_SHA,
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
        "formal_completion_blocked_by_protected_main": not (
            status == "PASS" and protected_main
        ),
        "runtime_composition_qualified": status == "PASS" and protected_main,
        "qualification": (
            "PIQB_B1_QUALIFIED"
            if status == "PASS" and protected_main
            else "PIQB_B1_CANDIDATE"
            if status == "PASS"
            else "PIQB_B1_NOT_QUALIFIED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", required=True, type=int)
    parser.add_argument("--required-jobs-total", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = review(
        expected_revision=args.expected_revision,
        checked_out_revision=args.checked_out_revision,
        event_name=args.event_name,
        git_ref=args.git_ref,
        run_conclusion=args.run_conclusion,
        required_jobs_success=args.required_jobs_success,
        required_jobs_total=args.required_jobs_total,
    )
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
