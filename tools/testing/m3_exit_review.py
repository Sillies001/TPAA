#!/usr/bin/env python3
"""M3-TST-006 clean-reconstruction and protected-main Exit review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "docs" / "baseline" / "SDIB-1.2" / "M3_TASK_BASELINE.json"
TRACKING_ISSUE = 117

TASK_EVIDENCE = {
    "M3-WORLD-001": "m3-world-001-logical-equivalence.json",
    "M3-WORLD-002": "m3-world-002-logical-equivalence.json",
    "M3-WORLD-003": "m3-world-003-logical-equivalence.json",
    "M3-WORLD-004": "m3-world-004-logical-equivalence.json",
    "M3-WORLD-005": "m3-world-005-logical-equivalence.json",
    "M3-MET-001": "m3-met-001-logical-equivalence.json",
    "M3-MET-002": "m3-met-002-logical-equivalence.json",
    "M3-MET-003": "m3-met-003-logical-equivalence.json",
    "M3-MET-004": "m3-met-004-logical-equivalence.json",
    "M3-MET-005": "m3-met-005-logical-equivalence.json",
    "M3-MET-006": "m3-met-006-logical-equivalence.json",
    "M3-MET-007": "m3-met-007-logical-equivalence.json",
    "M3-MET-008": "m3-met-008-logical-equivalence.json",
    "M3-MET-009": "m3-met-009-logical-equivalence.json",
    "M3-OBS-001": "m3-obs-001-logical-equivalence.json",
    "M3-OBS-002": "m3-obs-002-logical-equivalence.json",
    "M3-OBS-003": "m3-obs-003-logical-equivalence.json",
    "M3-API-001": "m3-api-001-logical-equivalence.json",
    "M3-API-002": "m3-api-002-logical-equivalence.json",
    "M3-GUI-001": "m3-gui-001-logical-equivalence.json",
    "M3-GUI-002": "m3-gui-002-logical-equivalence.json",
    "M3-GUI-003": "m3-gui-003-logical-equivalence.json",
    "M3-TST-001": "m3-tst-001-logical-equivalence.json",
    "M3-TST-002": "m3-tst-002-logical-equivalence.json",
    "M3-TST-003": "m3-tst-003-logical-equivalence.json",
    "M3-TST-004": "m3-tst-004-logical-equivalence.json",
}
EXPECTED_TASK_IDS = tuple(TASK_EVIDENCE) + ("M3-TST-005", "M3-TST-006")


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path}: root must be a string-keyed object")
    return cast(dict[str, object], value)


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a string list")
    return tuple(cast(list[str], value))


def _task_identity(payload: dict[str, object], task_id: str) -> bool:
    if payload.get("task_id") == task_id:
        return True
    task_ids = payload.get("task_ids")
    return isinstance(task_ids, list) and task_id in task_ids


def _task_evidence_pass(
    payload: dict[str, object],
    *,
    task_id: str,
    expected_revision: str,
) -> bool:
    return (
        _task_identity(payload, task_id)
        and payload.get("status") == "PASS"
        and payload.get("source_revision") == expected_revision
        and payload.get("failed_acceptance") == []
        and payload.get("task_complete") is not False
        and payload.get("implementation_complete") is not False
    )


def _cold_start_pass(
    payload: dict[str, object],
    *,
    platform: str,
    expected_revision: str,
    require_postgres: bool,
) -> bool:
    base = (
        payload.get("schema") == "TPAA_M0_COLD_START_V2"
        and payload.get("status") == "PASS"
        and payload.get("source_revision") == expected_revision
        and payload.get("platform") == platform
        and payload.get("clean_clone") is True
        and payload.get("uv_sync_locked") is True
        and payload.get("m0_gates") == "PASS"
        and payload.get("worktree_clean") is True
    )
    if not base:
        return False
    if require_postgres:
        return (
            payload.get("postgres_bootstrap") == "PASS"
            and payload.get("postgres_repository") == "PASS"
        )
    return True


def review(
    *,
    logical_root: Path,
    platform_artifact_root: Path,
    tst005_path: Path,
    postgres_cold_start_path: Path,
    expected_revision: str,
    event_name: str,
    git_ref: str,
) -> dict[str, object]:
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be an exact 40-character Git SHA")

    baseline = _load(BASELINE)
    raw_tasks = baseline.get("tasks")
    if not isinstance(raw_tasks, list) or not all(isinstance(item, dict) for item in raw_tasks):
        raise ValueError("M3 task baseline tasks must be object rows")
    baseline_task_ids = tuple(str(item.get("task_id")) for item in raw_tasks)

    task_acceptance: dict[str, bool] = {}
    task_evidence_hashes: dict[str, str] = {}
    upstream_failed_acceptance_empty = True
    logical_payloads: dict[str, dict[str, object]] = {}
    for task_id, filename in TASK_EVIDENCE.items():
        path = logical_root / filename
        payload = _load(path)
        logical_payloads[task_id] = payload
        task_acceptance[task_id] = _task_evidence_pass(
            payload,
            task_id=task_id,
            expected_revision=expected_revision,
        )
        upstream_failed_acceptance_empty = (
            upstream_failed_acceptance_empty
            and payload.get("failed_acceptance") == []
        )
        task_evidence_hashes[task_id] = hashlib.sha256(path.read_bytes()).hexdigest()

    tst005 = _load(tst005_path)
    tst005_acceptance = _mapping(
        tst005.get("acceptance"),
        field="M3-TST-005.acceptance",
    )
    tst005_complete = (
        tst005.get("schema")
        == "TPAA_M3_TST_005_RELEASE_API_GUI_STORAGE_QUALIFICATION_V1"
        and _task_evidence_pass(
            tst005,
            task_id="M3-TST-005",
            expected_revision=expected_revision,
        )
        and bool(tst005_acceptance)
        and all(value is True for value in tst005_acceptance.values())
    )
    task_acceptance["M3-TST-005"] = tst005_complete
    task_evidence_hashes["M3-TST-005"] = hashlib.sha256(
        tst005_path.read_bytes()
    ).hexdigest()
    upstream_failed_acceptance_empty = (
        upstream_failed_acceptance_empty
        and tst005.get("failed_acceptance") == []
    )

    runtime_product = _mapping(
        logical_payloads["M3-MET-009"].get("logical_product"),
        field="M3-MET-009.logical_product",
    )
    runtime_codes = _strings(
        runtime_product.get("metric_codes"),
        field="M3-MET-009.metric_codes",
    )
    tst005_product = _mapping(
        tst005.get("logical_product"),
        field="M3-TST-005.logical_product",
    )
    qualified_codes = _strings(
        tst005_product.get("metric_codes"),
        field="M3-TST-005.metric_codes",
    )

    windows_cold = _load(
        platform_artifact_root / "devops" / "windows" / "cold-start.json"
    )
    linux_cold = _load(
        platform_artifact_root / "devops" / "linux" / "cold-start.json"
    )
    postgres_cold = _load(postgres_cold_start_path)

    acceptance = {
        "baseline_task_count_exact_28": (
            baseline.get("task_count") == 28 and len(baseline_task_ids) == 28
        ),
        "baseline_task_ids_exact": baseline_task_ids == EXPECTED_TASK_IDS,
        "logical_task_evidence_exact_26": (
            len(TASK_EVIDENCE) == 26
            and all(task_acceptance[task_id] for task_id in TASK_EVIDENCE)
        ),
        "tst005_exact_revision_complete": tst005_complete,
        "upstream_failed_acceptance_empty": upstream_failed_acceptance_empty,
        "runtime_116_executable_codes_exact": (
            len(runtime_codes) == 116
            and len(set(runtime_codes)) == 116
            and task_acceptance["M3-MET-009"]
        ),
        "tst005_116_qualified_codes_exact_and_match_runtime": (
            len(qualified_codes) == 116
            and len(set(qualified_codes)) == 116
            and qualified_codes == runtime_codes
        ),
        "windows_clean_source_baseline_reconstruction_pass": _cold_start_pass(
            windows_cold,
            platform="windows",
            expected_revision=expected_revision,
            require_postgres=False,
        ),
        "linux_clean_source_baseline_reconstruction_pass": _cold_start_pass(
            linux_cold,
            platform="linux",
            expected_revision=expected_revision,
            require_postgres=False,
        ),
        "postgres_clean_source_baseline_reconstruction_pass": _cold_start_pass(
            postgres_cold,
            platform="linux",
            expected_revision=expected_revision,
            require_postgres=True,
        ),
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    implementation_complete = not failed

    task_acceptance["M3-TST-006"] = implementation_complete
    task_evidence_hashes["M3-TST-006"] = "SELF:TPAA_M3_EXIT_REVIEW_V1"
    acceptance["task_evidence_exact_28"] = (
        len(task_acceptance) == 28
        and tuple(task_acceptance) == EXPECTED_TASK_IDS
        and all(task_acceptance.values())
    )
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    implementation_complete = not failed
    task_acceptance["M3-TST-006"] = implementation_complete

    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    task_complete = implementation_complete and protected_main
    decision = (
        "GO"
        if task_complete
        else "PENDING_PROTECTED_MAIN"
        if implementation_complete
        else "NO_GO"
    )
    unresolved_risks: list[dict[str, object]] = []
    if failed:
        unresolved_risks.append({"kind": "acceptance", "items": failed})

    return {
        "schema": "TPAA_M3_EXIT_REVIEW_V1",
        "task_id": "M3-TST-006",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "task_complete": task_complete,
        "implementation_complete": implementation_complete,
        "formal_completion_blocked_by_protected_main": (
            implementation_complete and not protected_main
        ),
        "protected_main_exact": protected_main,
        "source_revision": expected_revision,
        "task_count": len(EXPECTED_TASK_IDS),
        "task_ids": list(EXPECTED_TASK_IDS),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": task_evidence_hashes,
        "metric_codes": list(runtime_codes),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "unresolved_risks": unresolved_risks,
        "scope": {
            "cold_start_and_m3_exit_review_only": True,
            "clean_source_baseline_reconstruction_executed": True,
            "windows_linux_exact_revision_evidence_reviewed": True,
            "sqlite_postgresql_parity_reused_from_m3_tst_005": True,
            "all_116_executable_p1_metrics_qualified": True,
            "protected_main_required_for_go": True,
            "business_metric_semantics_recomputed": False,
            "catalog_formulas_modified": False,
            "applicability_modified": False,
            "publication_routes_modified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logical-root", type=Path, required=True)
    parser.add_argument("--platform-artifact-root", type=Path, required=True)
    parser.add_argument("--tst005", type=Path, required=True)
    parser.add_argument("--postgres-cold-start", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            logical_root=args.logical_root,
            platform_artifact_root=args.platform_artifact_root,
            tst005_path=args.tst005,
            postgres_cold_start_path=args.postgres_cold_start,
            expected_revision=args.expected_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
        )
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_EXIT_REVIEW_V1",
            "task_id": "M3-TST-006",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "decision": "NO_GO",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
