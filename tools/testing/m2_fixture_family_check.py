#!/usr/bin/env python3
"""M2-DATA-005 governed fixture-family acceptance and cross-platform comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m2"
FAMILY_PATH = FIXTURE_ROOT / "M2_FIXTURE_FAMILY_V1.json"

EXPECTED_SCHEMA = "TPAA_M2_FIXTURE_FAMILY_V1"
EXPECTED_TASK_ID = "M2-DATA-005"
EXPECTED_TRACKING_ISSUE = 96
EXPECTED_FAMILY_ID = "M2_P1_FOUNDATION_DATA_WORLD_FIXTURES"
EXPECTED_FAMILY_VERSION = "1.0.0"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_CATEGORIES = {
    "NOMINAL",
    "WRAP_BOUNDARY",
    "GAP",
    "INSUFFICIENT",
    "INVALID",
    "WRONG_SENSOR_APPLICABILITY",
}
EXPECTED_PLATFORM_POLICY = {
    "host_path_in_logical_product": False,
    "source_bytes": "REPOSITORY_CONTROLLED_IDENTICAL_BYTES",
    "windows_linux_constraint": "SAME_MANIFEST_AND_INPUT_SHA256",
}


class M2FixtureFamilyError(RuntimeError):
    """Deterministic fail-closed fixture-family error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


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


def _load_json(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M2FixtureFamilyError("M2_FIXTURE_FAMILY_JSON_INVALID", str(exc)) from exc
    if not isinstance(raw, dict):
        raise M2FixtureFamilyError("M2_FIXTURE_FAMILY_JSON_INVALID", "root must be object")
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise M2FixtureFamilyError("M2_FIXTURE_FAMILY_INVALID", f"{field} must be object")
    return cast(dict[str, object], value)


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_INVALID",
            f"{field} must be non-empty string",
        )
    return value


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _execute_member(member: dict[str, object]) -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_ingest import (
        M2MissionSystemError,
        M2TimeAlignmentError,
        load_m2_measurement_alignment,
        load_m2_mission_system,
        load_m2_reference_truth,
        load_m2_time_alignment,
    )

    fixture_id = _string(member.get("fixture_id"), field="member.fixture_id")
    loader_name = _string(member.get("loader"), field=f"{fixture_id}.loader")
    fixture_dir = FIXTURE_ROOT / fixture_id
    fixture_manifest = _load_json(fixture_dir / "manifest.json")
    if fixture_manifest.get("fixture_id") != fixture_id:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_MEMBER_ID_MISMATCH",
            fixture_id,
        )

    expected_input = _string(member.get("input_sha256"), field=f"{fixture_id}.input_sha256")
    manifest_input = _string(
        fixture_manifest.get("input_sha256"),
        field=f"{fixture_id}.manifest.input_sha256",
    )
    if manifest_input != expected_input:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_MEMBER_HASH_MISMATCH",
            f"{fixture_id} family={expected_input} manifest={manifest_input}",
        )

    positive_loaders: dict[str, Callable[[Path], Any]] = {
        "REFERENCE_TRUTH": load_m2_reference_truth,
        "TIME_ALIGNMENT": load_m2_time_alignment,
        "MISSION_SYSTEM": load_m2_mission_system,
        "MEASUREMENT_ALIGNMENT": load_m2_measurement_alignment,
    }
    if loader_name not in positive_loaders:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_LOADER_UNSUPPORTED",
            f"{fixture_id} loader={loader_name}",
        )
    loader = positive_loaders[loader_name]
    expected_error = member.get("expected_error_code")

    if expected_error is not None:
        expected_code = _string(expected_error, field=f"{fixture_id}.expected_error_code")
        try:
            loader(fixture_dir)
        except (M2TimeAlignmentError, M2MissionSystemError) as exc:
            if exc.code != expected_code:
                raise M2FixtureFamilyError(
                    "M2_FIXTURE_FAMILY_ERROR_CODE_MISMATCH",
                    f"{fixture_id} expected={expected_code} actual={exc.code}",
                ) from exc
            return {
                "fixture_id": fixture_id,
                "category": member["category"],
                "loader": loader_name,
                "input_sha256": expected_input,
                "outcome": "EXPECTED_ERROR",
                "error_code": exc.code,
            }
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_EXPECTED_ERROR_NOT_RAISED",
            f"{fixture_id} expected={expected_code}",
        )

    first = loader(fixture_dir)
    second = loader(fixture_dir)
    first_hash = getattr(first, "logical_hash", None)
    second_hash = getattr(second, "logical_hash", None)
    if not isinstance(first_hash, str) or len(first_hash) != 64 or first_hash != second_hash:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_REPLAY_UNSTABLE",
            fixture_id,
        )

    expected_status = member.get("expected_status")
    actual_status = getattr(first, "status", "PASS")
    if expected_status is not None and actual_status != expected_status:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_STATUS_MISMATCH",
            f"{fixture_id} expected={expected_status} actual={actual_status}",
        )

    expected_reasons = member.get("expected_reason_codes")
    actual_reasons = tuple(getattr(first, "reason_codes", ()))
    if expected_reasons is not None:
        if not isinstance(expected_reasons, list) or not all(
            isinstance(item, str) for item in expected_reasons
        ):
            raise M2FixtureFamilyError(
                "M2_FIXTURE_FAMILY_INVALID",
                f"{fixture_id}.expected_reason_codes",
            )
        if tuple(expected_reasons) != actual_reasons:
            raise M2FixtureFamilyError(
                "M2_FIXTURE_FAMILY_REASON_CODES_MISMATCH",
                f"{fixture_id} expected={expected_reasons} actual={actual_reasons}",
            )

    return {
        "fixture_id": fixture_id,
        "category": member["category"],
        "loader": loader_name,
        "input_sha256": expected_input,
        "outcome": "PROJECTED",
        "status": actual_status,
        "reason_codes": list(actual_reasons),
        "logical_hash": first_hash,
        "replay_stable": True,
    }


def verify() -> dict[str, object]:
    family = _load_json(FAMILY_PATH)
    if family.get("schema") != EXPECTED_SCHEMA:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_SCHEMA_MISMATCH",
            repr(family.get("schema")),
        )
    if family.get("task_id") != EXPECTED_TASK_ID:
        raise M2FixtureFamilyError("M2_FIXTURE_FAMILY_TASK_MISMATCH", repr(family.get("task_id")))
    if family.get("tracking_issue") != EXPECTED_TRACKING_ISSUE:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_TRACKING_MISMATCH",
            repr(family.get("tracking_issue")),
        )
    if family.get("family_id") != EXPECTED_FAMILY_ID:
        raise M2FixtureFamilyError("M2_FIXTURE_FAMILY_ID_MISMATCH", repr(family.get("family_id")))
    if family.get("family_version") != EXPECTED_FAMILY_VERSION:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_VERSION_MISMATCH",
            repr(family.get("family_version")),
        )
    if family.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_CLASSIFICATION_MISMATCH",
            repr(family.get("data_classification")),
        )
    if family.get("platform_policy") != EXPECTED_PLATFORM_POLICY:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_PLATFORM_POLICY_MISMATCH",
            repr(family.get("platform_policy")),
        )

    required_categories = family.get("required_categories")
    if not isinstance(required_categories, list) or set(required_categories) != EXPECTED_CATEGORIES:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_CATEGORY_CONTRACT_MISMATCH",
            repr(required_categories),
        )

    raw_members = family.get("members")
    if not isinstance(raw_members, list) or not raw_members:
        raise M2FixtureFamilyError("M2_FIXTURE_FAMILY_INVALID", "members must be non-empty list")
    members = [_object(item, field="members[]") for item in raw_members]
    fixture_ids = [_string(item.get("fixture_id"), field="member.fixture_id") for item in members]
    if len(fixture_ids) != len(set(fixture_ids)):
        raise M2FixtureFamilyError("M2_FIXTURE_FAMILY_DUPLICATE_MEMBER", repr(fixture_ids))

    observed_categories = {_string(item.get("category"), field="member.category") for item in members}
    if not EXPECTED_CATEGORIES <= observed_categories:
        raise M2FixtureFamilyError(
            "M2_FIXTURE_FAMILY_CATEGORY_COVERAGE_INCOMPLETE",
            repr(sorted(observed_categories)),
        )

    results = [_execute_member(member) for member in members]
    logical_product = {
        "schema": EXPECTED_SCHEMA,
        "task_id": EXPECTED_TASK_ID,
        "family_id": EXPECTED_FAMILY_ID,
        "family_version": EXPECTED_FAMILY_VERSION,
        "platform_policy": EXPECTED_PLATFORM_POLICY,
        "required_categories": sorted(EXPECTED_CATEGORIES),
        "members": results,
    }
    family_file_sha256 = hashlib.sha256(FAMILY_PATH.read_bytes()).hexdigest()
    logical_hash = _canonical_hash(logical_product)
    acceptance = {
        "family_manifest_valid": True,
        "fixture_ids_unique": True,
        "required_categories_complete": True,
        "member_manifest_hashes_exact": True,
        "nominal_and_boundary_execute": True,
        "gap_and_insufficient_execute": True,
        "invalid_fails_closed": True,
        "wrong_sensor_fails_closed": True,
        "replay_stable": True,
        "platform_policy_exact": True,
        "host_path_excluded_from_logical_product": True,
    }
    return {
        "schema": "TPAA_M2_DATA_005_FIXTURE_FAMILY_EVIDENCE_V1",
        "task_id": EXPECTED_TASK_ID,
        "tracking_issue": EXPECTED_TRACKING_ISSUE,
        "status": "PASS",
        "source_revision": _git_revision(),
        "fixture_family_file_sha256": family_file_sha256,
        "fixture_family_logical_hash": logical_hash,
        "member_count": len(results),
        "required_categories": sorted(EXPECTED_CATEGORIES),
        "platform_policy": EXPECTED_PLATFORM_POLICY,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": [],
    }


def compare_evidence(windows: Path, linux: Path, *, expected_revision: str) -> dict[str, object]:
    left = _load_json(windows)
    right = _load_json(linux)
    checks = {
        "windows_status_pass": left.get("status") == "PASS",
        "linux_status_pass": right.get("status") == "PASS",
        "windows_revision_exact": left.get("source_revision") == expected_revision,
        "linux_revision_exact": right.get("source_revision") == expected_revision,
        "family_file_sha256_equal": left.get("fixture_family_file_sha256")
        == right.get("fixture_family_file_sha256"),
        "family_logical_hash_equal": left.get("fixture_family_logical_hash")
        == right.get("fixture_family_logical_hash"),
        "logical_product_equal": left.get("logical_product") == right.get("logical_product"),
        "host_path_absent": "host_path" not in json.dumps(left.get("logical_product")),
    }
    failed = sorted(key for key, value in checks.items() if not value)
    return {
        "schema": "TPAA_M2_DATA_005_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": EXPECTED_TASK_ID,
        "status": "PASS" if not failed else "FAIL",
        "expected_revision": expected_revision,
        "checks": checks,
        "failed_acceptance": failed,
        "fixture_family_file_sha256": left.get("fixture_family_file_sha256"),
        "fixture_family_logical_hash": left.get("fixture_family_logical_hash"),
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
    compare.add_argument("--evidence", type=Path)
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
            "schema": "TPAA_M2_DATA_005_FIXTURE_FAMILY_EVIDENCE_V1",
            "task_id": EXPECTED_TASK_ID,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
