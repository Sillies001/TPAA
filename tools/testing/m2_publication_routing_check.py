#!/usr/bin/env python3
"""Formal M2-OBS-001 publication lane/route evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"


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

    from tpaa_metric import build_m2_metric_execution_plan
    from tpaa_observation import build_m2_publication_routing_plan

    metric_plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    plan = build_m2_publication_routing_plan(AUTHORITY_ROOT)
    replay = build_m2_publication_routing_plan(AUTHORITY_ROOT)
    target_by_code = {target.metric_code: target for target in plan.targets}
    definition_by_code = {
        definition.metric_code: definition
        for definition in metric_plan.definitions
    }

    capability_codes = {
        "P1-AIR-001",
        "P1-AIR-002",
        "P1-AIR-003",
    }
    evidence_only_codes = {
        "P1-QA-001",
        "P1-QA-002",
        "P1-QA-005",
        "P1-QA-007",
        "P1-QA-008",
    }
    system_codes = {
        "P1-QA-003",
        "P1-QA-004",
        "P1-QA-006",
        *(f"P1-SNS-{index:03d}" for index in range(1, 22)),
    }

    route_counts = dict(
        sorted(Counter(target.publication_route for target in plan.targets).items())
    )
    lane_counts = dict(
        sorted(Counter(target.observation_lane for target in plan.targets).items())
    )

    unknown_route = _error_code(
        replace(
            definition_by_code["P1-QA-001"],
            publication_route="UNKNOWN_ROUTE",
        )
    )
    lane_mismatch = _error_code(
        replace(
            definition_by_code["P1-AIR-001"],
            observation_lane="QUALITY_EVIDENCE_ONLY",
        )
    )
    subject_mismatch = _error_code(
        replace(
            definition_by_code["P1-AIR-001"],
            subject_type="TARGET_PAIR",
        )
    )
    quality_trend = _error_code(
        replace(
            definition_by_code["P1-QA-001"],
            p1_longitudinal_trend_eligibility=True,
        )
    )

    acceptance = {
        "foundation_membership_exact_32": (
            len(plan.targets) == 32
            and plan.metric_codes == metric_plan.metric_codes
            and set(plan.metric_codes) == set(metric_plan.catalog_metric_codes)
        ),
        "catalog_identity_bound": (
            plan.catalog_id == metric_plan.catalog_id
            and plan.catalog_version == metric_plan.catalog_version
            and plan.catalog_hash == metric_plan.catalog_sha256
            and plan.metric_execution_plan_hash == metric_plan.logical_hash
        ),
        "catalog_owned_routing_metadata_exact_32": all(
            target.subject_type == definition_by_code[target.metric_code].subject_type
            and target.observation_lane
            == definition_by_code[target.metric_code].observation_lane
            and target.publication_route
            == definition_by_code[target.metric_code].publication_route
            and target.definition_hash
            == definition_by_code[target.metric_code].definition_hash
            for target in plan.targets
        ),
        "publication_route_counts_exact": route_counts
        == {
            "CAPABILITY_OBSERVATION": 3,
            "METRIC_INSTANCE_EVIDENCE_ONLY": 5,
            "SYSTEM_PERFORMANCE_OBSERVATION": 24,
        },
        "observation_lane_counts_exact": lane_counts
        == {
            "AIRCRAFT_CAP_L1_OBSERVATION": 3,
            "QUALITY_EVIDENCE_ONLY": 5,
            "SYSTEM_PERFORMANCE_OBSERVATION": 24,
        },
        "capability_route_codes_exact": {
            code
            for code, target in target_by_code.items()
            if target.publication_route == "CAPABILITY_OBSERVATION"
        }
        == capability_codes,
        "system_performance_route_codes_exact": {
            code
            for code, target in target_by_code.items()
            if target.publication_route == "SYSTEM_PERFORMANCE_OBSERVATION"
        }
        == system_codes,
        "evidence_only_route_codes_exact": {
            code
            for code, target in target_by_code.items()
            if target.publication_route == "METRIC_INSTANCE_EVIDENCE_ONLY"
        }
        == evidence_only_codes,
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
        "metric_instance_and_evidence_persist_for_all_32": all(
            target.persist_metric_instance and target.persist_evidence_set
            for target in plan.targets
        ),
        "definition_hashes_bound_exact_32": all(
            len(target.definition_hash) == 64 for target in plan.targets
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
        "quality_longitudinal_route_fails_closed": (
            quality_trend == "M2_PUBLICATION_QUALITY_TREND_FORBIDDEN"
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    logical_product = {
        "catalog_id": plan.catalog_id,
        "catalog_version": plan.catalog_version,
        "catalog_hash": plan.catalog_hash,
        "metric_execution_plan_hash": plan.metric_execution_plan_hash,
        "publication_routing_plan_hash": plan.logical_hash,
        "metric_codes": list(plan.metric_codes),
        "route_counts": route_counts,
        "lane_counts": lane_counts,
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
            "quality_longitudinal": quality_trend,
        },
    }
    return {
        "schema": "TPAA_M2_OBS_001_PUBLICATION_ROUTING_EVIDENCE_V1",
        "task_id": "M2-OBS-001",
        "tracking_issue": 98,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
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
            "gui_rendering_executed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_OBS_001_PUBLICATION_ROUTING_EVIDENCE_V1",
            "task_id": "M2-OBS-001",
            "tracking_issue": 98,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
