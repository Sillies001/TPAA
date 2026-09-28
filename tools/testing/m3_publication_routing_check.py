#!/usr/bin/env python3
"""M3-OBS-001 exact 116-metric publication lane/route qualification evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
TRACKING_ISSUE = 116

EXPECTED_CAPABILITY_CODES = {
    *(f"P1-AIR-{index:03d}" for index in range(1, 40)),
}
EXPECTED_EVIDENCE_ONLY_CODES = {
    "P1-QA-001",
    "P1-QA-002",
    "P1-QA-005",
    "P1-QA-007",
    "P1-QA-008",
}
EXPECTED_SYSTEM_CODES = {
    "P1-QA-003",
    "P1-QA-004",
    "P1-QA-006",
    *(f"P1-SNS-{index:03d}" for index in range(1, 22)),
    *(f"P1-TRK-{index:03d}" for index in range(1, 8)),
    *(f"P1-ID-{index:03d}" for index in range(1, 13)),
    *(f"P1-PSV-{index:03d}" for index in range(1, 8)),
    *(f"P1-ESM-{index:03d}" for index in range(1, 7)),
    *(f"P1-DL-{index:03d}" for index in range(1, 9)),
    *(f"P1-FUS-{index:03d}" for index in range(1, 9)),
}
EXPECTED_REMAINDER_CAPABILITY_CODES = {
    *(f"P1-AIR-{index:03d}" for index in range(4, 40)),
}
EXPECTED_REMAINDER_SYSTEM_CODES = (
    EXPECTED_SYSTEM_CODES
    - {
        "P1-QA-003",
        "P1-QA-004",
        "P1-QA-006",
        *(f"P1-SNS-{index:03d}" for index in range(1, 22)),
    }
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


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], raw)


def _error_code(definition: object) -> str:
    from tpaa_observation import (
        M2PublicationRoutingError,
        route_m2_metric_definition,
    )

    try:
        route_m2_metric_definition(definition)  # type: ignore[arg-type]
    except M2PublicationRoutingError as exc:
        return exc.code
    return "NO_ERROR"


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        build_m2_metric_execution_plan,
        build_m3_metric_execution_plan,
    )
    from tpaa_observation import (
        M3_PUBLICATION_LANE_COUNTS,
        M3_PUBLICATION_ROUTE_COUNTS,
        build_m2_publication_routing_plan,
        build_m3_publication_routing_plan,
    )

    metric_plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    foundation_metric_plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    foundation_plan = build_m2_publication_routing_plan(AUTHORITY_ROOT)
    plan = build_m3_publication_routing_plan(AUTHORITY_ROOT)
    replay = build_m3_publication_routing_plan(AUTHORITY_ROOT)

    target_by_code = {target.metric_code: target for target in plan.targets}
    definition_by_code = {
        definition.metric_code: definition
        for definition in metric_plan.definitions
    }
    foundation_target_by_code = {
        target.metric_code: target
        for target in foundation_plan.targets
    }
    foundation_codes = set(foundation_metric_plan.metric_codes)
    remainder_codes = set(metric_plan.metric_codes) - foundation_codes

    route_counts = dict(
        sorted(Counter(target.publication_route for target in plan.targets).items())
    )
    lane_counts = dict(
        sorted(Counter(target.observation_lane for target in plan.targets).items())
    )
    capability_codes = {
        code
        for code, target in target_by_code.items()
        if target.publication_route == "CAPABILITY_OBSERVATION"
    }
    evidence_only_codes = {
        code
        for code, target in target_by_code.items()
        if target.publication_route == "METRIC_INSTANCE_EVIDENCE_ONLY"
    }
    system_codes = {
        code
        for code, target in target_by_code.items()
        if target.publication_route == "SYSTEM_PERFORMANCE_OBSERVATION"
    }
    remainder_capability_codes = capability_codes & remainder_codes
    remainder_system_codes = system_codes & remainder_codes
    remainder_evidence_only_codes = evidence_only_codes & remainder_codes

    unknown_route = _error_code(
        replace(
            definition_by_code["P1-FUS-001"],
            publication_route="UNKNOWN_ROUTE",
        )
    )
    lane_mismatch = _error_code(
        replace(
            definition_by_code["P1-AIR-039"],
            observation_lane="SYSTEM_PERFORMANCE_OBSERVATION",
        )
    )
    subject_mismatch = _error_code(
        replace(
            definition_by_code["P1-DL-001"],
            subject_type="AIRCRAFT",
        )
    )

    acceptance = {
        "integrated_membership_exact_116": (
            len(plan.targets) == 116
            and len(set(plan.metric_codes)) == 116
            and plan.metric_codes == metric_plan.metric_codes
            and set(plan.metric_codes) == set(metric_plan.catalog_metric_codes)
        ),
        "catalog_identity_bound": (
            plan.catalog_id == metric_plan.catalog_id
            and plan.catalog_version == metric_plan.catalog_version
            and plan.catalog_hash == metric_plan.catalog_sha256
            and plan.metric_execution_plan_hash == metric_plan.logical_hash
        ),
        "catalog_owned_routing_metadata_exact_116": all(
            target.subject_type == definition_by_code[target.metric_code].subject_type
            and target.observation_lane
            == definition_by_code[target.metric_code].observation_lane
            and target.publication_route
            == definition_by_code[target.metric_code].publication_route
            and target.definition_hash
            == definition_by_code[target.metric_code].definition_hash
            for target in plan.targets
        ),
        "foundation_routes_preserved_exact_32": (
            len(foundation_target_by_code) == 32
            and plan.foundation_publication_routing_plan_hash
            == foundation_plan.logical_hash
            and all(
                target_by_code[code] == foundation_target_by_code[code]
                for code in foundation_target_by_code
            )
        ),
        "publication_route_counts_exact_39_5_72": (
            route_counts == dict(sorted(M3_PUBLICATION_ROUTE_COUNTS.items()))
            == {
                "CAPABILITY_OBSERVATION": 39,
                "METRIC_INSTANCE_EVIDENCE_ONLY": 5,
                "SYSTEM_PERFORMANCE_OBSERVATION": 72,
            }
        ),
        "observation_lane_counts_exact_39_5_72": (
            lane_counts == dict(sorted(M3_PUBLICATION_LANE_COUNTS.items()))
            == {
                "AIRCRAFT_CAP_L1_OBSERVATION": 39,
                "QUALITY_EVIDENCE_ONLY": 5,
                "SYSTEM_PERFORMANCE_OBSERVATION": 72,
            }
        ),
        "capability_route_codes_exact_39": (
            capability_codes == EXPECTED_CAPABILITY_CODES
        ),
        "evidence_only_route_codes_exact_5": (
            evidence_only_codes == EXPECTED_EVIDENCE_ONLY_CODES
        ),
        "system_performance_route_codes_exact_72": (
            system_codes == EXPECTED_SYSTEM_CODES
        ),
        "remainder_route_partition_exact_36_plus_48": (
            remainder_capability_codes == EXPECTED_REMAINDER_CAPABILITY_CODES
            and remainder_system_codes == EXPECTED_REMAINDER_SYSTEM_CODES
            and remainder_evidence_only_codes == set()
            and len(remainder_codes) == 84
        ),
        "capability_subject_contract_exact": all(
            target.subject_type == "AIRCRAFT"
            and target.observation_lane == "AIRCRAFT_CAP_L1_OBSERVATION"
            and target.observation_record_type == "CAPABILITY_OBSERVATION"
            for code, target in target_by_code.items()
            if code in capability_codes
        ),
        "system_subject_contract_exact": all(
            target.subject_type == "MISSION_SYSTEM_INSTANCE"
            and target.observation_lane == "SYSTEM_PERFORMANCE_OBSERVATION"
            and target.observation_record_type == "SYSTEM_PERFORMANCE_OBSERVATION"
            for code, target in target_by_code.items()
            if code in system_codes
        ),
        "quality_evidence_has_no_observation_record": all(
            target.observation_lane == "QUALITY_EVIDENCE_ONLY"
            and target.observation_record_type is None
            and not target.p1_longitudinal_trend_eligibility
            for code, target in target_by_code.items()
            if code in evidence_only_codes
        ),
        "metric_instance_and_evidence_persist_for_all_116": all(
            target.persist_metric_instance and target.persist_evidence_set
            for target in plan.targets
        ),
        "definition_hashes_bound_exact_116": all(
            len(target.definition_hash) == 64
            for target in plan.targets
        ),
        "routing_plan_hash_well_formed": len(plan.logical_hash) == 64,
        "routing_plan_replay_exact": replay == plan,
        "unknown_route_fails_closed": (
            unknown_route == "M2_PUBLICATION_ROUTE_UNKNOWN"
        ),
        "lane_mismatch_fails_closed": (
            lane_mismatch == "M2_PUBLICATION_LANE_MISMATCH"
        ),
        "subject_mismatch_fails_closed": (
            subject_mismatch == "M2_PUBLICATION_SUBJECT_MISMATCH"
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    logical_product = {
        "catalog_id": plan.catalog_id,
        "catalog_version": plan.catalog_version,
        "catalog_hash": plan.catalog_hash,
        "metric_execution_plan_hash": plan.metric_execution_plan_hash,
        "foundation_publication_routing_plan_hash": (
            plan.foundation_publication_routing_plan_hash
        ),
        "publication_routing_plan_hash": plan.logical_hash,
        "metric_codes": list(plan.metric_codes),
        "route_counts": route_counts,
        "lane_counts": lane_counts,
        "capability_codes": sorted(capability_codes),
        "evidence_only_codes": sorted(evidence_only_codes),
        "system_performance_codes": sorted(system_codes),
        "remainder_capability_codes": sorted(remainder_capability_codes),
        "remainder_system_performance_codes": sorted(remainder_system_codes),
        "targets": [
            {
                "metric_code": target.metric_code,
                "semantic_id": target.semantic_id,
                "semantic_version": target.semantic_version,
                "definition_hash": target.definition_hash,
                "subject_type": target.subject_type,
                "observation_lane": target.observation_lane,
                "publication_route": target.publication_route,
                "observation_record_type": target.observation_record_type,
                "p1_longitudinal_trend_eligibility": (
                    target.p1_longitudinal_trend_eligibility
                ),
                "persist_metric_instance": target.persist_metric_instance,
                "persist_evidence_set": target.persist_evidence_set,
            }
            for target in plan.targets
        ],
        "negative_error_codes": {
            "unknown_route": unknown_route,
            "lane_mismatch": lane_mismatch,
            "subject_mismatch": subject_mismatch,
        },
    }
    return {
        "schema": "TPAA_M3_OBS_001_PUBLICATION_ROUTING_EVIDENCE_V1",
        "task_id": "M3-OBS-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "catalog_owned_routing_only": True,
            "business_metric_semantics_executed": False,
            "metric_values_recomputed": False,
            "database_persistence_executed": False,
            "release_snapshot_created": False,
            "api_projection_executed": False,
            "gui_rendering_executed": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "windows_status_pass": windows.get("status") == "PASS",
        "linux_status_pass": linux.get("status") == "PASS",
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "windows_implementation_complete": (
            windows.get("implementation_complete") is True
        ),
        "linux_implementation_complete": linux.get("implementation_complete") is True,
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M3_OBS_001_PUBLICATION_ROUTING_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-OBS-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
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
            evidence = args.evidence
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
            "schema": "TPAA_M3_OBS_001_PUBLICATION_ROUTING_EVIDENCE_V1",
            "task_id": "M3-OBS-001",
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
