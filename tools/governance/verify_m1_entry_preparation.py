#!/usr/bin/env python3
"""Verify SDIB-1.0.1 M1 Entry preparation records.

This verifier covers preparation evidence for §19.1 conditions 6, 7, 9 and 10.
It intentionally does not decide M1 admission and does not satisfy condition 8
(human role assignment).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.manifest.m1_entry_manifest import build_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKLOG = REPO_ROOT / "docs" / "planning" / "M1_BACKLOG_IMPORT.json"
FIXTURE_POLICY = REPO_ROOT / "tools" / "testing" / "M1_FIXTURE_POLICY.json"
ARCH_REVIEW = REPO_ROOT / "docs" / "reviews" / "M1_ARCHITECTURE_BLOCKER_REVIEW.json"

EXPECTED_TASK_IDS = (
    "M1-DATA-001", "M1-DATA-002", "M1-DATA-003", "M1-DATA-004", "M1-DATA-005",
    "M1-DATA-006", "M1-DATA-007",
    "M1-WORLD-001", "M1-WORLD-002", "M1-WORLD-003", "M1-WORLD-004",
    "M1-WORLD-005", "M1-WORLD-006", "M1-WORLD-007",
    "M1-MET-001", "M1-MET-002", "M1-MET-003", "M1-MET-004", "M1-MET-005",
    "M1-MET-006", "M1-MET-007", "M1-MET-008",
    "M1-OBS-001", "M1-OBS-002", "M1-OBS-003", "M1-OBS-004", "M1-OBS-005",
    "M1-STO-001", "M1-STO-002", "M1-STO-003",
    "M1-API-001", "M1-API-002", "M1-API-003", "M1-API-004", "M1-API-005",
    "M1-GUI-001", "M1-GUI-002", "M1-GUI-003", "M1-GUI-004", "M1-GUI-005",
    "M1-GUI-006", "M1-GUI-007",
    "M1-TST-001", "M1-TST-002", "M1-TST-003", "M1-TST-004", "M1-TST-005",
    "M1-TST-006", "M1-TST-007", "M1-TST-008", "M1-TST-009", "M1-TST-010",
    "M1-PLAT-001", "M1-PLAT-002", "M1-PLAT-003", "M1-PLAT-004",
)

EXPECTED_FIXTURES = {
    "BF_M1_NOMINAL_V1",
    "BF_M1_GAP_V1",
    "BF_M1_ANGLE_WRAP_V1",
    "BF_M1_STRUCTURED_PARTIAL_V1",
    "BF_M1_STAGE_BOUNDARY_V1",
    "BF_M1_REPLAY_V1",
    "BF_M1_CROSS_PLATFORM_V1",
    "BF_M1_FAILURE_V1",
}

EXPECTED_LAYERS = {"Context", "Stage", "World", "Release", "API", "GUI"}


def _load_json(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return raw


def _check(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"check": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _desktop_profile() -> str:
    if sys.platform == "win32":
        return "WINDOWS_DESKTOP_X64"
    if sys.platform.startswith("linux"):
        return "LINUX_DESKTOP_X64"
    raise RuntimeError(f"unsupported M1 Entry verification platform: {sys.platform}")


def verify() -> dict[str, object]:
    checks: list[dict[str, str]] = []

    backlog = _load_json(BACKLOG)
    records_obj = backlog.get("records")
    records = records_obj if isinstance(records_obj, list) else []
    task_ids: list[str] = []
    issue_urls: list[str] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        issue = item.get("issue")
        if isinstance(task_id, str):
            task_ids.append(task_id)
        if isinstance(issue, dict):
            url = issue.get("url")
            if isinstance(url, str):
                issue_urls.append(url)
    checks.append(_check("backlog_count", len(records) == 56, f"records={len(records)}"))
    checks.append(_check("backlog_task_ids", set(task_ids) == set(EXPECTED_TASK_IDS), f"unique={len(set(task_ids))}"))
    checks.append(_check("backlog_issue_urls", len(issue_urls) == 56 and all(url.startswith("https://github.com/Sillies001/TPAA/issues/") for url in issue_urls), f"issue_urls={len(issue_urls)}"))
    checks.append(_check("backlog_boundary", backlog.get("admission_boundary") == "PLANNING_ONLY_M1_NOT_ADMITTED", str(backlog.get("admission_boundary"))))

    fixture = _load_json(FIXTURE_POLICY)
    bundles_obj = fixture.get("bundles")
    bundles = bundles_obj if isinstance(bundles_obj, list) else []
    fixture_ids: list[str] = []
    for item in bundles:
        if isinstance(item, dict):
            value = item.get("id")
            if isinstance(value, str):
                fixture_ids.append(value)
    data_governance = fixture.get("data_governance")
    dg = data_governance if isinstance(data_governance, dict) else {}
    independence = fixture.get("expected_result_independence")
    independent = independence if isinstance(independence, dict) else {}
    checks.append(_check("fixture_ids", set(fixture_ids) == EXPECTED_FIXTURES and len(fixture_ids) == 8, f"fixtures={len(fixture_ids)}"))
    checks.append(_check("fixture_synthetic_default", dg.get("default_allowed_classifications") == ["SYNTHETIC"], str(dg.get("default_allowed_classifications"))))
    checks.append(_check("fixture_no_operational_dependency", dg.get("operational_dependency") is False, str(dg.get("operational_dependency"))))
    checks.append(_check("fixture_no_sensitive_dependency", dg.get("sensitive_dependency") is False, str(dg.get("sensitive_dependency"))))
    checks.append(_check("golden_independent_review", independent.get("golden_reviewer_independence_required") is True, str(independent.get("golden_reviewer_independence_required"))))

    arch = _load_json(ARCH_REVIEW)
    layers_obj = arch.get("required_layers")
    layers = {value for value in layers_obj if isinstance(value, str)} if isinstance(layers_obj, list) else set()
    checks.append(_check("architecture_review", arch.get("status") == "PASS" and arch.get("decision") == "NO_KNOWN_ARCHITECTURE_BLOCKER", f"{arch.get('status')} / {arch.get('decision')}"))
    checks.append(_check("architecture_layers", layers == EXPECTED_LAYERS, ",".join(sorted(layers))))
    checks.append(_check("architecture_no_bypass", arch.get("bypass_authorized") is False, str(arch.get("bypass_authorized"))))

    manifest = build_manifest(_desktop_profile())
    checks.append(_check("manifest_schema", manifest.get("schema") == "TPAA_M1_ENTRY_BUILD_MANIFEST_V1", str(manifest.get("schema"))))
    checks.append(_check("manifest_boundary", manifest.get("admission") == "M1_NOT_ADMITTED_BY_THIS_MANIFEST", str(manifest.get("admission"))))
    for key in (
        "source_revision",
        "core_baseline",
        "db_schema_version",
        "baseline_lock_sha256",
        "dependency_lock_sha256",
        "p1_metric_catalog_sha256",
        "stage_authority_sha256",
        "dto_authority_sha256",
    ):
        value = manifest.get(key)
        checks.append(_check(f"manifest:{key}", isinstance(value, str) and bool(value), str(value)))

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema": "TPAA_M1_ENTRY_PREPARATION_VERIFICATION_V1",
        "status": status,
        "admission": "M1_NOT_ADMITTED",
        "condition_8": "NOT_EVALUATED_HUMAN_ASSIGNMENT_REQUIRED",
        "checks": checks,
    }


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
