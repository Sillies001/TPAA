#!/usr/bin/env python3
"""PIQB-1.0 final protected-main product qualification and release review."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
B6_BASELINE = ROOT / "docs" / "baseline" / "PIQB-1.0" / "B6_TASK_BASELINE.json"
B6_STATE = ROOT / "docs" / "baseline" / "PIQB-1.0" / "B6_IMPLEMENTATION_STATE.json"
RELEASE_CONTRACT = ROOT / "docs" / "baseline" / "PIQB-1.0" / "B6_RELEASE_CONTRACT.json"
PYPROJECT = ROOT / "pyproject.toml"
EXPECTED_TASK_IDS = tuple(f"PIQB-B6-{index:03d}" for index in range(1, 9))
WINDOWS_PROFILES = ("WINDOWS_DESKTOP_X64", "WINDOWS_SERVICE_X64")
LINUX_PROFILES = ("LINUX_DESKTOP_X64", "LINUX_SERVICE_X64")


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return cast(dict[str, Any], payload)


def _task_ids(baseline: dict[str, Any]) -> tuple[str, ...]:
    rows = baseline.get("tasks")
    if not isinstance(rows, list):
        raise RuntimeError("B6 task baseline rows missing")
    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
            raise RuntimeError("B6 task baseline row invalid")
        result.append(str(row["task_id"]))
    return tuple(result)


def _project_version() -> str:
    raw = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = raw.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise RuntimeError("project version unavailable")
    return str(project["version"])


def _profile_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        raise RuntimeError("B6 platform profile rows missing")
    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("profile_id"), str):
            raise RuntimeError("B6 platform profile row invalid")
        result.append(str(row["profile_id"]))
    return tuple(result)


def _package_hashes(payload: dict[str, Any]) -> dict[str, str]:
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        raise RuntimeError("B6 platform profile rows missing")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("B6 platform profile row invalid")
        profile = row.get("profile_id")
        digest = row.get("package_sha256")
        if not isinstance(profile, str) or not isinstance(digest, str):
            raise RuntimeError("B6 package identity missing")
        result[profile] = digest
    return result


def review(
    *,
    windows_path: Path,
    linux_path: Path,
    postgres_path: Path,
    b4_path: Path,
    expected_revision: str,
    checked_out_revision: str,
    event_name: str,
    git_ref: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
) -> dict[str, Any]:
    baseline = _json(B6_BASELINE)
    state = _json(B6_STATE)
    contract = _json(RELEASE_CONTRACT)
    windows = _json(windows_path)
    linux = _json(linux_path)
    postgres = _json(postgres_path)
    b4 = _json(b4_path)

    state_rows = state.get("task_state")
    if not isinstance(state_rows, dict):
        raise RuntimeError("B6 implementation task state missing")
    states = {
        task_id: (
            cast(dict[str, Any], state_rows.get(task_id, {})).get("state")
        )
        for task_id in EXPECTED_TASK_IDS
    }
    completed_states = {"COMPLETE", "COMPLETE_CANDIDATE"}
    pg_acceptance = postgres.get("acceptance")
    if not isinstance(pg_acceptance, dict):
        raise RuntimeError("PIQB B2 PostgreSQL acceptance missing")

    protected_main = (
        event_name == "push"
        and git_ref == "refs/heads/main"
        and expected_revision == checked_out_revision
    )
    acceptance = {
        "task_inventory_exact_8": (
            baseline.get("task_count") == 8
            and _task_ids(baseline) == EXPECTED_TASK_IDS
        ),
        "b5_entry_exact": (
            baseline.get("source_b5_protected_main_sha")
            == "eb3f03f8baeb1bfc56b8bc138848636de1d15776"
            and baseline.get("source_b5_qualification") == "PIQB_B5_QUALIFIED"
            and baseline.get("source_b5_run_number") == 628
        ),
        "all_tasks_complete_candidate": all(
            states[task_id] in completed_states for task_id in EXPECTED_TASK_IDS
        ),
        "candidate_revision_exact": (
            expected_revision == checked_out_revision
            and windows.get("source_revision") == expected_revision
            and linux.get("source_revision") == expected_revision
            and postgres.get("source_revision") == expected_revision
            and b4.get("source_revision") == expected_revision
        ),
        "product_version_1_0_0": (
            _project_version() == "1.0.0"
            and baseline.get("product_version") == "1.0.0"
            and contract.get("product_version") == "1.0.0"
            and windows.get("product_version") == "1.0.0"
            and linux.get("product_version") == "1.0.0"
        ),
        "db_1_9_authority_exact": (
            baseline.get("db_schema_version") == "1.9.0"
            and contract.get("db_schema_version") == "1.9.0"
            and windows.get("db_schema_version") == "1.9.0"
            and linux.get("db_schema_version") == "1.9.0"
            and cast(dict[str, Any], postgres.get("scope", {})).get(
                "db_schema_version"
            )
            == "1.9.0"
        ),
        "windows_final_product_qualification_pass": (
            windows.get("schema") == "TPAA_PIQB_B6_PLATFORM_QUALIFICATION_V1"
            and windows.get("status") == "PASS"
            and windows.get("failed_acceptance") == []
            and _profile_ids(windows) == WINDOWS_PROFILES
        ),
        "linux_final_product_qualification_pass": (
            linux.get("schema") == "TPAA_PIQB_B6_PLATFORM_QUALIFICATION_V1"
            and linux.get("status") == "PASS"
            and linux.get("failed_acceptance") == []
            and _profile_ids(linux) == LINUX_PROFILES
        ),
        "cross_platform_logical_equivalence": (
            windows.get("logical_product_hash")
            == linux.get("logical_product_hash")
            and windows.get("logical_product") == linux.get("logical_product")
        ),
        "current_db_restart_recovery_pass": (
            postgres.get("status") == "PASS"
            and postgres.get("failed_acceptance") == []
            and pg_acceptance.get("sqlite_current_db_1_9") is True
            and pg_acceptance.get("postgres_current_db_1_9") is True
            and pg_acceptance.get("sqlite_restart_exact") is True
            and pg_acceptance.get("postgres_restart_exact") is True
            and pg_acceptance.get("sqlite_postgres_logical_parity") is True
            and pg_acceptance.get(
                "orphan_recovery_preserves_registered_both_engines"
            )
            is True
        ),
        "same_run_product_api_security_observability_pass": (
            b4.get("status") == "PASS"
            and b4.get("failed_acceptance") == []
            and cast(dict[str, Any], b4.get("scope", {})).get(
                "db_schema_version"
            )
            == "1.9.0"
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "sqlite_db_1_9"
            )
            is True
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "postgres_db_1_9"
            )
            is True
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "product_openapi_exact"
            )
            is True
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "product_client_exact"
            )
            is True
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "product_route_count_exact_10"
            )
            is True
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "product_exact_id_only"
            )
            is True
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "audit_semantic_parity"
            )
            is True
            and cast(dict[str, Any], b4.get("acceptance", {})).get(
                "observability_exact"
            )
            is True
        ),
        "release_contract_exact": (
            contract.get("schema") == "TPAA_PIQB_B6_RELEASE_CONTRACT_V1"
            and contract.get("piqb_exit_qualification") == "PIQB_1_0_QUALIFIED"
            and contract.get("mandatory_profiles")
            == [*WINDOWS_PROFILES, *LINUX_PROFILES]
        ),
        "required_jobs_exact": (
            required_jobs_success == 14 and required_jobs_total == 14
        ),
        "run_conclusion_success": run_conclusion == "success",
        "historical_m5_semantics_preserved": (
            cast(dict[str, Any], contract.get("provenance", {})).get(
                "historical_m5_qualification_semantics_rewritten"
            )
            is False
        ),
        "no_m10_p7": cast(dict[str, Any], baseline.get("scope", {})).get(
            "no_m10_p7"
        )
        is True,
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    status = "PASS" if not failed else "FAIL"
    decision = (
        "GO"
        if status == "PASS" and protected_main
        else "PENDING_PROTECTED_MAIN"
        if status == "PASS"
        else "NO_GO"
    )
    qualification = (
        "PIQB_1_0_QUALIFIED"
        if decision == "GO"
        else "PIQB_B6_CANDIDATE"
        if status == "PASS"
        else "PIQB_B6_NOT_QUALIFIED"
    )
    package_hashes = {
        **_package_hashes(windows),
        **_package_hashes(linux),
    }
    return {
        "schema": "TPAA_PIQB_EXIT_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "status": status,
        "decision": decision,
        "qualification": qualification,
        "implementation_complete": status == "PASS",
        "formal_release_claimed": decision == "GO",
        "formal_completion_blocked_by_protected_main": (
            status == "PASS" and not protected_main
        ),
        "protected_main_exact": protected_main,
        "event_name": event_name,
        "git_ref": git_ref,
        "source_revision": expected_revision,
        "checked_out_revision": checked_out_revision,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "run_conclusion": run_conclusion,
        "product_version": "1.0.0",
        "db_schema_version": "1.9.0",
        "package_sha256_by_profile": package_hashes,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "tasks": {
            task_id: status == "PASS"
            for task_id in EXPECTED_TASK_IDS
        },
        "scope": {
            "p1_p6_qualified_product": status == "PASS",
            "windows_linux_desktop_service_profiles": 4,
            "current_db_schema_version": "1.9.0",
            "historical_m5_authority_mutated": False,
            "no_m10_p7": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows-qualification", type=Path, required=True)
    parser.add_argument("--linux-qualification", type=Path, required=True)
    parser.add_argument("--postgres-recovery", type=Path, required=True)
    parser.add_argument("--b4-qualification", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", type=int, required=True)
    parser.add_argument("--required-jobs-total", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            windows_path=args.windows_qualification,
            linux_path=args.linux_qualification,
            postgres_path=args.postgres_recovery,
            b4_path=args.b4_qualification,
            expected_revision=args.expected_revision,
            checked_out_revision=args.checked_out_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
            run_conclusion=args.run_conclusion,
            required_jobs_success=args.required_jobs_success,
            required_jobs_total=args.required_jobs_total,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_PIQB_EXIT_REVIEW_V1",
            "status": "FAIL",
            "decision": "NO_GO",
            "qualification": "PIQB_B6_NOT_QUALIFIED",
            "failed_acceptance": ["review_exception"],
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    print(rendered, end="")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
