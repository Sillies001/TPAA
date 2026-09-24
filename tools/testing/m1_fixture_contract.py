#!/usr/bin/env python3
"""M1-TST-001 fixture-bundle contract validator.

This module validates fixture identity, lifecycle, hashes, synthetic-data
classification, authority refs, tolerance contracts, and independently
reviewable expected-result provenance. It intentionally does not execute
Metric/Stage/World production algorithms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
POLICY = REPO_ROOT / "tools" / "testing" / "M1_FIXTURE_POLICY.json"
BASELINE_LOCK = REPO_ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"

MANIFEST_SCHEMA = "TPAA_M1_FIXTURE_MANIFEST_V1"
FIXTURE_VERSION = "1.0.0"
SOURCE_SCHEMA = "TPAA_M1_SYNTHETIC_SOURCE_V1"
CONTEXT_SCHEMA = "TPAA_M1_SYNTHETIC_CONTEXT_V1"
EXPECTED_SCHEMA = "TPAA_M1_FIXTURE_EXPECTED_V1"
ALLOWED_REVIEW_STATES = {"REVIEWED", "APPROVED_GOLDEN"}
EXPECTED_IDS = {
    "BF_M1_NOMINAL_V1",
    "BF_M1_GAP_V1",
    "BF_M1_ANGLE_WRAP_V1",
    "BF_M1_STRUCTURED_PARTIAL_V1",
    "BF_M1_STAGE_BOUNDARY_V1",
    "BF_M1_REPLAY_V1",
    "BF_M1_CROSS_PLATFORM_V1",
    "BF_M1_FAILURE_V1",
}
EXPECTED_FILES = {
    "source": "source/flight.json",
    "context": "context/evaluation-context.json",
    "expected": "expected/expected.json",
}


class M1FixtureError(RuntimeError):
    """Fail-closed fixture-contract error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class M1FixtureSpec:
    fixture_id: str
    fixture_version: str
    review_state: str
    data_classification: str
    source_path: Path
    context_path: Path
    expected_path: Path
    source_sha256: str
    context_sha256: str
    expected_sha256: str


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise M1FixtureError("M1_FIXTURE_FILE_MISSING", path.as_posix()) from exc


def _load(path: Path, *, missing: str, corrupt: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise M1FixtureError(missing, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M1FixtureError(corrupt, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict):
        raise M1FixtureError(corrupt, f"{path.as_posix()}: root must be object")
    return {str(key): value for key, value in raw.items()}


def _required_str(mapping: dict[str, object], key: str, *, code: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise M1FixtureError(code, f"{key} must be non-empty string")
    return value


def _object(mapping: dict[str, object], key: str, *, code: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise M1FixtureError(code, f"{key} must be object")
    return {str(item_key): item for item_key, item in value.items()}


def _safe_file(bundle: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise M1FixtureError("M1_FIXTURE_PATH_UNSAFE", relative)
    root = bundle.resolve()
    resolved = (bundle / candidate).resolve()
    if root not in resolved.parents:
        raise M1FixtureError("M1_FIXTURE_PATH_UNSAFE", relative)
    return resolved


def _baseline_hashes() -> dict[str, str]:
    lock = _load(
        BASELINE_LOCK,
        missing="M1_BASELINE_LOCK_MISSING",
        corrupt="M1_BASELINE_LOCK_CORRUPT",
    )
    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, list):
        raise M1FixtureError("M1_BASELINE_LOCK_CORRUPT", "artifacts must be array")
    result: dict[str, str] = {}
    for raw in artifacts:
        if not isinstance(raw, dict):
            continue
        name = raw.get("file")
        digest = raw.get("sha256")
        if isinstance(name, str) and isinstance(digest, str):
            result[name] = digest
    return result


def load_spec(bundle: Path) -> M1FixtureSpec:
    manifest = _load(
        bundle / "manifest.json",
        missing="M1_FIXTURE_MANIFEST_MISSING",
        corrupt="M1_FIXTURE_MANIFEST_CORRUPT",
    )
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise M1FixtureError(
            "M1_FIXTURE_SCHEMA_MISMATCH",
            repr(manifest.get("schema")),
        )
    fixture_id = _required_str(
        manifest,
        "fixture_id",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    if fixture_id != bundle.name:
        raise M1FixtureError(
            "M1_FIXTURE_ID_PATH_MISMATCH",
            f"path={bundle.name} manifest={fixture_id}",
        )
    fixture_version = _required_str(
        manifest,
        "fixture_version",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    if fixture_version != FIXTURE_VERSION:
        raise M1FixtureError(
            "M1_FIXTURE_VERSION_UNSUPPORTED",
            f"expected={FIXTURE_VERSION} actual={fixture_version}",
        )
    review_state = _required_str(
        manifest,
        "review_state",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    if review_state not in ALLOWED_REVIEW_STATES:
        raise M1FixtureError("M1_FIXTURE_NOT_REVIEWED", review_state)
    classification = _required_str(
        manifest,
        "data_classification",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    if classification != "SYNTHETIC":
        raise M1FixtureError("M1_FIXTURE_DATA_CLASS_FORBIDDEN", classification)

    files = _object(manifest, "files", code="M1_FIXTURE_MANIFEST_INVALID")
    refs: dict[str, tuple[Path, str]] = {}
    for role, expected_path in EXPECTED_FILES.items():
        item_raw = files.get(role)
        if not isinstance(item_raw, dict):
            raise M1FixtureError(
                "M1_FIXTURE_MANIFEST_INVALID",
                f"files.{role} must be object",
            )
        item = {str(key): value for key, value in item_raw.items()}
        relative = _required_str(
            item,
            "path",
            code="M1_FIXTURE_MANIFEST_INVALID",
        )
        if relative != expected_path:
            raise M1FixtureError(
                "M1_FIXTURE_LAYOUT_MISMATCH",
                f"{role}: expected={expected_path} actual={relative}",
            )
        digest = _required_str(
            item,
            "sha256",
            code="M1_FIXTURE_MANIFEST_INVALID",
        )
        refs[role] = (_safe_file(bundle, relative), digest)

    input_sha = _required_str(
        manifest,
        "input_sha256",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    expected_sha = _required_str(
        manifest,
        "expected_sha256",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    if input_sha != refs["source"][1]:
        raise M1FixtureError(
            "M1_FIXTURE_INPUT_HASH_DECLARATION_MISMATCH",
            fixture_id,
        )
    if expected_sha != refs["expected"][1]:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_HASH_DECLARATION_MISMATCH",
            fixture_id,
        )

    tolerance = _object(
        manifest,
        "tolerance_profile",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    if tolerance.get("discrete") != "EXACT":
        raise M1FixtureError("M1_FIXTURE_TOLERANCE_INVALID", fixture_id)
    numeric_abs = tolerance.get("numeric_abs")
    if not isinstance(numeric_abs, str) or not numeric_abs:
        raise M1FixtureError("M1_FIXTURE_TOLERANCE_INVALID", fixture_id)

    authority = _object(
        manifest,
        "authority_refs",
        code="M1_FIXTURE_MANIFEST_INVALID",
    )
    hashes = _baseline_hashes()
    expected_authority = {
        "core_baseline": "CB-1.4.0",
        "stage_profile": "BASIC_FLIGHT_V1",
        "stage_registry_sha256": hashes.get("STAGE_REGISTRY.json"),
        "p1_metric_catalog_sha256": hashes.get("P1_METRIC_CATALOG.json"),
        "dto_contracts_sha256": hashes.get("CROSS_LAYER_DTO_CONTRACTS.json"),
    }
    for key, expected_value in expected_authority.items():
        if authority.get(key) != expected_value:
            raise M1FixtureError(
                "M1_FIXTURE_AUTHORITY_MISMATCH",
                f"{fixture_id}:{key}",
            )

    return M1FixtureSpec(
        fixture_id=fixture_id,
        fixture_version=fixture_version,
        review_state=review_state,
        data_classification=classification,
        source_path=refs["source"][0],
        context_path=refs["context"][0],
        expected_path=refs["expected"][0],
        source_sha256=refs["source"][1],
        context_sha256=refs["context"][1],
        expected_sha256=refs["expected"][1],
    )


def validate_bundle(bundle: Path) -> dict[str, object]:
    spec = load_spec(bundle)
    actual = {
        "source": _sha256(spec.source_path),
        "context": _sha256(spec.context_path),
        "expected": _sha256(spec.expected_path),
    }
    expected = {
        "source": spec.source_sha256,
        "context": spec.context_sha256,
        "expected": spec.expected_sha256,
    }
    for role in ("source", "context", "expected"):
        if actual[role] != expected[role]:
            raise M1FixtureError(
                "M1_FIXTURE_HASH_MISMATCH",
                f"{spec.fixture_id}:{role}:"
                f"expected={expected[role]} actual={actual[role]}",
            )

    source = _load(
        spec.source_path,
        missing="M1_FIXTURE_FILE_MISSING",
        corrupt="M1_FIXTURE_SOURCE_CORRUPT",
    )
    context = _load(
        spec.context_path,
        missing="M1_FIXTURE_FILE_MISSING",
        corrupt="M1_FIXTURE_CONTEXT_CORRUPT",
    )
    expected_payload = _load(
        spec.expected_path,
        missing="M1_FIXTURE_FILE_MISSING",
        corrupt="M1_FIXTURE_EXPECTED_CORRUPT",
    )
    for payload, schema, role in (
        (source, SOURCE_SCHEMA, "source"),
        (context, CONTEXT_SCHEMA, "context"),
        (expected_payload, EXPECTED_SCHEMA, "expected"),
    ):
        if payload.get("schema") != schema:
            raise M1FixtureError(
                "M1_FIXTURE_PAYLOAD_SCHEMA_MISMATCH",
                f"{spec.fixture_id}:{role}",
            )
        if payload.get("fixture_id") != spec.fixture_id:
            raise M1FixtureError(
                "M1_FIXTURE_PAYLOAD_ID_MISMATCH",
                f"{spec.fixture_id}:{role}",
            )

    if source.get("data_classification") != "SYNTHETIC":
        raise M1FixtureError("M1_FIXTURE_SOURCE_CLASS_FORBIDDEN", spec.fixture_id)
    if context.get("classification") != "SYNTHETIC":
        raise M1FixtureError("M1_FIXTURE_CONTEXT_CLASS_FORBIDDEN", spec.fixture_id)

    stage_profile = context.get("stage_profile")
    if not isinstance(stage_profile, dict):
        raise M1FixtureError("M1_FIXTURE_CONTEXT_INVALID", "stage_profile")
    if stage_profile.get("profile_id") != "BASIC_FLIGHT_V1":
        raise M1FixtureError(
            "M1_FIXTURE_STAGE_PROFILE_MISMATCH",
            spec.fixture_id,
        )

    generation = expected_payload.get("expected_generation")
    if not isinstance(generation, dict):
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_PROVENANCE_MISSING",
            spec.fixture_id,
        )
    if generation.get("generated_from_implementation_under_test") is not False:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_NOT_INDEPENDENT",
            spec.fixture_id,
        )
    if generation.get("independently_reviewable") is not True:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_NOT_REVIEWABLE",
            spec.fixture_id,
        )
    reviewer = generation.get("reviewer")
    attestation = generation.get("independence_attestation")
    if not isinstance(reviewer, str) or not reviewer:
        raise M1FixtureError("M1_FIXTURE_REVIEWER_MISSING", spec.fixture_id)
    if not isinstance(attestation, str) or not attestation:
        raise M1FixtureError(
            "M1_FIXTURE_INDEPENDENCE_ATTESTATION_MISSING",
            spec.fixture_id,
        )

    return {
        "fixture_id": spec.fixture_id,
        "fixture_version": spec.fixture_version,
        "review_state": spec.review_state,
        "data_classification": spec.data_classification,
        "hashes": actual,
        "status": "PASS",
    }


def validate_all(root: Path = FIXTURE_ROOT) -> dict[str, object]:
    policy = _load(
        POLICY,
        missing="M1_FIXTURE_POLICY_MISSING",
        corrupt="M1_FIXTURE_POLICY_CORRUPT",
    )
    bundles = policy.get("bundles")
    if not isinstance(bundles, list):
        raise M1FixtureError("M1_FIXTURE_POLICY_CORRUPT", "bundles")
    policy_ids = {
        item.get("id")
        for item in bundles
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if policy_ids != EXPECTED_IDS:
        raise M1FixtureError(
            "M1_FIXTURE_POLICY_ID_MISMATCH",
            repr(sorted(policy_ids)),
        )
    actual_dirs = {
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    if actual_dirs != EXPECTED_IDS:
        raise M1FixtureError(
            "M1_FIXTURE_DIRECTORY_SET_MISMATCH",
            f"expected={sorted(EXPECTED_IDS)} actual={sorted(actual_dirs)}",
        )
    results = [validate_bundle(root / fixture_id) for fixture_id in sorted(EXPECTED_IDS)]
    return {
        "schema": "TPAA_M1_FIXTURE_CONTRACT_EVIDENCE_V1",
        "task_id": "M1-TST-001",
        "status": "PASS",
        "fixture_count": len(results),
        "fixtures": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        if args.bundle is None:
            result = validate_all()
        else:
            result = {
                "schema": "TPAA_M1_FIXTURE_CONTRACT_EVIDENCE_V1",
                "task_id": "M1-TST-001",
                "status": "PASS",
                "fixture_count": 1,
                "fixtures": [validate_bundle(args.bundle)],
            }
    except M1FixtureError as exc:
        result = {
            "schema": "TPAA_M1_FIXTURE_CONTRACT_EVIDENCE_V1",
            "task_id": "M1-TST-001",
            "status": "FAIL",
            "failure_classification": exc.code,
            "failure_detail": exc.detail,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.evidence is not None:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
