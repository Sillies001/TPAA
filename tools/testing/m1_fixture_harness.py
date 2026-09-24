#!/usr/bin/env python3
"""M1-TST-001 governed fixture bundle validation.

This harness validates synthetic fixture identity, hashes, authority references,
Golden review metadata, and cross-bundle completeness. It intentionally does
not implement M1 Data/World/Metric business logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
POLICY_PATH = REPO_ROOT / "tools" / "testing" / "M1_FIXTURE_POLICY.json"
ROLE_ASSIGNMENTS = REPO_ROOT / "docs" / "governance" / "M1_ROLE_ASSIGNMENTS.json"
STAGE_REGISTRY = (
    REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical" / "STAGE_REGISTRY.json"
)
METRIC_MATRIX = (
    REPO_ROOT
    / "baseline"
    / "CB-1.4.0"
    / "canonical"
    / "METRIC_INPUT_AUTHORITY_MATRIX.json"
)
STAGE_REGISTRY_SHA256 = "52377c097342fd52ad7b10e771a85420f3dca24f0446d171ff285306b8245691"
P1_METRIC_CATALOG_SHA256 = "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d"
DTO_CONTRACTS_SHA256 = "be9e83d18427c0a71d80df6ba2a56f7f611a059c749e1e163d9b5c0140b90e1c"
INPUT_HASH_ALGORITHM = "SHA256_PATH_SHA256_V1"
EXPECTED_HASH_ALGORITHM = "SHA256_FILE_BYTES_V1"

EXPECTED_SCHEMA = "TPAA_M1_FIXTURE_BUNDLE_V1"
EXPECTED_VERSION = "1.0.0"
EXPECTED_SOURCE_SCHEMA = "TPAA_M1_SYNTHETIC_SOURCE_V1"
EXPECTED_CONTEXT_SCHEMA = "TPAA_M1_SYNTHETIC_CONTEXT_V1"
EXPECTED_EXPECTED_SCHEMA = "TPAA_M1_FIXTURE_EXPECTED_V1"
EXPECTED_STAGE_PROFILE = "BASIC_FLIGHT_V1"
EXPECTED_METRICS = {
    "P1-AIR-001",
    "P1-AIR-002",
    "P1-AIR-003",
    "P1-AIR-004",
    "P1-AIR-007",
}
EXPECTED_STAGES = (
    "SETUP_ENTRY",
    "EXECUTION",
    "STABILIZATION_RECOVERY",
    "COMPLETION",
)
REVIEWABLE_STATES = {"REVIEWED", "APPROVED_GOLDEN"}


class M1FixtureError(RuntimeError):
    """Deterministic fail-closed M1 fixture validation error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class BundleSpec:
    fixture_id: str
    fixture_version: str
    review_state: str
    data_classification: str
    input_sha256: str
    expected_sha256: str
    source_path: Path
    source_sha256: str
    context_path: Path
    context_sha256: str
    expected_path: Path
    expected_file_sha256: str
    metric_codes: frozenset[str]
    stage_profile: str
    tolerance_id: str
    tolerance_absolute: Decimal
    tolerance_relative: Decimal
    expected_method: str
    expected_reviewer: str
    expected_independence_attestation: str


def _load_json(path: Path, *, missing_code: str, corrupt_code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise M1FixtureError(missing_code, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M1FixtureError(corrupt_code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict):
        raise M1FixtureError(corrupt_code, f"{path.as_posix()}: JSON root must be object")
    return {str(key): value for key, value in raw.items()}


def _object(value: object, *, code: str, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise M1FixtureError(code, f"{field} must be object")
    if not all(isinstance(key, str) for key in value):
        raise M1FixtureError(code, f"{field} contains non-string key")
    return dict(value)


def _string(value: object, *, code: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M1FixtureError(code, f"{field} must be non-empty string")
    return value


def _string_set(value: object, *, code: str, field: str) -> set[str]:
    if not isinstance(value, list) or not value:
        raise M1FixtureError(code, f"{field} must be non-empty array")
    result: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item:
            raise M1FixtureError(code, f"{field} entries must be non-empty strings")
        result.add(item)
    return result


def _decimal(value: object, *, field: str) -> Decimal:
    if not isinstance(value, str):
        raise M1FixtureError("M1_FIXTURE_TOLERANCE_INVALID", f"{field} must be string")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise M1FixtureError(
            "M1_FIXTURE_TOLERANCE_INVALID",
            f"{field} is not decimal: {value!r}",
        ) from exc
    if not result.is_finite() or result < 0:
        raise M1FixtureError(
            "M1_FIXTURE_TOLERANCE_INVALID",
            f"{field} must be finite and >= 0",
        )
    return result


def _safe_path(bundle: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise M1FixtureError("M1_FIXTURE_PATH_INVALID", relative)
    root = bundle.resolve()
    result = (bundle / candidate).resolve()
    if result != root and root not in result.parents:
        raise M1FixtureError("M1_FIXTURE_PATH_INVALID", relative)
    return result


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise M1FixtureError("M1_FIXTURE_FILE_MISSING", path.as_posix()) from exc


def _input_digest(source_sha256: str, context_sha256: str) -> str:
    value = (
        f"source/flight.json={source_sha256}\n"
        f"context/evaluation-context.json={context_sha256}\n"
    ).encode("ascii")
    return hashlib.sha256(value).hexdigest()


def _policy() -> dict[str, object]:
    policy = _load_json(
        POLICY_PATH,
        missing_code="M1_FIXTURE_POLICY_MISSING",
        corrupt_code="M1_FIXTURE_POLICY_CORRUPT",
    )
    if policy.get("schema") != "TPAA_M1_FIXTURE_POLICY_V1":
        raise M1FixtureError(
            "M1_FIXTURE_POLICY_SCHEMA_MISMATCH",
            repr(policy.get("schema")),
        )
    return policy


def expected_bundle_ids() -> set[str]:
    policy = _policy()
    bundles = policy.get("bundles")
    if not isinstance(bundles, list):
        raise M1FixtureError("M1_FIXTURE_POLICY_CORRUPT", "bundles must be array")
    result: set[str] = set()
    for index, item in enumerate(bundles):
        bundle = _object(
            item,
            code="M1_FIXTURE_POLICY_CORRUPT",
            field=f"bundles[{index}]",
        )
        result.add(
            _string(
                bundle.get("id"),
                code="M1_FIXTURE_POLICY_CORRUPT",
                field=f"bundles[{index}].id",
            )
        )
    return result


def load_spec(bundle: Path) -> BundleSpec:
    manifest = _load_json(
        bundle / "manifest.json",
        missing_code="M1_FIXTURE_MANIFEST_MISSING",
        corrupt_code="M1_FIXTURE_MANIFEST_CORRUPT",
    )
    if manifest.get("schema") != EXPECTED_SCHEMA:
        raise M1FixtureError(
            "M1_FIXTURE_SCHEMA_MISMATCH",
            repr(manifest.get("schema")),
        )
    version = _string(
        manifest.get("fixture_version"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="fixture_version",
    )
    if version != EXPECTED_VERSION:
        raise M1FixtureError(
            "M1_FIXTURE_VERSION_UNSUPPORTED",
            f"expected={EXPECTED_VERSION} actual={version}",
        )

    fixture_id = _string(
        manifest.get("fixture_id"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="fixture_id",
    )
    if fixture_id != bundle.name:
        raise M1FixtureError(
            "M1_FIXTURE_ID_PATH_MISMATCH",
            f"manifest={fixture_id} directory={bundle.name}",
        )

    policy = _policy()
    required = _string_set(
        policy.get("common_manifest_requirements"),
        code="M1_FIXTURE_POLICY_CORRUPT",
        field="common_manifest_requirements",
    )
    missing = sorted(required - set(manifest))
    if missing:
        raise M1FixtureError(
            "M1_FIXTURE_MANIFEST_INCOMPLETE",
            ",".join(missing),
        )

    classification = _string(
        manifest.get("data_classification"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="data_classification",
    )
    allowed = _object(
        policy.get("data_governance"),
        code="M1_FIXTURE_POLICY_CORRUPT",
        field="data_governance",
    ).get("default_allowed_classifications")
    if not isinstance(allowed, list) or classification not in allowed:
        raise M1FixtureError(
            "M1_FIXTURE_DATA_CLASSIFICATION_FORBIDDEN",
            classification,
        )

    review_state = _string(
        manifest.get("review_state"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="review_state",
    )
    if review_state not in REVIEWABLE_STATES:
        raise M1FixtureError("M1_FIXTURE_NOT_REVIEWABLE", review_state)

    files = _object(
        manifest.get("files"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="files",
    )

    def file_ref(name: str) -> tuple[Path, str]:
        raw = _object(
            files.get(name),
            code="M1_FIXTURE_MANIFEST_INVALID",
            field=f"files.{name}",
        )
        relative = _string(
            raw.get("path"),
            code="M1_FIXTURE_MANIFEST_INVALID",
            field=f"files.{name}.path",
        )
        digest = _string(
            raw.get("sha256"),
            code="M1_FIXTURE_MANIFEST_INVALID",
            field=f"files.{name}.sha256",
        )
        if len(digest) != 64:
            raise M1FixtureError(
                "M1_FIXTURE_MANIFEST_INVALID",
                f"files.{name}.sha256 must be 64 hex chars",
            )
        return _safe_path(bundle, relative), digest

    source_path, source_sha = file_ref("source")
    context_path, context_sha = file_ref("context")
    expected_path, expected_file_sha = file_ref("expected")

    input_hash_basis = manifest.get("input_hash_basis")
    if input_hash_basis != [
        "source/flight.json",
        "context/evaluation-context.json",
    ]:
        raise M1FixtureError(
            "M1_FIXTURE_INPUT_HASH_BASIS_MISMATCH",
            repr(input_hash_basis),
        )

    authority = _object(
        manifest.get("authority_refs"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="authority_refs",
    )
    if authority.get("core_baseline") != "CB-1.4.0":
        raise M1FixtureError(
            "M1_FIXTURE_AUTHORITY_MISMATCH",
            f"core_baseline={authority.get('core_baseline')!r}",
        )
    expected_authority_hashes = {
        "stage_registry_sha256": STAGE_REGISTRY_SHA256,
        "p1_metric_catalog_sha256": P1_METRIC_CATALOG_SHA256,
        "dto_contracts_sha256": DTO_CONTRACTS_SHA256,
    }
    for key, expected_digest in expected_authority_hashes.items():
        if authority.get(key) != expected_digest:
            raise M1FixtureError(
                "M1_FIXTURE_AUTHORITY_MISMATCH",
                f"{key}={authority.get(key)!r}",
            )
    stage_profile = _string(
        authority.get("stage_profile"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="authority_refs.stage_profile",
    )
    metric_codes = frozenset(
        _string_set(
            authority.get("metric_codes"),
            code="M1_FIXTURE_MANIFEST_INVALID",
            field="authority_refs.metric_codes",
        )
    )

    tolerance = _object(
        manifest.get("tolerance_profile"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="tolerance_profile",
    )
    tolerance_id = _string(
        tolerance.get("id"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="tolerance_profile.id",
    )

    if manifest.get("input_hash_algorithm") != INPUT_HASH_ALGORITHM:
        raise M1FixtureError(
            "M1_FIXTURE_INPUT_HASH_ALGORITHM_MISMATCH",
            repr(manifest.get("input_hash_algorithm")),
        )
    if manifest.get("expected_hash_algorithm") != EXPECTED_HASH_ALGORITHM:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_HASH_ALGORITHM_MISMATCH",
            repr(manifest.get("expected_hash_algorithm")),
        )

    generation = _object(
        manifest.get("expected_generation"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="expected_generation",
    )
    method = _string(
        generation.get("method"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="expected_generation.method",
    )
    reviewer = _string(
        generation.get("reviewer"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="expected_generation.reviewer",
    )
    attestation = _string(
        generation.get("independence_attestation"),
        code="M1_FIXTURE_MANIFEST_INVALID",
        field="expected_generation.independence_attestation",
    )

    roles = _load_json(
        ROLE_ASSIGNMENTS,
        missing_code="M1_ROLE_ASSIGNMENTS_MISSING",
        corrupt_code="M1_ROLE_ASSIGNMENTS_CORRUPT",
    )
    if roles.get("status") != "ASSIGNED":
        raise M1FixtureError(
            "M1_FIXTURE_GOLDEN_ROLE_UNASSIGNED",
            repr(roles.get("status")),
        )
    if reviewer != roles.get("golden_independent_reviewer"):
        raise M1FixtureError(
            "M1_FIXTURE_GOLDEN_REVIEWER_MISMATCH",
            f"fixture={reviewer!r} assigned={roles.get('golden_independent_reviewer')!r}",
        )
    if attestation != roles.get("golden_independence_attestation"):
        raise M1FixtureError(
            "M1_FIXTURE_GOLDEN_ATTESTATION_MISMATCH",
            "fixture attestation differs from M1 role assignment contract",
        )

    return BundleSpec(
        fixture_id=fixture_id,
        fixture_version=version,
        review_state=review_state,
        data_classification=classification,
        input_sha256=_string(
            manifest.get("input_sha256"),
            code="M1_FIXTURE_MANIFEST_INVALID",
            field="input_sha256",
        ),
        expected_sha256=_string(
            manifest.get("expected_sha256"),
            code="M1_FIXTURE_MANIFEST_INVALID",
            field="expected_sha256",
        ),
        source_path=source_path,
        source_sha256=source_sha,
        context_path=context_path,
        context_sha256=context_sha,
        expected_path=expected_path,
        expected_file_sha256=expected_file_sha,
        metric_codes=metric_codes,
        stage_profile=stage_profile,
        tolerance_id=tolerance_id,
        tolerance_absolute=_decimal(tolerance.get("absolute"), field="absolute"),
        tolerance_relative=_decimal(tolerance.get("relative"), field="relative"),
        expected_method=method,
        expected_reviewer=reviewer,
        expected_independence_attestation=attestation,
    )


def _validate_authorities(spec: BundleSpec) -> None:
    stages = _load_json(
        STAGE_REGISTRY,
        missing_code="M1_STAGE_AUTHORITY_MISSING",
        corrupt_code="M1_STAGE_AUTHORITY_CORRUPT",
    )
    profiles = _object(
        stages.get("profiles"),
        code="M1_STAGE_AUTHORITY_CORRUPT",
        field="profiles",
    )
    if spec.stage_profile != EXPECTED_STAGE_PROFILE or spec.stage_profile not in profiles:
        raise M1FixtureError(
            "M1_FIXTURE_STAGE_PROFILE_MISMATCH",
            spec.stage_profile,
        )

    matrix = _load_json(
        METRIC_MATRIX,
        missing_code="M1_METRIC_AUTHORITY_MISSING",
        corrupt_code="M1_METRIC_AUTHORITY_CORRUPT",
    )
    bindings = matrix.get("bindings")
    if not isinstance(bindings, list):
        raise M1FixtureError("M1_METRIC_AUTHORITY_CORRUPT", "bindings must be array")
    known = {
        item.get("metric_code")
        for item in bindings
        if isinstance(item, dict) and isinstance(item.get("metric_code"), str)
    }
    if spec.metric_codes != EXPECTED_METRICS or not spec.metric_codes <= known:
        raise M1FixtureError(
            "M1_FIXTURE_METRIC_SET_MISMATCH",
            repr(sorted(spec.metric_codes)),
        )


def _validate_payloads(spec: BundleSpec) -> None:
    source = _load_json(
        spec.source_path,
        missing_code="M1_FIXTURE_FILE_MISSING",
        corrupt_code="M1_FIXTURE_SOURCE_CORRUPT",
    )
    context = _load_json(
        spec.context_path,
        missing_code="M1_FIXTURE_FILE_MISSING",
        corrupt_code="M1_FIXTURE_CONTEXT_CORRUPT",
    )
    expected = _load_json(
        spec.expected_path,
        missing_code="M1_FIXTURE_FILE_MISSING",
        corrupt_code="M1_FIXTURE_EXPECTED_CORRUPT",
    )
    schemas = (
        (source, EXPECTED_SOURCE_SCHEMA, "source"),
        (context, EXPECTED_CONTEXT_SCHEMA, "context"),
        (expected, EXPECTED_EXPECTED_SCHEMA, "expected"),
    )
    for payload, schema, label in schemas:
        if payload.get("schema") != schema:
            raise M1FixtureError(
                "M1_FIXTURE_PAYLOAD_SCHEMA_MISMATCH",
                f"{label}={payload.get('schema')!r}",
            )
        if payload.get("fixture_id") != spec.fixture_id:
            raise M1FixtureError(
                "M1_FIXTURE_PAYLOAD_ID_MISMATCH",
                f"{label}={payload.get('fixture_id')!r}",
            )

    if source.get("data_classification") != "SYNTHETIC":
        raise M1FixtureError(
            "M1_FIXTURE_DATA_CLASSIFICATION_FORBIDDEN",
            repr(source.get("data_classification")),
        )
    if context.get("classification") != "SYNTHETIC":
        raise M1FixtureError(
            "M1_FIXTURE_DATA_CLASSIFICATION_FORBIDDEN",
            repr(context.get("classification")),
        )

    stage_profile = _object(
        context.get("stage_profile"),
        code="M1_FIXTURE_CONTEXT_CORRUPT",
        field="stage_profile",
    )
    if stage_profile.get("profile_id") != EXPECTED_STAGE_PROFILE:
        raise M1FixtureError(
            "M1_FIXTURE_STAGE_PROFILE_MISMATCH",
            repr(stage_profile.get("profile_id")),
        )

    generation = _object(
        expected.get("expected_generation"),
        code="M1_FIXTURE_EXPECTED_CORRUPT",
        field="expected_generation",
    )
    if generation.get("generated_from_implementation_under_test") is not False:
        raise M1FixtureError(
            "M1_FIXTURE_GOLDEN_INDEPENDENCE_FAILED",
            "generated_from_implementation_under_test must be false",
        )
    if generation.get("independently_reviewable") is not True:
        raise M1FixtureError(
            "M1_FIXTURE_GOLDEN_INDEPENDENCE_FAILED",
            "independently_reviewable must be true",
        )
    if generation.get("method") != spec.expected_method:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_METADATA_MISMATCH",
            "method differs between manifest and expected payload",
        )
    if generation.get("reviewer") != spec.expected_reviewer:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_METADATA_MISMATCH",
            "reviewer differs between manifest and expected payload",
        )
    if (
        generation.get("independence_attestation")
        != spec.expected_independence_attestation
    ):
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_METADATA_MISMATCH",
            "independence attestation differs between manifest and expected payload",
        )

    expected_stages = expected.get("stages")
    if not isinstance(expected_stages, list):
        raise M1FixtureError("M1_FIXTURE_EXPECTED_CORRUPT", "stages must be array")
    stage_types = tuple(
        item.get("stage_type")
        for item in expected_stages
        if isinstance(item, dict)
    )
    if stage_types != EXPECTED_STAGES:
        raise M1FixtureError(
            "M1_FIXTURE_STAGE_ORDER_MISMATCH",
            repr(stage_types),
        )


def validate_bundle(bundle: Path) -> dict[str, object]:
    spec = load_spec(bundle)

    actual_source = _sha256_file(spec.source_path)
    actual_context = _sha256_file(spec.context_path)
    actual_expected = _sha256_file(spec.expected_path)

    if actual_source != spec.source_sha256:
        raise M1FixtureError(
            "M1_FIXTURE_SOURCE_HASH_MISMATCH",
            f"expected={spec.source_sha256} actual={actual_source}",
        )
    if actual_context != spec.context_sha256:
        raise M1FixtureError(
            "M1_FIXTURE_CONTEXT_HASH_MISMATCH",
            f"expected={spec.context_sha256} actual={actual_context}",
        )
    if actual_expected != spec.expected_file_sha256:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_HASH_MISMATCH",
            f"expected={spec.expected_file_sha256} actual={actual_expected}",
        )
    if spec.expected_sha256 != actual_expected:
        raise M1FixtureError(
            "M1_FIXTURE_EXPECTED_HASH_MISMATCH",
            f"top_level={spec.expected_sha256} actual={actual_expected}",
        )

    actual_input = _input_digest(actual_source, actual_context)
    if spec.input_sha256 != actual_input:
        raise M1FixtureError(
            "M1_FIXTURE_INPUT_HASH_MISMATCH",
            f"expected={spec.input_sha256} actual={actual_input}",
        )

    _validate_authorities(spec)
    _validate_payloads(spec)

    return {
        "fixture_id": spec.fixture_id,
        "fixture_version": spec.fixture_version,
        "review_state": spec.review_state,
        "data_classification": spec.data_classification,
        "input_sha256": spec.input_sha256,
        "expected_sha256": spec.expected_sha256,
        "stage_profile": spec.stage_profile,
        "metric_codes": sorted(spec.metric_codes),
        "tolerance_profile": spec.tolerance_id,
        "status": "PASS",
    }


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


def validate_all() -> dict[str, object]:
    expected = expected_bundle_ids()
    actual = {
        path.name
        for path in FIXTURE_ROOT.iterdir()
        if path.is_dir()
    } if FIXTURE_ROOT.is_dir() else set()
    if actual != expected:
        raise M1FixtureError(
            "M1_FIXTURE_SET_MISMATCH",
            f"expected={sorted(expected)} actual={sorted(actual)}",
        )

    results = [
        validate_bundle(FIXTURE_ROOT / fixture_id)
        for fixture_id in sorted(expected)
    ]
    return {
        "schema": "TPAA_M1_TST_001_FIXTURE_EVIDENCE_V1",
        "task_id": "M1-TST-001",
        "status": "PASS",
        "source_revision": _git_revision(),
        "bundle_count": len(results),
        "reviewed_bundle_count": sum(
            item["review_state"] in REVIEWABLE_STATES for item in results
        ),
        "bundles": results,
        "business_logic_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    try:
        if args.bundle:
            if args.bundle not in expected_bundle_ids():
                raise M1FixtureError("M1_FIXTURE_ID_UNKNOWN", args.bundle)
            payload: dict[str, object] = {
                "schema": "TPAA_M1_TST_001_FIXTURE_EVIDENCE_V1",
                "task_id": "M1-TST-001",
                "status": "PASS",
                "source_revision": _git_revision(),
                "bundle_count": 1,
                "bundles": [validate_bundle(FIXTURE_ROOT / args.bundle)],
                "business_logic_executed": False,
            }
        else:
            payload = validate_all()
        return_code = 0
    except M1FixtureError as exc:
        payload = {
            "schema": "TPAA_M1_TST_001_FIXTURE_EVIDENCE_V1",
            "task_id": "M1-TST-001",
            "status": "FAIL",
            "source_revision": _git_revision(),
            "error_code": exc.code,
            "error_detail": exc.detail,
            "business_logic_executed": False,
        }
        return_code = 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
