#!/usr/bin/env python3
"""Formal M2-TST-002 QA/AIR Golden and negative-suite evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]

QA_GOLDEN_CHECKS = (
    "qa_001_c3_nonidentity_golden_exact",
    "qa_002_c3_nondegenerate_golden_exact",
    "qa_003_segment_boundary_golden",
    "qa_004_latency_golden",
    "qa_005_interpolation_golden",
    "qa_006_structured_formula_golden",
    "qa_007_time_uncertainty_golden",
    "qa_008_time_uncertainty_golden",
)
QA_NEGATIVE_CHECKS = (
    "qa_001_zero_norm_fail_closed",
    "qa_002_wrong_jacobian_fail_closed",
)
AIR_GOLDEN_CHECKS = (
    "air_001_nominal_golden",
    "air_001_stage_boundary_exact",
    "air_002_primary_and_diagnostic_exact",
    "air_003_nominal_derivative_exact",
    "air_003_angle_unwrap_golden",
    "air_003_gap_not_bridged",
)
AIR_NEGATIVE_CHECKS = (
    "air_001_gap_fails_closed",
    "air_003_insufficient_window_fails_closed",
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


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _checks_exact(
    acceptance: dict[str, object],
    names: tuple[str, ...],
) -> bool:
    return all(acceptance.get(name) is True for name in names)


def verify() -> dict[str, object]:
    from tools.testing.m2_air_formal_delivery_check import verify as air_verify
    from tools.testing.m2_qa_foundation_incremental_check import (
        verify as qa_verify,
    )

    qa = qa_verify()
    air = air_verify()
    qa_acceptance = _mapping(qa.get("acceptance"), field="qa.acceptance")
    air_acceptance = _mapping(air.get("acceptance"), field="air.acceptance")
    qa_product = _mapping(qa.get("logical_product"), field="qa.logical_product")
    air_product = _mapping(
        air.get("logical_product"),
        field="air.logical_product",
    )
    qa_codes = qa_product.get("engine_metric_codes")
    air_codes = air_product.get("delivery_membership")
    revision = _git_revision()

    acceptance = {
        "qa_source_evidence_pass": (
            qa.get("status") == "PASS"
            and qa.get("task_complete") is True
            and qa.get("failed_acceptance") == []
            and all(value is True for value in qa_acceptance.values())
        ),
        "air_source_evidence_pass": (
            air.get("status") == "PASS"
            and air.get("task_complete") is True
            and air.get("failed_acceptance") == []
            and all(value is True for value in air_acceptance.values())
        ),
        "source_revisions_exact": (
            qa.get("source_revision")
            == air.get("source_revision")
            == revision
        ),
        "qa_golden_suite_exact_8": (
            len(QA_GOLDEN_CHECKS) == 8
            and _checks_exact(qa_acceptance, QA_GOLDEN_CHECKS)
        ),
        "qa_negative_suite_fail_closed": _checks_exact(
            qa_acceptance,
            QA_NEGATIVE_CHECKS,
        ),
        "air_golden_suite_complete": _checks_exact(
            air_acceptance,
            AIR_GOLDEN_CHECKS,
        ),
        "air_negative_suite_fail_closed": _checks_exact(
            air_acceptance,
            AIR_NEGATIVE_CHECKS,
        ),
        "qa_membership_exact_8": (
            isinstance(qa_codes, list)
            and len(qa_codes) == 8
            and set(qa_codes) == {f"P1-QA-{index:03d}" for index in range(1, 9)}
        ),
        "air_membership_exact_3": (
            air_codes == ["P1-AIR-001", "P1-AIR-002", "P1-AIR-003"]
        ),
        "combined_qa_air_membership_exact_11": (
            isinstance(qa_codes, list)
            and isinstance(air_codes, list)
            and len(set(qa_codes) | set(air_codes)) == 11
            and set(qa_codes).isdisjoint(air_codes)
        ),
        "qa_world_inputs_bound": (
            qa_acceptance.get("world_inputs_bound") is True
        ),
        "air_release_replay_exact": (
            air_acceptance.get("release_bound_replay_exact_no_latest") is True
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed
    return {
        "schema": "TPAA_M2_TST_002_QA_AIR_GOLDEN_NEGATIVE_EVIDENCE_V1",
        "task_id": "M2-TST-002",
        "tracking_issue": 99,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": revision,
        "logical_product": {
            "qa_source_schema": qa.get("schema"),
            "air_source_schema": air.get("schema"),
            "qa_metric_codes": qa_codes,
            "air_metric_codes": air_codes,
            "qa_logical_product_hash": _canonical_hash(qa_product),
            "air_logical_product_hash": _canonical_hash(air_product),
            "qa_golden_checks": list(QA_GOLDEN_CHECKS),
            "qa_negative_checks": list(QA_NEGATIVE_CHECKS),
            "air_golden_checks": list(AIR_GOLDEN_CHECKS),
            "air_negative_checks": list(AIR_NEGATIVE_CHECKS),
            "qa_acceptance_count": len(qa_acceptance),
            "air_acceptance_count": len(air_acceptance),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "qa_air_golden_negative_qualification_only": True,
            "business_metric_semantics_executed": True,
            "qa_foundation_8_executed": True,
            "air_foundation_3_executed": True,
            "sns_metric_semantics_executed": False,
            "p1_remainder_84_executed": False,
            "database_persistence_executed": False,
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
            "schema": "TPAA_M2_TST_002_QA_AIR_GOLDEN_NEGATIVE_EVIDENCE_V1",
            "task_id": "M2-TST-002",
            "tracking_issue": 99,
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
