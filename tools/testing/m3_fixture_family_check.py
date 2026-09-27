#!/usr/bin/env python3
"""M3-WORLD-005 frozen four-training fixture-family qualification."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m3"
FAMILY_PATH = FIXTURE_ROOT / "M3_FIXTURE_FAMILY_V1.json"
APPLICABILITY_PATH = FIXTURE_ROOT / "M3_WORLD_004_MISSION_SYSTEMS_V1.json"

EXPECTED_SCHEMA = "TPAA_M3_FIXTURE_FAMILY_V1"
EXPECTED_TASK_ID = "M3-WORLD-005"
EXPECTED_TRACKING_ISSUE = 112
EXPECTED_FAMILY_ID = "M3_FOUR_TRAINING_WORLD_FIXTURES"
EXPECTED_FAMILY_VERSION = "1.0.0"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_HASH_POLICY = "SHA256_FROZEN_BASE_AND_CANONICAL_CASE_V1"
EXPECTED_TRAINING_TYPES = ("BASIC_FLIGHT", "WVR", "BVR", "STRIKE")
EXPECTED_CATEGORIES = (
    "NOMINAL",
    "BOUNDARY",
    "GAP",
    "INSUFFICIENT",
    "INVALID",
    "APPLICABILITY",
)
EXPECTED_PLATFORM_POLICY = {
    "host_path_in_logical_product": False,
    "source_bytes": "REPOSITORY_CONTROLLED_IDENTICAL_BYTES",
    "windows_linux_constraint": "SAME_MANIFEST_TRANSFORM_AND_INPUT_SHA256",
}
EXPECTED_TRAINING_CONTRACTS: dict[str, dict[str, str]] = {
    "BASIC_FLIGHT": {
        "base_fixture": "BASIC_M3_WORLD_005_BASE_V1.json",
        "episode_type": "BASIC_FLIGHT",
        "stage_profile_id": "BASIC_FLIGHT_V1",
        "world_capability_code": "BASIC_CORE",
    },
    "WVR": {
        "base_fixture": "WVR_M3_WORLD_005_BASE_V1.json",
        "episode_type": "WVR_ENGAGEMENT",
        "stage_profile_id": "WVR_ENGAGEMENT_V1",
        "world_capability_code": "WVR_CORE",
    },
    "BVR": {
        "base_fixture": "BVR_M3_WORLD_002_NOMINAL_V1.json",
        "episode_type": "BVR_KILL_CHAIN",
        "stage_profile_id": "BVR_KILL_CHAIN_V1",
        "world_capability_code": "BVR_PROCESS",
    },
    "STRIKE": {
        "base_fixture": "STRIKE_M3_WORLD_003_NOMINAL_V1.json",
        "episode_type": "STRIKE_MISSION",
        "stage_profile_id": "STRIKE_MISSION_V1",
        "world_capability_code": "STRIKE_CORE",
    },
}
EXPECTED_TRANSFORMS = {
    "NOMINAL": "IDENTITY_V1",
    "BOUNDARY": "NON_UNIFORM_BOUNDARY_V1",
    "GAP": "DECLARED_SOURCE_GAP_V1",
    "INSUFFICIENT": "DROP_REQUIRED_WORLD_V1",
    "INVALID": "CORRUPT_STAGE_ORDER_V1",
    "APPLICABILITY": "CATALOG_APPLICABILITY_MATRIX_V1",
}
EXPECTED_APPLICABILITY_FIXTURE = "M3_WORLD_004_MISSION_SYSTEMS_V1.json"

TRACK_ID = "61111111-1111-4111-8111-111111111111"
IRST = "62222222-2222-4222-8222-222222222222"
RWR = "64444444-4444-4444-8444-444444444444"
DL = "66666666-6666-4666-8666-666666666666"
FUS = "67777777-7777-4777-8777-777777777777"
RADAR = "68888888-8888-4888-8888-888888888888"


class M3FixtureFamilyError(RuntimeError):
    """Deterministic fail-closed M3 fixture-family qualification error."""

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


def _load(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_JSON_INVALID",
            f"{path.name}: {exc}",
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_JSON_INVALID",
            f"{path.name}: root must be string-keyed object",
        )
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_INVALID",
            f"{field} must be non-empty string",
        )
    return value


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_FILE_MISSING",
            path.name,
        ) from exc


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _render(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"


def _markers(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("official_stage_markers")
    if not isinstance(raw, list) or len(raw) < 3:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_BASE_INVALID",
            "official_stage_markers must contain at least 3 entries",
        )
    markers: list[dict[str, object]] = []
    for index, value in enumerate(raw):
        markers.append(_object(value, field=f"official_stage_markers[{index}]"))
    return markers


def _world_sources(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("world_sources")
    if not isinstance(raw, list) or not raw:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_BASE_INVALID",
            "world_sources must be non-empty list",
        )
    return [
        _object(value, field=f"world_sources[{index}]")
        for index, value in enumerate(raw)
    ]


def _case_payload(
    base: dict[str, object],
    *,
    category: str,
    training_type: str,
) -> dict[str, object]:
    payload = copy.deepcopy(base)
    markers = _markers(payload)
    worlds = _world_sources(payload)

    if category == "NOMINAL":
        return payload
    if category == "BOUNDARY":
        current = int(_string(markers[1].get("session_time_us"), field="marker time"))
        following = int(_string(markers[2].get("session_time_us"), field="marker time"))
        adjusted = current + min(12345, max(1, (following - current) // 4))
        if not current < adjusted < following:
            raise M3FixtureFamilyError(
                "M3_FIXTURE_FAMILY_BOUNDARY_TRANSFORM_INVALID",
                training_type,
            )
        markers[1]["session_time_us"] = str(adjusted)
        return payload
    if category == "GAP":
        first = int(_string(markers[1].get("session_time_us"), field="marker time"))
        second = int(_string(markers[2].get("session_time_us"), field="marker time"))
        gap_start = first + max(1, (second - first) // 3)
        gap_end = first + max(2, 2 * (second - first) // 3)
        payload["declared_source_gaps"] = [
            {
                "start_session_time_us": str(gap_start),
                "end_session_time_us": str(gap_end),
                "reason_code": "SYNTHETIC_SOURCE_GAP",
            }
        ]
        return payload
    if category == "INSUFFICIENT":
        if len(worlds) < 2:
            raise M3FixtureFamilyError(
                "M3_FIXTURE_FAMILY_INSUFFICIENT_TRANSFORM_INVALID",
                training_type,
            )
        payload["world_sources"] = worlds[:-1]
        return payload
    if category == "INVALID":
        first_stage = _string(markers[0].get("stage"), field="stage")
        markers[1]["stage"] = first_stage
        return payload
    if category == "APPLICABILITY":
        payload["applicability_fixture"] = EXPECTED_APPLICABILITY_FIXTURE
        return payload
    raise M3FixtureFamilyError(
        "M3_FIXTURE_FAMILY_CATEGORY_UNSUPPORTED",
        category,
    )


def _applicability_matrix() -> dict[str, object]:
    from tpaa_world.m3_mission_product_applicability import (
        load_m3_mission_product_inputs,
        project_m3_family_applicability,
    )

    inputs = load_m3_mission_product_inputs(
        APPLICABILITY_PATH,
        authority_root=AUTHORITY_ROOT,
    )
    positives = (
        ("P1-TRK-*", TRACK_ID),
        ("P1-ID-*", TRACK_ID),
        ("P1-PSV-*", IRST),
        ("P1-ESM-*", RWR),
        ("P1-DL-*", DL),
        ("P1-FUS-*", FUS),
    )
    negatives = tuple((family, RADAR) for family, _ in positives)
    positive_results = tuple(
        project_m3_family_applicability(
            inputs,
            family_code=family,
            mission_system_instance_id=subject,
        )
        for family, subject in positives
    )
    negative_results = tuple(
        project_m3_family_applicability(
            inputs,
            family_code=family,
            mission_system_instance_id=subject,
        )
        for family, subject in negatives
    )
    if not all(
        result.applicable and result.product_input_emitted
        for result in positive_results
    ):
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_APPLICABILITY_POSITIVE_FAILED",
            "positive matrix did not emit all governed inputs",
        )
    if not all(
        not result.applicable and not result.product_input_emitted
        for result in negative_results
    ):
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_APPLICABILITY_NEGATIVE_FAILED",
            "negative matrix emitted a fake product input",
        )
    return {
        "fixture_sha256": inputs.fixture_sha256,
        "positive": [
            {
                "family_code": result.family_code,
                "mission_system_instance_id": result.mission_system_instance_id,
                "system_type": result.system_type,
                "reason_code": result.reason_code,
                "logical_hash": result.logical_hash,
            }
            for result in positive_results
        ],
        "negative": [
            {
                "family_code": result.family_code,
                "mission_system_instance_id": result.mission_system_instance_id,
                "system_type": result.system_type,
                "reason_code": result.reason_code,
                "logical_hash": result.logical_hash,
            }
            for result in negative_results
        ],
    }


def _execute_case(
    *,
    training_type: str,
    category: str,
    base: dict[str, object],
    temp_root: Path,
) -> dict[str, object]:
    from tpaa_world.m3_profile_training import (
        M3ProfileWorldError,
        project_m3_training_profile,
    )

    payload = _case_payload(
        base,
        category=category,
        training_type=training_type,
    )
    case_text = _render(payload)
    case_path = temp_root / f"{training_type}-{category}.json"
    case_path.write_text(case_text, encoding="utf-8", newline="\n")
    case_sha256 = hashlib.sha256(case_text.encode("utf-8")).hexdigest()

    expected_error = {
        "INSUFFICIENT": "M3_PROFILE_REQUIRED_WORLD_MISMATCH",
        "INVALID": "M3_PROFILE_STAGE_MARKER_ORDER_INVALID",
    }.get(category)
    if expected_error is not None:
        try:
            project_m3_training_profile(case_path, authority_root=AUTHORITY_ROOT)
        except M3ProfileWorldError as exc:
            if exc.code != expected_error:
                raise M3FixtureFamilyError(
                    "M3_FIXTURE_FAMILY_ERROR_CODE_MISMATCH",
                    (
                        f"{training_type}/{category} expected={expected_error} "
                        f"actual={exc.code}"
                    ),
                ) from exc
            return {
                "training_type": training_type,
                "category": category,
                "input_sha256": case_sha256,
                "outcome": "EXPECTED_ERROR",
                "error_code": exc.code,
            }
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_EXPECTED_ERROR_NOT_RAISED",
            f"{training_type}/{category} expected={expected_error}",
        )

    first = project_m3_training_profile(case_path, authority_root=AUTHORITY_ROOT)
    replay = project_m3_training_profile(case_path, authority_root=AUTHORITY_ROOT)
    if first != replay or first.logical_hash != replay.logical_hash:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_REPLAY_UNSTABLE",
            f"{training_type}/{category}",
        )

    result: dict[str, object] = {
        "training_type": training_type,
        "category": category,
        "input_sha256": case_sha256,
        "outcome": "PROJECTED",
        "stage_profile_id": first.stage_profile_id,
        "world_capability_code": first.world_capability_code,
        "stage_count": len(first.stages),
        "world_codes": [code for code, _ in first.worlds],
        "logical_hash": first.logical_hash,
        "replay_stable": True,
    }
    if category == "GAP":
        gaps = payload.get("declared_source_gaps")
        if not isinstance(gaps, list) or len(gaps) != 1:
            raise M3FixtureFamilyError(
                "M3_FIXTURE_FAMILY_GAP_PROVENANCE_MISSING",
                training_type,
            )
        result["declared_source_gaps"] = gaps
        result["gap_business_semantics_executed"] = False
    if category == "APPLICABILITY":
        result["applicability"] = _applicability_matrix()
    return result


def _contains_host_path_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "host_path", "temp_path"}:
                return True
            if _contains_host_path_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_host_path_key(item) for item in value)
    return False


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    family = _load(FAMILY_PATH)
    if family.get("schema") != EXPECTED_SCHEMA:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_SCHEMA_MISMATCH",
            repr(family.get("schema")),
        )
    if family.get("task_id") != EXPECTED_TASK_ID:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_TASK_MISMATCH",
            repr(family.get("task_id")),
        )
    if family.get("tracking_issue") != EXPECTED_TRACKING_ISSUE:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_TRACKING_MISMATCH",
            repr(family.get("tracking_issue")),
        )
    if family.get("family_id") != EXPECTED_FAMILY_ID:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_ID_MISMATCH",
            repr(family.get("family_id")),
        )
    if family.get("family_version") != EXPECTED_FAMILY_VERSION:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_VERSION_MISMATCH",
            repr(family.get("family_version")),
        )
    if family.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_CLASSIFICATION_MISMATCH",
            repr(family.get("data_classification")),
        )
    if family.get("hash_policy") != EXPECTED_HASH_POLICY:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_HASH_POLICY_MISMATCH",
            repr(family.get("hash_policy")),
        )
    if family.get("platform_policy") != EXPECTED_PLATFORM_POLICY:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_PLATFORM_POLICY_MISMATCH",
            repr(family.get("platform_policy")),
        )
    if family.get("required_training_types") != list(EXPECTED_TRAINING_TYPES):
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_TRAINING_SET_MISMATCH",
            repr(family.get("required_training_types")),
        )
    if family.get("required_categories") != list(EXPECTED_CATEGORIES):
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_CATEGORY_SET_MISMATCH",
            repr(family.get("required_categories")),
        )
    if family.get("case_transforms") != EXPECTED_TRANSFORMS:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_TRANSFORM_MISMATCH",
            repr(family.get("case_transforms")),
        )
    if family.get("applicability_fixture") != EXPECTED_APPLICABILITY_FIXTURE:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_APPLICABILITY_FIXTURE_MISMATCH",
            repr(family.get("applicability_fixture")),
        )

    raw_contracts = _object(
        family.get("training_contracts"),
        field="training_contracts",
    )
    contracts: dict[str, dict[str, str]] = {}
    for training_type in EXPECTED_TRAINING_TYPES:
        raw = _object(
            raw_contracts.get(training_type),
            field=f"training_contracts.{training_type}",
        )
        contract = {
            key: _string(raw.get(key), field=f"{training_type}.{key}")
            for key in (
                "base_fixture",
                "episode_type",
                "stage_profile_id",
                "world_capability_code",
            )
        }
        contracts[training_type] = contract
    if contracts != EXPECTED_TRAINING_CONTRACTS:
        raise M3FixtureFamilyError(
            "M3_FIXTURE_FAMILY_TRAINING_CONTRACT_MISMATCH",
            repr(contracts),
        )

    base_hashes: dict[str, str] = {}
    results: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="tpaa-m3-world-005-") as temp:
        temp_root = Path(temp)
        for training_type in EXPECTED_TRAINING_TYPES:
            base_name = contracts[training_type]["base_fixture"]
            base_path = FIXTURE_ROOT / base_name
            base = _load(base_path)
            for field in (
                "episode_type",
                "stage_profile_id",
                "world_capability_code",
            ):
                if base.get(field) != contracts[training_type][field]:
                    raise M3FixtureFamilyError(
                        "M3_FIXTURE_FAMILY_BASE_CONTRACT_MISMATCH",
                        f"{training_type}.{field}",
                    )
            if base.get("training_type") != training_type:
                raise M3FixtureFamilyError(
                    "M3_FIXTURE_FAMILY_BASE_TRAINING_MISMATCH",
                    training_type,
                )
            base_hashes[training_type] = _sha(base_path)
            for category in EXPECTED_CATEGORIES:
                results.append(
                    _execute_case(
                        training_type=training_type,
                        category=category,
                        base=base,
                        temp_root=temp_root,
                    )
                )

    category_counts = {
        category: sum(result["category"] == category for result in results)
        for category in EXPECTED_CATEGORIES
    }
    training_counts = {
        training_type: sum(
            result["training_type"] == training_type
            for result in results
        )
        for training_type in EXPECTED_TRAINING_TYPES
    }
    gap_results = [result for result in results if result["category"] == "GAP"]
    applicability_results = [
        result for result in results if result["category"] == "APPLICABILITY"
    ]
    logical_product: dict[str, object] = {
        "schema": EXPECTED_SCHEMA,
        "task_id": EXPECTED_TASK_ID,
        "family_id": EXPECTED_FAMILY_ID,
        "family_version": EXPECTED_FAMILY_VERSION,
        "hash_policy": EXPECTED_HASH_POLICY,
        "platform_policy": EXPECTED_PLATFORM_POLICY,
        "required_training_types": list(EXPECTED_TRAINING_TYPES),
        "required_categories": list(EXPECTED_CATEGORIES),
        "base_fixture_sha256": base_hashes,
        "applicability_fixture_sha256": _sha(APPLICABILITY_PATH),
        "cases": results,
    }
    acceptance = {
        "family_manifest_exact": True,
        "four_training_types_exact": (
            set(training_counts) == set(EXPECTED_TRAINING_TYPES)
            and all(count == len(EXPECTED_CATEGORIES) for count in training_counts.values())
        ),
        "six_categories_each_exact": (
            set(category_counts) == set(EXPECTED_CATEGORIES)
            and all(count == len(EXPECTED_TRAINING_TYPES) for count in category_counts.values())
        ),
        "exact_24_case_matrix": len(results) == 24,
        "manifest_and_base_hashes_bound": (
            len(_sha(FAMILY_PATH)) == 64
            and len(_sha(APPLICABILITY_PATH)) == 64
            and all(len(value) == 64 for value in base_hashes.values())
        ),
        "case_input_hashes_bound": all(
            isinstance(result.get("input_sha256"), str)
            and len(cast(str, result["input_sha256"])) == 64
            for result in results
        ),
        "nominal_and_boundary_replay_stable": all(
            result.get("replay_stable") is True
            for result in results
            if result["category"] in {"NOMINAL", "BOUNDARY"}
        ),
        "gap_fixture_provenance_exact": (
            len(gap_results) == 4
            and all(result.get("declared_source_gaps") for result in gap_results)
            and all(
                result.get("gap_business_semantics_executed") is False
                for result in gap_results
            )
        ),
        "insufficient_fails_closed_distinctly": all(
            result.get("error_code") == "M3_PROFILE_REQUIRED_WORLD_MISMATCH"
            for result in results
            if result["category"] == "INSUFFICIENT"
        ),
        "invalid_fails_closed_distinctly": all(
            result.get("error_code") == "M3_PROFILE_STAGE_MARKER_ORDER_INVALID"
            for result in results
            if result["category"] == "INVALID"
        ),
        "applicability_matrix_exact": (
            len(applicability_results) == 4
            and all(result.get("applicability") for result in applicability_results)
        ),
        "platform_policy_exact": True,
        "host_paths_excluded": not _contains_host_path_key(logical_product),
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))
    family_sha256 = _sha(FAMILY_PATH)
    return {
        "schema": "TPAA_M3_WORLD_005_FIXTURE_FAMILY_EVIDENCE_V1",
        "task_id": EXPECTED_TASK_ID,
        "tracking_issue": EXPECTED_TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "fixture_family_file_sha256": family_sha256,
        "fixture_family_logical_hash": _hash(logical_product),
        "case_count": len(results),
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
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
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "family_file_sha256_equal": (
            windows.get("fixture_family_file_sha256")
            == linux.get("fixture_family_file_sha256")
        ),
        "family_logical_hash_equal": (
            windows.get("fixture_family_logical_hash")
            == linux.get("fixture_family_logical_hash")
        ),
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
        "schema": "TPAA_M3_WORLD_005_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": EXPECTED_TASK_ID,
        "tracking_issue": EXPECTED_TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
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
            "schema": "TPAA_M3_WORLD_005_FIXTURE_FAMILY_EVIDENCE_V1",
            "task_id": EXPECTED_TASK_ID,
            "tracking_issue": EXPECTED_TRACKING_ISSUE,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "task_complete": False,
            "implementation_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
