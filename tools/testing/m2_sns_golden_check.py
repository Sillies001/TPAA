#!/usr/bin/env python3
"""Formal M2-TST-003 SNS Golden/applicability qualification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]

DETECTION_GOLDEN_CHECKS = (
    "sns001_planned_off_coverage_golden",
    "sns002_ten_eight_invalid_excluded_golden",
    "sns003_first_detection_3_2s_golden",
    "sns004_linear_range_golden",
)
DETECTION_NEGATIVE_CHECKS = (
    "sns003_missing_detection_na",
    "sns004_gap_not_bridged",
)
ACCURACY_GOLDEN_CHECKS = (
    "constant_50m_and_vector_golden",
    "discriminating_aggregation_golden_exact_17",
    "wrap_boundary_golden",
)
ACCURACY_QUALITY_CHECKS = (
    "quality_rejections_never_enter_statistics",
    "full_profile_rejection_reason_surface_exact",
    "rejected_samples_excluded_from_statistics",
    "empty_sample_set_uses_profile_reason",
)
APPLICABILITY_CHECKS = (
    "radar_applicability_exact",
    "non_radar_emits_no_fake_observation",
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
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _all_true(source: dict[str, object], names: tuple[str, ...]) -> bool:
    return all(source.get(name) is True for name in names)


def verify() -> dict[str, object]:
    from tools.testing.m2_sns_accuracy_incremental_check import (
        verify as accuracy_verify,
    )
    from tools.testing.m2_sns_detection_check import verify as detection_verify

    detection = detection_verify()
    accuracy = accuracy_verify()
    detection_acceptance = _mapping(
        detection.get("acceptance"),
        field="detection.acceptance",
    )
    accuracy_acceptance = _mapping(
        accuracy.get("acceptance"),
        field="accuracy.acceptance",
    )
    detection_product = _mapping(
        detection.get("logical_product"),
        field="detection.logical_product",
    )
    accuracy_product = _mapping(
        accuracy.get("logical_product"),
        field="accuracy.logical_product",
    )
    detection_codes = detection_product.get("delivery_membership")
    accuracy_codes = accuracy_product.get("delivery_membership")
    revision = _git_revision()

    acceptance = {
        "detection_source_evidence_pass": (
            detection.get("status") == "PASS"
            and detection.get("task_complete") is True
            and detection.get("failed_acceptance") == []
            and all(value is True for value in detection_acceptance.values())
        ),
        "accuracy_source_evidence_pass": (
            accuracy.get("status") == "PASS"
            and accuracy.get("task_complete") is True
            and accuracy.get("implementation_complete") is True
            and accuracy.get("failed_acceptance") == []
            and all(value is True for value in accuracy_acceptance.values())
        ),
        "source_revisions_exact": (
            detection.get("source_revision")
            == accuracy.get("source_revision")
            == revision
        ),
        "sns_detection_membership_exact_4": (
            detection_codes
            == ["P1-SNS-001", "P1-SNS-002", "P1-SNS-003", "P1-SNS-004"]
        ),
        "sns_accuracy_membership_exact_17": (
            isinstance(accuracy_codes, list)
            and len(accuracy_codes) == 17
            and accuracy_codes[0] == "P1-SNS-005"
            and accuracy_codes[-1] == "P1-SNS-021"
        ),
        "sns_combined_membership_exact_21": (
            isinstance(detection_codes, list)
            and isinstance(accuracy_codes, list)
            and len(set(detection_codes) | set(accuracy_codes)) == 21
            and set(detection_codes).isdisjoint(accuracy_codes)
        ),
        "detection_golden_suite_exact": _all_true(
            detection_acceptance,
            DETECTION_GOLDEN_CHECKS,
        ),
        "detection_negative_suite_fail_closed": _all_true(
            detection_acceptance,
            DETECTION_NEGATIVE_CHECKS,
        ),
        "accuracy_golden_suite_exact": _all_true(
            accuracy_acceptance,
            ACCURACY_GOLDEN_CHECKS,
        ),
        "accuracy_quality_negative_suite_exact": _all_true(
            accuracy_acceptance,
            ACCURACY_QUALITY_CHECKS,
        ),
        "detection_applicability_exact": _all_true(
            detection_acceptance,
            APPLICABILITY_CHECKS,
        ),
        "accuracy_applicability_exact": _all_true(
            accuracy_acceptance,
            APPLICABILITY_CHECKS,
        ),
        "adopted_c3_profile_consumed_exact": (
            accuracy_acceptance.get("adopted_c3_profile_fixture_exact") is True
            and accuracy_acceptance.get(
                "adopted_c3_profile_consumed_by_world_adapter"
            )
            is True
            and accuracy_acceptance.get("adopted_c3_profile_outputs_valid_17")
            is True
        ),
        "sns_replay_exact": (
            detection_acceptance.get("replay_exact") is True
            and accuracy_acceptance.get("algorithm_replay_exact") is True
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed
    return {
        "schema": "TPAA_M2_TST_003_SNS_GOLDEN_APPLICABILITY_EVIDENCE_V1",
        "task_id": "M2-TST-003",
        "tracking_issue": 99,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": revision,
        "logical_product": {
            "detection_source_schema": detection.get("schema"),
            "accuracy_source_schema": accuracy.get("schema"),
            "detection_metric_codes": detection_codes,
            "accuracy_metric_codes": accuracy_codes,
            "detection_logical_product_hash": _hash(detection_product),
            "accuracy_logical_product_hash": _hash(accuracy_product),
            "detection_golden_checks": list(DETECTION_GOLDEN_CHECKS),
            "detection_negative_checks": list(DETECTION_NEGATIVE_CHECKS),
            "accuracy_golden_checks": list(ACCURACY_GOLDEN_CHECKS),
            "accuracy_quality_checks": list(ACCURACY_QUALITY_CHECKS),
            "applicability_checks": list(APPLICABILITY_CHECKS),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "sns_golden_applicability_qualification_only": True,
            "sns_detection_4_executed": True,
            "sns_accuracy_17_executed": True,
            "business_metric_semantics_executed": True,
            "non_radar_applicability_executed": True,
            "adopted_c3_profile_executed": True,
            "qa_air_business_semantics_executed_by_this_check": False,
            "p1_remainder_84_executed": False,
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
            "schema": "TPAA_M2_TST_003_SNS_GOLDEN_APPLICABILITY_EVIDENCE_V1",
            "task_id": "M2-TST-003",
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
