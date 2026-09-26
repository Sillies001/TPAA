#!/usr/bin/env python3
"""Executable sentinel for the audited M2 Batch 2 C3 authority-gap state.

PASS means the current frozen authority still matches the conditions audited
into Baseline Change #106, so blocked Metric tasks must remain fail-closed.
Any authority or discriminating-fixture change intentionally invalidates this
sentinel and requires a new governed closure review before consumers change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0"
CANONICAL_ROOT = BASELINE_ROOT / "canonical"
REFERENCE_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "m2"
    / "RT_M2_NOMINAL_V1"
    / "source"
    / "reference-truth.json"
)
ALIGNMENT_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "m2"
    / "MA_M2_NOMINAL_V1"
    / "source"
    / "measurement-alignment.json"
)

AUDITED_BASELINE_LOCK_SHA256 = (
    "9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa"
)
EXPECTED_QA2_UNCERTAINTY_INPUTS = (
    "own_position_uncertainty_ref",
    "target_position_uncertainty_ref",
    "own_attitude_uncertainty_ref",
    "target_attitude_uncertainty_ref",
    "time_alignment_uncertainty_ref",
)
EXPECTED_PROFILE_MISSING_FIELDS = (
    "accepted_reference_quality_statuses",
    "max_interpolation_age_us",
    "max_sigma_by_error_domain",
    "na_reason_map",
    "required_uncertainty_components",
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], value)


def _metric(catalog: dict[str, object], code: str) -> dict[str, object]:
    raw = catalog.get("metrics")
    if not isinstance(raw, list):
        raise ValueError("catalog.metrics must be list")
    matches = [
        item
        for item in raw
        if isinstance(item, dict) and item.get("metric_code") == code
    ]
    if len(matches) != 1:
        raise ValueError(f"{code}: expected exactly one Catalog definition")
    return cast(dict[str, object], matches[0])


def _matrix_shape(value: object) -> tuple[int, int] | None:
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(row, list) for row in value):
        return None
    rows = cast(list[list[object]], value)
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        return None
    return len(rows), widths.pop()


def verify() -> dict[str, object]:
    catalog_path = CANONICAL_ROOT / "P1_METRIC_CATALOG.json"
    matrix_path = CANONICAL_ROOT / "METRIC_INPUT_AUTHORITY_MATRIX.json"
    provenance_path = CANONICAL_ROOT / "SOURCE_PROVENANCE.json"
    lock_path = BASELINE_ROOT / "BASELINE_LOCK.json"

    catalog = _load(catalog_path)
    reference_fixture = _load(REFERENCE_FIXTURE)
    alignment_fixture = _load(ALIGNMENT_FIXTURE)

    qa1 = _metric(catalog, "P1-QA-001")
    qa2 = _metric(catalog, "P1-QA-002")

    qa1_records = reference_fixture.get("records")
    if not isinstance(qa1_records, list) or not qa1_records:
        raise ValueError("reference fixture records missing")

    own_quaternions: list[object] = []
    boresights: list[object] = []
    jacobian_shapes: list[tuple[int, int] | None] = []
    for raw_record in qa1_records:
        if not isinstance(raw_record, dict):
            raise ValueError("reference fixture record must be object")
        own = raw_record.get("own")
        if not isinstance(own, dict):
            raise ValueError("reference fixture own must be object")
        own_quaternions.append(own.get("attitude_quat"))
        boresights.append(raw_record.get("sensor_boresight_quat"))
        jacobian_shapes.append(_matrix_shape(raw_record.get("relative_state_jacobian")))

    identity_quaternion = [1, 0, 0, 0]
    qa1_fixture_non_discriminating = (
        all(value == identity_quaternion for value in own_quaternions)
        and all(value is None for value in boresights)
    )

    qa2_inputs_raw = qa2.get("input_fields")
    if not isinstance(qa2_inputs_raw, list) or not all(
        isinstance(item, str) for item in qa2_inputs_raw
    ):
        raise ValueError("P1-QA-002 input_fields invalid")
    qa2_inputs = cast(list[str], qa2_inputs_raw)
    qa2_uncertainty_inputs = tuple(
        field for field in qa2_inputs if field.endswith("_uncertainty_ref")
    )
    qa2_current_shape_is_3x6 = (
        bool(jacobian_shapes)
        and all(shape == (3, 6) for shape in jacobian_shapes)
    )

    profile_registry = catalog.get("reference_match_quality_profile_registry")
    if not isinstance(profile_registry, dict):
        raise ValueError("reference_match_quality_profile_registry missing")
    contract = profile_registry.get("CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1")
    if not isinstance(contract, dict):
        raise ValueError("CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 missing")
    required_raw = contract.get("required_instance_fields")
    if not isinstance(required_raw, list) or not all(
        isinstance(item, str) for item in required_raw
    ):
        raise ValueError("required_instance_fields invalid")
    required_fields = set(cast(list[str], required_raw))

    profile = alignment_fixture.get("quality_profile")
    if not isinstance(profile, dict) or not all(
        isinstance(key, str) for key in profile
    ):
        raise ValueError("alignment fixture quality_profile invalid")
    profile_keys = set(cast(dict[str, object], profile))
    missing_profile_fields = tuple(sorted(required_fields - profile_keys))

    current_hashes = {
        "BASELINE_LOCK.json": _sha256(lock_path),
        "P1_METRIC_CATALOG.json": _sha256(catalog_path),
        "METRIC_INPUT_AUTHORITY_MATRIX.json": _sha256(matrix_path),
        "SOURCE_PROVENANCE.json": _sha256(provenance_path),
        "RT_M2_NOMINAL_V1/reference-truth.json": _sha256(REFERENCE_FIXTURE),
        "MA_M2_NOMINAL_V1/measurement-alignment.json": _sha256(ALIGNMENT_FIXTURE),
    }

    acceptance = {
        "audited_baseline_lock_unchanged": (
            current_hashes["BASELINE_LOCK.json"]
            == AUDITED_BASELINE_LOCK_SHA256
        ),
        "qa1_formula_still_requires_body_transform": (
            isinstance(qa1.get("formula"), str)
            and "Transform r_rel into own-body" in cast(str, qa1["formula"])
        ),
        "qa1_fixture_still_non_discriminating": qa1_fixture_non_discriminating,
        "qa2_uncertainty_inputs_exact_five": (
            qa2_uncertainty_inputs == EXPECTED_QA2_UNCERTAINTY_INPUTS
        ),
        "qa2_fixture_jacobian_shape_still_3x6": qa2_current_shape_is_3x6,
        "profile_required_fields_still_missing_exact_five": (
            missing_profile_fields == EXPECTED_PROFILE_MISSING_FIELDS
        ),
        "formal_tasks_remain_non_completing": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    return {
        "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1",
        "tracking_issue": 97,
        "baseline_change_issue": 106,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "authority_resolution_ready": False,
        "task_complete": False,
        "blocked_tasks": [
            "M2-MET-002",
            "M2-MET-005",
            "M2-MET-006",
            "M2-MET-007",
        ],
        "scope": {
            "semantic_decision_made": False,
            "authority_values_invented": False,
            "sentinel_only": True,
        },
        "logical_product": {
            "audited_baseline_lock_sha256": AUDITED_BASELINE_LOCK_SHA256,
            "current_hashes": current_hashes,
            "qa1_fixture_non_discriminating": qa1_fixture_non_discriminating,
            "qa2_uncertainty_inputs": list(qa2_uncertainty_inputs),
            "qa2_jacobian_shapes": [
                None if shape is None else list(shape)
                for shape in jacobian_shapes
            ],
            "profile_required_fields": sorted(required_fields),
            "profile_present_fields": sorted(profile_keys),
            "profile_missing_fields": list(missing_profile_fields),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
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
            "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1",
            "tracking_issue": 97,
            "baseline_change_issue": 106,
            "status": "FAIL",
            "authority_resolution_ready": False,
            "task_complete": False,
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
