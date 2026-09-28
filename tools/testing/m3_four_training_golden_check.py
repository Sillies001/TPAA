#!/usr/bin/env python3
"""M3-TST-002 four-training Stage/World/Event Golden qualification."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKING_ISSUE = 117

EXPECTED_STAGE_PROFILES = {
    "BASIC": "BASIC_FLIGHT_V1",
    "WVR": "WVR_ENGAGEMENT_V1",
    "BVR": "BVR_KILL_CHAIN_V1",
    "STRIKE": "STRIKE_MISSION_V1",
}
EXPECTED_STAGE_ORDERS = {
    "BASIC": (
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ),
    "WVR": (
        "MERGE",
        "POSITION_ADVANTAGE",
        "MANEUVER",
        "WEAPON_ENVELOPE",
        "LAUNCH",
        "KILL_ASSESSMENT",
    ),
    "BVR": (
        "DETECTION",
        "TRACK",
        "IDENTIFICATION",
        "DECISION",
        "WEAPON_EMPLOYMENT",
        "ASSESSMENT",
    ),
    "STRIKE": (
        "MISSION_SETUP",
        "ROUTE_TASK_EXECUTION",
        "TARGET_INFORMATION_AVAILABLE",
        "TARGET_ASSOCIATION",
        "DESIGNATION_TRACK",
        "TRAINING_ATTACK_EVENT",
        "RANGE_SIM_ADJUDICATION",
        "POST_EVENT_TASK_TRANSITION",
        "RECOVERY",
    ),
}
EXPECTED_FIXTURE_CATEGORIES = (
    "NOMINAL",
    "BOUNDARY",
    "GAP",
    "INSUFFICIENT",
    "INVALID",
    "APPLICABILITY",
)
EXPECTED_FIXTURE_TRAINING_TYPES = (
    "BASIC_FLIGHT",
    "WVR",
    "BVR",
    "STRIKE",
)


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _rows(value: object, *, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(
        isinstance(item, dict) for item in value
    ):
        raise ValueError(f"{field} must be object rows")
    return cast(list[dict[str, object]], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be non-empty text")
    return value


def _acceptance(evidence: dict[str, object], *, field: str) -> dict[str, object]:
    return _object(evidence.get("acceptance"), field=f"{field}.acceptance")


def _logical(evidence: dict[str, object], *, field: str) -> dict[str, object]:
    return _object(evidence.get("logical_product"), field=f"{field}.logical_product")


def _all_acceptance_true(
    evidence: dict[str, object],
    *,
    field: str,
) -> bool:
    acceptance = _acceptance(evidence, field=field)
    return bool(acceptance) and all(value is True for value in acceptance.values())


def _failed_empty(evidence: dict[str, object]) -> bool:
    return evidence.get("failed_acceptance") == []


def _stage_order(
    evidence: dict[str, object],
    *,
    field: str,
) -> tuple[str, ...]:
    logical = _logical(evidence, field=field)
    stages = _rows(logical.get("stages"), field=f"{field}.logical_product.stages")
    return tuple(
        _text(stage.get("stage_type"), field=f"{field}.stage_type")
        for stage in stages
    )


def _profile(
    evidence: dict[str, object],
    *,
    field: str,
) -> str:
    logical = _logical(evidence, field=field)
    return _text(
        logical.get("stage_profile_id"),
        field=f"{field}.logical_product.stage_profile_id",
    )


def verify() -> dict[str, object]:
    repo_root = str(REPO_ROOT)
    src_root = str(REPO_ROOT / "src")
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tools.testing.m2_stage_world_lineage_check import verify as verify_basic
    from tools.testing.m3_bvr_world_check import verify as verify_bvr
    from tools.testing.m3_fixture_family_check import verify as verify_fixture
    from tools.testing.m3_strike_world_check import verify as verify_strike
    from tools.testing.m3_wvr_world_check import verify as verify_wvr

    basic = verify_basic()
    wvr = verify_wvr()
    bvr = verify_bvr()
    strike = verify_strike()
    fixture = verify_fixture()

    revision = _git_revision()
    upstream = {
        "BASIC": basic,
        "WVR": wvr,
        "BVR": bvr,
        "STRIKE": strike,
        "FIXTURE_FAMILY": fixture,
    }

    source_revisions_exact = all(
        evidence.get("source_revision") == revision
        for evidence in upstream.values()
    )
    upstream_pass = all(
        evidence.get("status") == "PASS"
        and _failed_empty(evidence)
        and _all_acceptance_true(evidence, field=name)
        for name, evidence in upstream.items()
    )

    stage_profiles = {
        "BASIC": _profile(basic, field="BASIC"),
        "WVR": _profile(wvr, field="WVR"),
        "BVR": _profile(bvr, field="BVR"),
        "STRIKE": _profile(strike, field="STRIKE"),
    }
    stage_orders = {
        "BASIC": _stage_order(basic, field="BASIC"),
        "WVR": _stage_order(wvr, field="WVR"),
        "BVR": _stage_order(bvr, field="BVR"),
        "STRIKE": _stage_order(strike, field="STRIKE"),
    }

    basic_acceptance = _acceptance(basic, field="BASIC")
    wvr_acceptance = _acceptance(wvr, field="WVR")
    bvr_acceptance = _acceptance(bvr, field="BVR")
    strike_acceptance = _acceptance(strike, field="STRIKE")
    fixture_acceptance = _acceptance(fixture, field="FIXTURE_FAMILY")

    fixture_logical = _logical(fixture, field="FIXTURE_FAMILY")
    cases = _rows(
        fixture_logical.get("cases"),
        field="FIXTURE_FAMILY.logical_product.cases",
    )
    case_categories = tuple(
        _text(case.get("category"), field="fixture.category")
        for case in cases
    )
    case_trainings = tuple(
        _text(case.get("training_type"), field="fixture.training_type")
        for case in cases
    )
    category_counts = dict(sorted(Counter(case_categories).items()))
    training_counts = dict(sorted(Counter(case_trainings).items()))

    boundary_cases = [
        case for case in cases if case.get("category") == "BOUNDARY"
    ]
    gap_cases = [case for case in cases if case.get("category") == "GAP"]
    insufficient_cases = [
        case for case in cases if case.get("category") == "INSUFFICIENT"
    ]
    invalid_cases = [
        case for case in cases if case.get("category") == "INVALID"
    ]
    replay_cases = [
        case
        for case in cases
        if case.get("category") in {"NOMINAL", "BOUNDARY"}
    ]

    acceptance = {
        "upstream_world_gates_pass": upstream_pass,
        "upstream_source_revision_exact": source_revisions_exact,
        "four_stage_profiles_exact": stage_profiles == EXPECTED_STAGE_PROFILES,
        "four_stage_orders_exact": stage_orders == EXPECTED_STAGE_ORDERS,
        "basic_regression_exact": (
            basic_acceptance.get("stage_profile_exact") is True
            and basic_acceptance.get("stage_order_exact") is True
            and basic_acceptance.get("stage_validity_exact") is True
            and basic_acceptance.get("world_roles_exact") is True
            and basic_acceptance.get("world_lineage_coverage_complete") is True
            and basic_acceptance.get("replay_stable") is True
        ),
        "wvr_stage_event_world_lineage_exact": (
            wvr_acceptance.get("stage_order_exact") is True
            and wvr_acceptance.get("event_projection_exact") is True
            and wvr_acceptance.get("required_worlds_exact") is True
            and wvr_acceptance.get("core_world_manifest_reused") is True
            and wvr_acceptance.get("worlds_episode_bound") is True
        ),
        "bvr_stage_event_world_lineage_exact": (
            bvr_acceptance.get("stage_order_exact") is True
            and bvr_acceptance.get("event_projection_exact") is True
            and bvr_acceptance.get("required_worlds_exact") is True
            and bvr_acceptance.get("core_world_manifest_reused") is True
            and bvr_acceptance.get("worlds_exact") is True
        ),
        "strike_stage_event_world_lineage_exact": (
            strike_acceptance.get("stage_order_exact") is True
            and strike_acceptance.get("event_projection_exact") is True
            and strike_acceptance.get("required_worlds_exact") is True
            and strike_acceptance.get("core_world_manifest_reused") is True
            and strike_acceptance.get("adjudication_world_absent_without_j") is True
        ),
        "fixture_matrix_exact_24": (
            len(cases) == 24
            and set(category_counts) == set(EXPECTED_FIXTURE_CATEGORIES)
            and all(
                category_counts[category] == 4
                for category in EXPECTED_FIXTURE_CATEGORIES
            )
            and set(training_counts) == set(EXPECTED_FIXTURE_TRAINING_TYPES)
            and all(
                training_counts[training] == 6
                for training in EXPECTED_FIXTURE_TRAINING_TYPES
            )
        ),
        "boundary_goldens_replay_stable": (
            len(boundary_cases) == 4
            and all(case.get("replay_stable") is True for case in boundary_cases)
            and fixture_acceptance.get("nominal_and_boundary_replay_stable") is True
        ),
        "gap_goldens_preserve_provenance": (
            len(gap_cases) == 4
            and all(case.get("declared_source_gaps") for case in gap_cases)
            and all(
                case.get("gap_business_semantics_executed") is False
                for case in gap_cases
            )
            and fixture_acceptance.get("gap_fixture_provenance_exact") is True
        ),
        "insufficient_goldens_fail_closed": (
            len(insufficient_cases) == 4
            and all(
                case.get("error_code") == "M3_PROFILE_REQUIRED_WORLD_MISMATCH"
                for case in insufficient_cases
            )
            and fixture_acceptance.get("insufficient_fails_closed_distinctly")
            is True
        ),
        "invalid_goldens_fail_closed": (
            len(invalid_cases) == 4
            and all(
                case.get("error_code") == "M3_PROFILE_STAGE_MARKER_ORDER_INVALID"
                for case in invalid_cases
            )
            and fixture_acceptance.get("invalid_fails_closed_distinctly") is True
        ),
        "four_training_replay_goldens_stable": (
            len(replay_cases) == 8
            and all(case.get("replay_stable") is True for case in replay_cases)
            and basic_acceptance.get("replay_stable") is True
            and wvr_acceptance.get("replay_stable") is True
            and bvr_acceptance.get("replay_stable") is True
            and strike_acceptance.get("replay_stable") is True
        ),
        "stage_authority_not_shadowed": (
            basic_acceptance.get("stage_authority_not_rewritten") is True
            and wvr_acceptance.get("no_shadow_stage_schema") is True
            and bvr_acceptance.get("no_shadow_stage_schema") is True
            and strike_acceptance.get("no_shadow_stage_schema") is True
        ),
        "event_persistence_schema_not_created": (
            wvr_acceptance.get("no_event_persistence_schema") is True
            and bvr_acceptance.get("no_event_persistence_schema") is True
            and strike_acceptance.get("no_event_persistence_schema") is True
        ),
        "fixture_family_contract_exact": (
            fixture_acceptance.get("four_training_types_exact") is True
            and fixture_acceptance.get("six_categories_each_exact") is True
            and fixture_acceptance.get("exact_24_case_matrix") is True
            and fixture_acceptance.get("host_paths_excluded") is True
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    logical_product = {
        "stage_profiles": stage_profiles,
        "stage_orders": {
            key: list(value)
            for key, value in stage_orders.items()
        },
        "fixture_category_counts": category_counts,
        "fixture_training_counts": training_counts,
        "basic": _logical(basic, field="BASIC"),
        "wvr": _logical(wvr, field="WVR"),
        "bvr": _logical(bvr, field="BVR"),
        "strike": _logical(strike, field="STRIKE"),
        "fixture_family": fixture_logical,
    }

    return {
        "schema": "TPAA_M3_TST_002_FOUR_TRAINING_GOLDEN_EVIDENCE_V1",
        "task_id": "M3-TST-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": revision,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "four_training_stage_world_event_qualification": True,
            "basic_regression_included": True,
            "boundary_gap_insufficient_invalid_included": True,
            "business_metric_values_executed": False,
            "metric_engine_executed": False,
            "persistence_executed": False,
            "shadow_stage_schema_created": False,
            "event_persistence_schema_created": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _object(
        json.loads(windows_path.read_text(encoding="utf-8")),
        field="windows",
    )
    linux = _object(
        json.loads(linux_path.read_text(encoding="utf-8")),
        field="linux",
    )
    checks = {
        "schemas_exact": (
            windows.get("schema")
            == linux.get("schema")
            == "TPAA_M3_TST_002_FOUR_TRAINING_GOLDEN_EVIDENCE_V1"
        ),
        "tasks_exact": (
            windows.get("task_id") == linux.get("task_id") == "M3-TST-002"
        ),
        "statuses_pass": windows.get("status") == linux.get("status") == "PASS",
        "tasks_complete": (
            windows.get("task_complete") is True
            and linux.get("task_complete") is True
        ),
        "implementation_complete": (
            windows.get("implementation_complete") is True
            and linux.get("implementation_complete") is True
        ),
        "revisions_exact": (
            windows.get("source_revision")
            == linux.get("source_revision")
            == expected_revision
        ),
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": (
            windows.get("acceptance") == linux.get("acceptance")
        ),
        "scope_equal": windows.get("scope") == linux.get("scope"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    complete = not failed
    return {
        "schema": (
            "TPAA_M3_TST_002_FOUR_TRAINING_GOLDEN_"
            "CROSS_PLATFORM_EVIDENCE_V1"
        ),
        "task_id": "M3-TST-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "scope": windows.get("scope"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("check")
    check.add_argument("--evidence", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.mode == "check":
            payload = verify()
        else:
            payload = compare_evidence(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
        evidence = args.evidence
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_TST_002_FOUR_TRAINING_GOLDEN_EVIDENCE_V1",
            "task_id": "M3-TST-002",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
