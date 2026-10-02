"""Static PIQB B0 product-topology qualification review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
SOURCE_MAIN_SHA = "06945127c86069918ffdfd415201d321d53aae4d"
EXPECTED_TASKS = (
    "PIQB-B0-001",
    "PIQB-B0-002",
    "PIQB-B0-003",
    "PIQB-B0-004",
    "PIQB-B0-005",
)
EXPECTED_FILES = {
    "PIQB-B0-001": "PRODUCT_COMPONENT_INVENTORY.json",
    "PIQB-B0-002": "PRODUCT_RUNTIME_TOPOLOGY.json",
    "PIQB-B0-003": "PRODUCT_REPOSITORY_MAPPING.json",
    "PIQB-B0-004": "PRODUCT_ADMISSION_MAPPING.json",
    "PIQB-B0-005": "PIQB_PRODUCT_GAP_BASELINE.json",
}
EXPECTED_SCHEMAS = {
    "PRODUCT_COMPONENT_INVENTORY.json": "TPAA_PIQB_PRODUCT_COMPONENT_INVENTORY_V1",
    "PRODUCT_RUNTIME_TOPOLOGY.json": "TPAA_PIQB_PRODUCT_RUNTIME_TOPOLOGY_V1",
    "PRODUCT_REPOSITORY_MAPPING.json": "TPAA_PIQB_PRODUCT_REPOSITORY_MAPPING_V1",
    "PRODUCT_ADMISSION_MAPPING.json": "TPAA_PIQB_PRODUCT_ADMISSION_MAPPING_V1",
    "PIQB_PRODUCT_GAP_BASELINE.json": "TPAA_PIQB_PRODUCT_GAP_BASELINE_V1",
}
REQUIRED_GAPS = {f"PIQB-GAP-{index:03d}" for index in range(1, 15)}


def _load(name: str) -> dict[str, Any]:
    value = json.loads((BASE / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name}: root must be object")
    return cast(dict[str, Any], value)


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
    acceptance: dict[str, bool] = {}

    artifacts = {name: _load(name) for name in EXPECTED_SCHEMAS}
    acceptance["baseline_markdown_present"] = (
        BASE / "TPAA_产品集成与最终资格化实施基线_PIQB-1.0.md"
    ).is_file()
    acceptance["schemas_exact"] = all(
        artifacts[name].get("schema") == schema
        for name, schema in EXPECTED_SCHEMAS.items()
    )
    acceptance["baseline_identity_exact"] = all(
        artifact.get("baseline") == "PIQB-1.0"
        and artifact.get("source_m9_protected_main_sha") == SOURCE_MAIN_SHA
        and artifact.get("db_schema_version") == "1.6.0"
        and artifact.get("umbrella_issue") == 206
        and artifact.get("batch_issue") == 207
        for artifact in artifacts.values()
    )

    inventory = artifacts["PRODUCT_COMPONENT_INVENTORY.json"]
    components = inventory.get("components")
    acceptance["component_inventory_nonempty"] = (
        isinstance(components, list) and len(components) >= 20
    )
    acceptance["b0_runtime_change_forbidden"] = (
        inventory.get("runtime_modification_permitted_in_b0") is False
        and artifacts["PRODUCT_RUNTIME_TOPOLOGY.json"].get("b0_runtime_change") is False
        and artifacts["PIQB_PRODUCT_GAP_BASELINE.json"].get(
            "runtime_changes_forbidden_in_b0"
        )
        is True
    )

    topology = artifacts["PRODUCT_RUNTIME_TOPOLOGY.json"]
    target = topology.get("target_frozen")
    acceptance["runtime_topology_frozen"] = (
        isinstance(target, dict)
        and isinstance(target.get("composition_root"), dict)
        and target["composition_root"].get("implementation_batch") == "B1"
    )

    mapping = artifacts["PRODUCT_REPOSITORY_MAPPING.json"]
    product_mapping = mapping.get("mapping")
    acceptance["repository_mapping_complete"] = (
        isinstance(product_mapping, list)
        and {item.get("product_family") for item in product_mapping if isinstance(item, dict)}
        == {
            "P1_SESSION_RELEASE",
            "LONGITUDINAL_RELEASE",
            "P2_ATTRIBUTION",
            "P3_TWIN_CAPABILITY",
            "P4_P5_ASSESSMENT",
            "P6_MODEL_PROJECTION_ADVISORY",
        }
        and mapping.get("no_shadow_schema") is True
    )

    admission = artifacts["PRODUCT_ADMISSION_MAPPING.json"]
    phases = admission.get("phases")
    acceptance["admission_mapping_p1_p6_exact"] = (
        isinstance(phases, list)
        and [item.get("phase") for item in phases if isinstance(item, dict)]
        == ["P1", "P2", "P3", "P4", "P5", "P6"]
        and all(item.get("qualified") is True for item in phases if isinstance(item, dict))
        and "naked booleans" in str(admission.get("rule"))
    )

    gaps = artifacts["PIQB_PRODUCT_GAP_BASELINE.json"].get("gaps")
    gap_ids = {
        item.get("gap_id")
        for item in gaps
        if isinstance(gaps, list) and isinstance(item, dict)
    } if isinstance(gaps, list) else set()
    acceptance["gap_baseline_exact"] = gap_ids == REQUIRED_GAPS

    acceptance["task_inventory_exact"] = tuple(EXPECTED_FILES) == EXPECTED_TASKS
    acceptance["candidate_revision_exact"] = expected_revision == checked_out_revision
    acceptance["required_jobs_exact"] = (
        required_jobs_success == 14 and required_jobs_total == 14
    )
    acceptance["run_conclusion_success"] = run_conclusion == "success"

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
        "schema": "TPAA_PIQB_B0_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "source_m9_protected_main_sha": SOURCE_MAIN_SHA,
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
        "product_topology_frozen": status == "PASS" and protected_main,
        "qualification": (
            "PIQB_B0_QUALIFIED"
            if status == "PASS" and protected_main
            else "PIQB_B0_CANDIDATE"
            if status == "PASS"
            else "PIQB_B0_NOT_QUALIFIED"
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
