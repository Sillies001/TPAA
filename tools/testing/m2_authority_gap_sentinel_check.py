#!/usr/bin/env python3
"""Executable sentinel for the adopted M2 Batch 2 C3 authority state."""

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
AUTHORITY = CANONICAL_ROOT / "M2_QA_SNS_AUTHORITY.json"
ALIGNMENT_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "m2"
    / "MA_M2_NOMINAL_V1"
    / "source"
    / "measurement-alignment.json"
)
ADOPTED_BASELINE_LOCK_SHA256 = (
    "d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d"
)
ADOPTED_AUTHORITY_SHA256 = (
    "1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3"
)
ADOPTED_PROFILE_SHA256 = (
    "904100e467f10e89aca1f06b1e9eeff86923121063ec9a41a2d73f84cc2400f1"
)
REQUIRED_PROFILE_FIELDS = (
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


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def verify() -> dict[str, object]:
    lock_path = BASELINE_ROOT / "BASELINE_LOCK.json"
    authority = _load(AUTHORITY)
    alignment = _load(ALIGNMENT_FIXTURE)

    qa1_raw = authority.get("qa_001_frame_convention")
    qa2_raw = authority.get("qa_002_uncertainty_contract")
    profile_raw = authority.get("reference_match_quality_profile")
    golden_raw = authority.get("golden_vectors")
    if not isinstance(qa1_raw, dict) or not isinstance(qa2_raw, dict):
        raise ValueError("C3 QA authority sections missing")
    if not isinstance(profile_raw, dict) or not isinstance(golden_raw, dict):
        raise ValueError("C3 profile/golden sections missing")

    qa1 = cast(dict[str, object], qa1_raw)
    qa2 = cast(dict[str, object], qa2_raw)
    profile = cast(dict[str, object], profile_raw)
    golden = cast(dict[str, object], golden_raw)
    qa1_golden = golden.get("qa_001")
    qa2_golden = golden.get("qa_002")
    if not isinstance(qa1_golden, dict) or not isinstance(qa2_golden, dict):
        raise ValueError("C3 discriminating Goldens missing")

    qa1_input = qa1_golden.get("input")
    qa2_expected = qa2_golden.get("expected")
    if not isinstance(qa1_input, dict) or not isinstance(qa2_expected, dict):
        raise ValueError("C3 Golden payload shape invalid")

    hash_payload = dict(profile)
    profile_hash = hash_payload.pop("profile_hash", None)
    hash_payload.pop("profile_hash_algorithm", None)
    hash_payload.pop("relationship_to_existing_profile_fields", None)

    legacy_profile = alignment.get("quality_profile")
    if not isinstance(legacy_profile, dict):
        raise ValueError("legacy alignment quality_profile missing")
    legacy_missing = sorted(set(REQUIRED_PROFILE_FIELDS) - set(legacy_profile))

    p_inputs_order = qa2.get("p_inputs_order")
    jacobian = qa2.get("relative_state_jacobian")
    if not isinstance(jacobian, dict):
        raise ValueError("C3 QA-002 jacobian authority missing")
    p_inputs = qa2_expected.get("p_inputs_m2")
    if not isinstance(p_inputs, list) or len(p_inputs) != 6:
        raise ValueError("C3 QA-002 Golden P_inputs missing")

    attitude_semantics_raw = qa1.get("own_attitude_quaternion_semantics")
    attitude_semantics = (
        cast(dict[str, object], attitude_semantics_raw)
        if isinstance(attitude_semantics_raw, dict)
        else {}
    )

    acceptance = {
        "adopted_baseline_lock_exact": _sha256(lock_path)
        == ADOPTED_BASELINE_LOCK_SHA256,
        "adopted_authority_artifact_exact": _sha256(AUTHORITY)
        == ADOPTED_AUTHORITY_SHA256,
        "authority_status_approved": (
            authority.get("status") == "APPROVED_BY_DELEGATED_OWNER_AUTHORITY"
        ),
        "qa1_quaternion_order_frozen": qa1.get("quaternion_element_order")
        == ["w", "x", "y", "z"],
        "qa1_rotation_direction_frozen": (
            attitude_semantics.get("source_frame") == "OWN_BODY_FRD"
            and attitude_semantics.get("destination_frame") == "ECEF"
        ),
        "qa1_nonidentity_golden_discriminating": (
            qa1_input.get("own_attitude_quat") != [1, 0, 0, 0]
            and qa1_input.get("sensor_boresight_quat") is not None
        ),
        "qa2_p_inputs_exact_6d": (
            qa2.get("p_inputs_dimension") == 6
            and isinstance(p_inputs_order, list)
            and len(p_inputs_order) == 6
        ),
        "qa2_jacobian_shape_exact": jacobian.get("shape") == [3, 6],
        "qa2_shared_time_cross_covariance_golden": (
            isinstance(p_inputs[1], list)
            and len(p_inputs[1]) == 6
            and p_inputs[1][4] != 0
        ),
        "profile_required_fields_complete": all(
            field in profile for field in REQUIRED_PROFILE_FIELDS
        ),
        "profile_hash_exact": (
            profile_hash == ADOPTED_PROFILE_SHA256
            and _canonical_hash(hash_payload) == ADOPTED_PROFILE_SHA256
        ),
        "legacy_fixture_stays_non_authoritative": legacy_missing
        == sorted(REQUIRED_PROFILE_FIELDS),
        "authority_resolution_ready": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    return {
        "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1",
        "tracking_issue": 97,
        "baseline_change_issue": 106,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "authority_resolution_ready": not failed,
        "task_complete": not failed,
        "blocked_tasks": [],
        "scope": {
            "semantic_decision_adopted": True,
            "authority_values_invented_by_implementation": False,
            "sentinel_only": True,
        },
        "logical_product": {
            "adopted_baseline_lock_sha256": _sha256(lock_path),
            "authority_artifact_sha256": _sha256(AUTHORITY),
            "authority_id": authority.get("authority_id"),
            "authority_version": authority.get("version"),
            "profile_id": profile.get("profile_id"),
            "profile_version": profile.get("profile_version"),
            "profile_hash": profile_hash,
            "legacy_profile_missing_fields": legacy_missing,
            "qa1_golden_case_id": qa1_golden.get("case_id"),
            "qa2_golden_case_id": qa2_golden.get("case_id"),
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
