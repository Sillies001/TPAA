#!/usr/bin/env python3
"""M0 test/fixture harness for Golden, replay, evidence, and platform parity smoke."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = REPO_ROOT / "fixtures" / "golden" / "M0_BASIC_TRANSPORT_V1"
BASELINE_LOCK = REPO_ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
UV_LOCK = REPO_ROOT / "uv.lock"
PYPROJECT = REPO_ROOT / "pyproject.toml"
EXPECTED_FIXTURE_SCHEMA = "TPAA_M0_FIXTURE_BUNDLE_V1"
EXPECTED_FIXTURE_VERSION = "1.0.0"
EXPECTED_INPUT_SCHEMA = "TPAA_M0_BASIC_OBJECT_INPUT_V1"
EXPECTED_PRODUCT_SCHEMA = "TPAA_M0_BASIC_LOGICAL_PRODUCT_V1"


class FixtureError(RuntimeError):
    """Deterministic engineering failure from the M0 fixture harness."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class FixtureSpec:
    fixture_id: str
    fixture_version: str
    lifecycle: str
    input_path: Path
    input_sha256: str
    expected_path: Path
    expected_sha256: str
    context_ref: str
    stage_ref: str
    profile_ref: str
    numeric_tolerance: Decimal
    known_cases: tuple[tuple[str, str], ...]
    release_id: str
    replay_input_sha256: str
    replay_expected_sha256: str
    replay_context_ref: str
    replay_stage_ref: str
    replay_profile_ref: str
    current_refs_path: Path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except FileNotFoundError as exc:
        raise FixtureError("FIXTURE_FILE_MISSING", path.as_posix()) from exc


def _load_json_object(path: Path, *, missing_code: str, corrupt_code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FixtureError(missing_code, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError(corrupt_code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict):
        raise FixtureError(corrupt_code, f"{path.as_posix()}: JSON root must be object")
    result: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise FixtureError(corrupt_code, f"{path.as_posix()}: non-string key")
        result[key] = value
    return result


def _as_object(value: object, *, code: str, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise FixtureError(code, f"{field} must be object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise FixtureError(code, f"{field} contains non-string key")
        result[key] = item
    return result


def _as_list(value: object, *, code: str, field: str) -> list[object]:
    if not isinstance(value, list):
        raise FixtureError(code, f"{field} must be array")
    return list(value)


def _required_str(mapping: dict[str, object], key: str, *, code: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise FixtureError(code, f"{key} must be non-empty string")
    return value


def _safe_path(bundle: Path, relative: str, *, code: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise FixtureError(code, f"unsafe relative path: {relative}")
    resolved_bundle = bundle.resolve()
    resolved = (bundle / candidate).resolve()
    if resolved != resolved_bundle and resolved_bundle not in resolved.parents:
        raise FixtureError(code, f"path escapes fixture bundle: {relative}")
    return resolved


def _decimal(text: str, *, code: str, field: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise FixtureError(code, f"{field} is not decimal string: {text!r}") from exc
    if not value.is_finite():
        raise FixtureError(code, f"{field} must be finite decimal")
    return value


def _canonical_decimal(text: str, *, code: str, field: str) -> str:
    value = _decimal(text, code=code, field=field)
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _validate_structured(value: object, *, field: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise FixtureError("BASIC_OBJECT_FLOAT_FORBIDDEN", f"{field} contains float")
    if isinstance(value, list):
        return [_validate_structured(item, field=f"{field}[]") for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise FixtureError("BASIC_OBJECT_INVALID", f"{field} contains non-string key")
        result: dict[str, object] = {}
        for key in sorted(value):
            result[key] = _validate_structured(value[key], field=f"{field}.{key}")
        return result
    raise FixtureError(
        "BASIC_OBJECT_INVALID",
        f"{field} contains unsupported value {type(value).__name__}",
    )


def load_spec(bundle: Path = DEFAULT_BUNDLE) -> FixtureSpec:
    manifest = _load_json_object(
        bundle / "manifest.json",
        missing_code="FIXTURE_MANIFEST_MISSING",
        corrupt_code="FIXTURE_MANIFEST_CORRUPT",
    )
    if manifest.get("schema") != EXPECTED_FIXTURE_SCHEMA:
        raise FixtureError("FIXTURE_SCHEMA_MISMATCH", repr(manifest.get("schema")))
    fixture_version = _required_str(manifest, "fixture_version", code="FIXTURE_MANIFEST_INVALID")
    if fixture_version != EXPECTED_FIXTURE_VERSION:
        raise FixtureError(
            "FIXTURE_VERSION_UNSUPPORTED",
            f"expected={EXPECTED_FIXTURE_VERSION} actual={fixture_version}",
        )
    lifecycle = _required_str(manifest, "lifecycle", code="FIXTURE_MANIFEST_INVALID")
    if lifecycle != "APPROVED_GOLDEN":
        raise FixtureError("FIXTURE_LIFECYCLE_NOT_APPROVED", lifecycle)

    input_ref = _as_object(
        manifest.get("input"),
        code="FIXTURE_MANIFEST_INVALID",
        field="input",
    )
    expected_ref = _as_object(
        manifest.get("expected"),
        code="FIXTURE_MANIFEST_INVALID",
        field="expected",
    )
    authority = _as_object(
        manifest.get("authority_refs"),
        code="FIXTURE_MANIFEST_INVALID",
        field="authority_refs",
    )
    replay = _as_object(
        manifest.get("replay"),
        code="FIXTURE_MANIFEST_INVALID",
        field="replay",
    )
    current_refs = _as_object(
        manifest.get("current_refs"),
        code="FIXTURE_MANIFEST_INVALID",
        field="current_refs",
    )

    tolerance_text = _required_str(manifest, "numeric_tolerance", code="FIXTURE_MANIFEST_INVALID")
    tolerance = _decimal(
        tolerance_text,
        code="FIXTURE_TOLERANCE_INVALID",
        field="numeric_tolerance",
    )
    if tolerance < 0:
        raise FixtureError("FIXTURE_TOLERANCE_INVALID", "numeric_tolerance must be >= 0")

    known_raw = _as_list(
        manifest.get("known_cases"),
        code="FIXTURE_MANIFEST_INVALID",
        field="known_cases",
    )
    known_cases: list[tuple[str, str]] = []
    for index, item in enumerate(known_raw):
        case = _as_object(
            item,
            code="FIXTURE_MANIFEST_INVALID",
            field=f"known_cases[{index}]",
        )
        known_cases.append(
            (
                _required_str(case, "id", code="FIXTURE_MANIFEST_INVALID"),
                _required_str(case, "classification", code="FIXTURE_MANIFEST_INVALID"),
            )
        )
    required_cases = {
        ("missing_input", "INVALID"),
        ("corrupt_input", "INVALID"),
        ("version_mismatch", "INVALID"),
        ("insufficient_payload", "INSUFFICIENT"),
    }
    if not required_cases.issubset(set(known_cases)):
        raise FixtureError("FIXTURE_KNOWN_CASES_INCOMPLETE", repr(known_cases))

    input_relative = _required_str(input_ref, "path", code="FIXTURE_MANIFEST_INVALID")
    expected_relative = _required_str(expected_ref, "path", code="FIXTURE_MANIFEST_INVALID")
    current_relative = _required_str(current_refs, "path", code="FIXTURE_MANIFEST_INVALID")

    return FixtureSpec(
        fixture_id=_required_str(manifest, "fixture_id", code="FIXTURE_MANIFEST_INVALID"),
        fixture_version=fixture_version,
        lifecycle=lifecycle,
        input_path=_safe_path(bundle, input_relative, code="FIXTURE_MANIFEST_INVALID"),
        input_sha256=_required_str(input_ref, "sha256", code="FIXTURE_MANIFEST_INVALID"),
        expected_path=_safe_path(bundle, expected_relative, code="FIXTURE_MANIFEST_INVALID"),
        expected_sha256=_required_str(expected_ref, "sha256", code="FIXTURE_MANIFEST_INVALID"),
        context_ref=_required_str(authority, "context", code="FIXTURE_MANIFEST_INVALID"),
        stage_ref=_required_str(authority, "stage", code="FIXTURE_MANIFEST_INVALID"),
        profile_ref=_required_str(authority, "profile", code="FIXTURE_MANIFEST_INVALID"),
        numeric_tolerance=tolerance,
        known_cases=tuple(known_cases),
        release_id=_required_str(replay, "release_id", code="FIXTURE_MANIFEST_INVALID"),
        replay_input_sha256=_required_str(
            replay,
            "frozen_input_sha256",
            code="FIXTURE_MANIFEST_INVALID",
        ),
        replay_expected_sha256=_required_str(
            replay,
            "frozen_expected_sha256",
            code="FIXTURE_MANIFEST_INVALID",
        ),
        replay_context_ref=_required_str(replay, "context_ref", code="FIXTURE_MANIFEST_INVALID"),
        replay_stage_ref=_required_str(replay, "stage_ref", code="FIXTURE_MANIFEST_INVALID"),
        replay_profile_ref=_required_str(replay, "profile_ref", code="FIXTURE_MANIFEST_INVALID"),
        current_refs_path=_safe_path(bundle, current_relative, code="FIXTURE_MANIFEST_INVALID"),
    )


def project_basic_object(payload: dict[str, object]) -> dict[str, object]:
    if payload.get("schema") != EXPECTED_INPUT_SCHEMA:
        raise FixtureError("BASIC_OBJECT_SCHEMA_MISMATCH", repr(payload.get("schema")))
    identity = _as_object(payload.get("identity"), code="BASIC_OBJECT_INVALID", field="identity")
    result_identity = {
        "core_baseline": _required_str(identity, "core_baseline", code="BASIC_OBJECT_INVALID"),
        "db_schema_version": _required_str(
            identity,
            "db_schema_version",
            code="BASIC_OBJECT_INVALID",
        ),
    }

    session_time_raw = payload.get("session_time")
    if not isinstance(session_time_raw, str):
        raise FixtureError("SESSION_TIME_NOT_DECIMAL_STRING", repr(session_time_raw))
    _decimal(session_time_raw, code="SESSION_TIME_INVALID", field="session_time")

    values_raw = _as_list(payload.get("values"), code="BASIC_OBJECT_INVALID", field="values")
    if not values_raw:
        raise FixtureError("BASIC_OBJECT_INSUFFICIENT", "values must not be empty")
    result_values: list[object] = []
    for index, item in enumerate(values_raw):
        value = _as_object(
            item,
            code="BASIC_OBJECT_INVALID",
            field=f"values[{index}]",
        )
        kind = _required_str(value, "kind", code="BASIC_OBJECT_INVALID")
        raw = value.get("value")
        if kind == "NUMERIC":
            if not isinstance(raw, str):
                raise FixtureError("NUMERIC_VALUE_NOT_DECIMAL_STRING", f"values[{index}]")
            projected: object = _canonical_decimal(
                raw,
                code="NUMERIC_VALUE_INVALID",
                field=f"values[{index}].value",
            )
        elif kind == "TEXT":
            if not isinstance(raw, str):
                raise FixtureError("TEXT_VALUE_INVALID", f"values[{index}]")
            projected = raw
        elif kind == "BOOLEAN":
            if not isinstance(raw, bool):
                raise FixtureError("BOOLEAN_VALUE_INVALID", f"values[{index}]")
            projected = raw
        elif kind == "STRUCTURED":
            projected = _validate_structured(raw, field=f"values[{index}].value")
        else:
            raise FixtureError("VALUE_KIND_UNSUPPORTED", kind)
        result_values.append({"kind": kind, "value": projected})

    return {
        "schema": EXPECTED_PRODUCT_SCHEMA,
        "identity": result_identity,
        "session_time": session_time_raw,
        "values": result_values,
    }


def compare_products(
    expected: dict[str, object],
    actual: dict[str, object],
    tolerance: Decimal,
) -> list[str]:
    mismatches: list[str] = []
    for key in ("schema", "identity", "session_time"):
        if expected.get(key) != actual.get(key):
            mismatches.append(
                f"{key}: expected={expected.get(key)!r} actual={actual.get(key)!r}"
            )

    expected_values = _as_list(
        expected.get("values"),
        code="EXPECTED_PRODUCT_INVALID",
        field="expected.values",
    )
    actual_values = _as_list(
        actual.get("values"),
        code="ACTUAL_PRODUCT_INVALID",
        field="actual.values",
    )
    if len(expected_values) != len(actual_values):
        mismatches.append(
            f"values.length: expected={len(expected_values)} actual={len(actual_values)}"
        )
        return mismatches

    for index, (expected_raw, actual_raw) in enumerate(
        zip(expected_values, actual_values, strict=True)
    ):
        expected_item = _as_object(
            expected_raw,
            code="EXPECTED_PRODUCT_INVALID",
            field=f"expected.values[{index}]",
        )
        actual_item = _as_object(
            actual_raw,
            code="ACTUAL_PRODUCT_INVALID",
            field=f"actual.values[{index}]",
        )
        expected_kind = _required_str(
            expected_item,
            "kind",
            code="EXPECTED_PRODUCT_INVALID",
        )
        actual_kind = _required_str(
            actual_item,
            "kind",
            code="ACTUAL_PRODUCT_INVALID",
        )
        if expected_kind != actual_kind:
            mismatches.append(
                f"values[{index}].kind: expected={expected_kind!r} actual={actual_kind!r}"
            )
            continue
        expected_value = expected_item.get("value")
        actual_value = actual_item.get("value")
        if expected_kind == "NUMERIC":
            if not isinstance(expected_value, str) or not isinstance(actual_value, str):
                mismatches.append(
                    f"values[{index}].value: numeric value must be decimal string"
                )
                continue
            expected_decimal = _decimal(
                expected_value,
                code="EXPECTED_PRODUCT_INVALID",
                field=f"expected.values[{index}].value",
            )
            actual_decimal = _decimal(
                actual_value,
                code="ACTUAL_PRODUCT_INVALID",
                field=f"actual.values[{index}].value",
            )
            if abs(expected_decimal - actual_decimal) > tolerance:
                mismatches.append(
                    f"values[{index}].value: expected={expected_value} "
                    f"actual={actual_value} tolerance={tolerance}"
                )
        elif expected_value != actual_value:
            mismatches.append(
                f"values[{index}].value: expected={expected_value!r} actual={actual_value!r}"
            )
    return mismatches


def golden_check(bundle: Path = DEFAULT_BUNDLE) -> dict[str, object]:
    spec = load_spec(bundle)
    try:
        actual_input_sha = _sha256_file(spec.input_path)
    except FixtureError as exc:
        if exc.code == "FIXTURE_FILE_MISSING":
            raise FixtureError("FIXTURE_INPUT_MISSING", spec.input_path.as_posix()) from exc
        raise
    if actual_input_sha != spec.input_sha256:
        raise FixtureError(
            "FIXTURE_INPUT_HASH_MISMATCH",
            f"expected={spec.input_sha256} actual={actual_input_sha}",
        )
    try:
        actual_expected_sha = _sha256_file(spec.expected_path)
    except FixtureError as exc:
        if exc.code == "FIXTURE_FILE_MISSING":
            raise FixtureError("FIXTURE_EXPECTED_MISSING", spec.expected_path.as_posix()) from exc
        raise
    if actual_expected_sha != spec.expected_sha256:
        raise FixtureError(
            "FIXTURE_EXPECTED_HASH_MISMATCH",
            f"expected={spec.expected_sha256} actual={actual_expected_sha}",
        )

    payload = _load_json_object(
        spec.input_path,
        missing_code="FIXTURE_INPUT_MISSING",
        corrupt_code="FIXTURE_INPUT_CORRUPT",
    )
    expected = _load_json_object(
        spec.expected_path,
        missing_code="FIXTURE_EXPECTED_MISSING",
        corrupt_code="FIXTURE_EXPECTED_CORRUPT",
    )
    actual = project_basic_object(payload)
    mismatches = compare_products(expected, actual, spec.numeric_tolerance)
    if mismatches:
        raise FixtureError("GOLDEN_MISMATCH", "; ".join(mismatches))
    return actual


def replay_check(bundle: Path = DEFAULT_BUNDLE) -> dict[str, object]:
    spec = load_spec(bundle)
    if spec.replay_input_sha256 != spec.input_sha256:
        raise FixtureError("REPLAY_INPUT_PROVENANCE_MISMATCH", spec.replay_input_sha256)
    if spec.replay_expected_sha256 != spec.expected_sha256:
        raise FixtureError("REPLAY_EXPECTED_PROVENANCE_MISMATCH", spec.replay_expected_sha256)
    if (
        spec.replay_context_ref,
        spec.replay_stage_ref,
        spec.replay_profile_ref,
    ) != (spec.context_ref, spec.stage_ref, spec.profile_ref):
        raise FixtureError("REPLAY_AUTHORITY_REF_MISMATCH", spec.release_id)

    current = _load_json_object(
        spec.current_refs_path,
        missing_code="CURRENT_REFS_MISSING",
        corrupt_code="CURRENT_REFS_CORRUPT",
    )
    current_tuple = (
        current.get("context_ref"),
        current.get("stage_ref"),
        current.get("profile_ref"),
    )
    frozen_tuple = (
        spec.replay_context_ref,
        spec.replay_stage_ref,
        spec.replay_profile_ref,
    )
    if current_tuple == frozen_tuple:
        raise FixtureError(
            "REPLAY_NEGATIVE_CONTROL_INVALID",
            "current refs must differ from frozen replay refs in M0 framework smoke",
        )
    return golden_check(bundle)


def _git_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _product_version() -> str:
    raw: object = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    root = _as_object(raw, code="PYPROJECT_INVALID", field="pyproject")
    project = _as_object(root.get("project"), code="PYPROJECT_INVALID", field="project")
    return _required_str(project, "version", code="PYPROJECT_INVALID")


def _baseline_metadata() -> tuple[str, str, str, str, str]:
    lock = _load_json_object(
        BASELINE_LOCK,
        missing_code="BASELINE_LOCK_MISSING",
        corrupt_code="BASELINE_LOCK_CORRUPT",
    )
    baseline = _as_object(
        lock.get("baseline"),
        code="BASELINE_LOCK_CORRUPT",
        field="baseline",
    )
    core = _required_str(baseline, "core", code="BASELINE_LOCK_CORRUPT")
    db_schema = _required_str(baseline, "db_schema", code="BASELINE_LOCK_CORRUPT")
    dto_hash = "UNKNOWN"
    catalog_hash = "UNKNOWN"
    stage_hash = "UNKNOWN"
    artifacts = _as_list(
        lock.get("artifacts"),
        code="BASELINE_LOCK_CORRUPT",
        field="artifacts",
    )
    for raw in artifacts:
        item = _as_object(raw, code="BASELINE_LOCK_CORRUPT", field="artifacts[]")
        filename = item.get("file")
        digest = item.get("sha256")
        if isinstance(filename, str) and isinstance(digest, str):
            if filename == "CROSS_LAYER_DTO_CONTRACTS.json":
                dto_hash = digest
            elif filename == "P1_METRIC_CATALOG.json":
                catalog_hash = digest
            elif filename == "STAGE_REGISTRY.json":
                stage_hash = digest
    return core, db_schema, dto_hash, catalog_hash, stage_hash


def _request_hash(spec: FixtureSpec, command: str) -> str:
    payload = {
        "command": command,
        "fixture_id": spec.fixture_id,
        "fixture_version": spec.fixture_version,
        "input_sha256": spec.input_sha256,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _job_identity() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID")
    job = os.environ.get("GITHUB_JOB")
    if run_id and job:
        return f"github:{run_id}:{job}"
    return "local"


def fixture_evidence(bundle: Path = DEFAULT_BUNDLE) -> tuple[int, dict[str, object]]:
    started = dt.datetime.now(dt.UTC).isoformat()
    spec: FixtureSpec | None = None
    error: FixtureError | None = None
    try:
        spec = load_spec(bundle)
        golden_check(bundle)
        replay_check(bundle)
    except FixtureError as exc:
        error = exc

    core, db_schema, dto_hash, catalog_hash, stage_hash = _baseline_metadata()
    finished = dt.datetime.now(dt.UTC).isoformat()
    status = "PASS" if error is None else "FAIL"
    payload: dict[str, object] = {
        "schema": "TPAA_M0_TEST_FIXTURE_EVIDENCE_V1",
        "status": status,
        "product_build_version": _product_version(),
        "source_revision": _git_revision(),
        "core_baseline": core,
        "baseline_lock_sha256": _sha256_file(BASELINE_LOCK),
        "db_schema_version": db_schema,
        "p1_metric_catalog_sha256": catalog_hash,
        "stage_authority_sha256": stage_hash,
        "dto_authority_sha256": dto_hash,
        "dependency_lock_sha256": _sha256_file(UV_LOCK),
        "platform_certification_profile": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "runner_os": os.environ.get("RUNNER_OS"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
        },
        "job_identity": _job_identity(),
        "gate_id": "M0-TST-FIXTURE-HARNESS",
        "started_at_utc": started,
        "finished_at_utc": finished,
        "failure_classification": None if error is None else error.code,
        "failure_detail": None if error is None else error.detail,
        "scope": {
            "included": "M0 Golden/replay/typed-transport/fixture lifecycle framework smoke",
            "excluded": [
                "production Metric mathematics",
                "production Release/Replay engine",
                "M1 synthetic fixture bundles",
                "M0 Exit",
            ],
        },
    }
    if spec is not None:
        payload.update(
            {
                "fixture_id": spec.fixture_id,
                "fixture_version": spec.fixture_version,
                "fixture_input_sha256": spec.input_sha256,
                "numeric_tolerance": str(spec.numeric_tolerance),
                "context_ref": spec.context_ref,
                "stage_ref": spec.stage_ref,
                "profile_ref": spec.profile_ref,
                "replay_source_release": spec.release_id,
                "request_hash": _request_hash(spec, "fixture-check"),
                "known_cases": [
                    {"id": case_id, "classification": classification}
                    for case_id, classification in spec.known_cases
                ],
            }
        )
    return (0 if status == "PASS" else 2), payload


def platform_product(bundle: Path = DEFAULT_BUNDLE) -> dict[str, object]:
    spec = load_spec(bundle)
    product = replay_check(bundle)
    logical = platform.system().lower()
    if logical == "windows":
        platform_name = "windows"
    elif logical == "linux":
        platform_name = "linux"
    else:
        platform_name = logical or sys.platform
    return {
        "schema": "TPAA_M0_PLATFORM_LOGICAL_PRODUCT_V1",
        "source_revision": _git_revision(),
        "platform": {
            "logical": platform_name,
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "fixture": {
            "id": spec.fixture_id,
            "version": spec.fixture_version,
            "input_sha256": spec.input_sha256,
            "numeric_tolerance": str(spec.numeric_tolerance),
        },
        "product": product,
    }


def compare_platform_payloads(
    windows: dict[str, object],
    linux: dict[str, object],
) -> tuple[str, list[str], dict[str, object]]:
    mismatches: list[str] = []
    if windows.get("schema") != "TPAA_M0_PLATFORM_LOGICAL_PRODUCT_V1":
        mismatches.append("windows.schema")
    if linux.get("schema") != "TPAA_M0_PLATFORM_LOGICAL_PRODUCT_V1":
        mismatches.append("linux.schema")
    if windows.get("source_revision") != linux.get("source_revision"):
        mismatches.append("source_revision")

    windows_platform = _as_object(
        windows.get("platform"),
        code="PLATFORM_PRODUCT_INVALID",
        field="windows.platform",
    )
    linux_platform = _as_object(
        linux.get("platform"),
        code="PLATFORM_PRODUCT_INVALID",
        field="linux.platform",
    )
    if windows_platform.get("logical") != "windows":
        mismatches.append("windows.platform.logical")
    if linux_platform.get("logical") != "linux":
        mismatches.append("linux.platform.logical")

    windows_fixture = _as_object(
        windows.get("fixture"),
        code="PLATFORM_PRODUCT_INVALID",
        field="windows.fixture",
    )
    linux_fixture = _as_object(
        linux.get("fixture"),
        code="PLATFORM_PRODUCT_INVALID",
        field="linux.fixture",
    )
    for key in ("id", "version", "input_sha256", "numeric_tolerance"):
        if windows_fixture.get(key) != linux_fixture.get(key):
            mismatches.append(f"fixture.{key}")
    tolerance_raw = windows_fixture.get("numeric_tolerance")
    if not isinstance(tolerance_raw, str):
        raise FixtureError("PLATFORM_PRODUCT_INVALID", "numeric_tolerance must be string")
    tolerance = _decimal(
        tolerance_raw,
        code="PLATFORM_PRODUCT_INVALID",
        field="numeric_tolerance",
    )

    windows_product = _as_object(
        windows.get("product"),
        code="PLATFORM_PRODUCT_INVALID",
        field="windows.product",
    )
    linux_product = _as_object(
        linux.get("product"),
        code="PLATFORM_PRODUCT_INVALID",
        field="linux.product",
    )
    mismatches.extend(compare_products(windows_product, linux_product, tolerance))
    status = "PASS" if not mismatches else "FAIL"
    fixture_summary = {
        "id": windows_fixture.get("id"),
        "version": windows_fixture.get("version"),
        "input_sha256": windows_fixture.get("input_sha256"),
        "numeric_tolerance": tolerance_raw,
    }
    return status, mismatches, fixture_summary


def platform_equivalence_evidence(
    windows_path: Path,
    linux_path: Path,
) -> tuple[int, dict[str, object]]:
    started = dt.datetime.now(dt.UTC).isoformat()
    try:
        windows = _load_json_object(
            windows_path,
            missing_code="WINDOWS_PLATFORM_PRODUCT_MISSING",
            corrupt_code="WINDOWS_PLATFORM_PRODUCT_CORRUPT",
        )
        linux = _load_json_object(
            linux_path,
            missing_code="LINUX_PLATFORM_PRODUCT_MISSING",
            corrupt_code="LINUX_PLATFORM_PRODUCT_CORRUPT",
        )
        status, mismatches, fixture_summary = compare_platform_payloads(windows, linux)
        error_code: str | None = None
        error_detail: str | None = None
    except FixtureError as exc:
        windows = {}
        linux = {}
        status = "FAIL"
        mismatches = []
        fixture_summary = {}
        error_code = exc.code
        error_detail = exc.detail
    finished = dt.datetime.now(dt.UTC).isoformat()
    payload: dict[str, object] = {
        "schema": "TPAA_M0_CROSS_PLATFORM_LOGICAL_EQUIVALENCE_V1",
        "status": status,
        "source_revision": windows.get("source_revision") or linux.get("source_revision"),
        "fixture": fixture_summary,
        "windows": windows.get("platform"),
        "linux": linux.get("platform"),
        "comparison_policy": {
            "exact": [
                "source_revision",
                "fixture id/version/input hash/tolerance",
                "logical product schema/identity/session time",
                "value kind",
                "TEXT/BOOLEAN/STRUCTURED values",
            ],
            "numeric": "same fixture numeric_tolerance on both platforms",
        },
        "mismatches": mismatches,
        "failure_classification": error_code,
        "failure_detail": error_detail,
        "gate_id": "M0-CROSS-PLATFORM-LOGICAL-EQUIVALENCE",
        "started_at_utc": started,
        "finished_at_utc": finished,
    }
    return (0 if status == "PASS" else 2), payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    check.add_argument("--evidence", type=Path)
    product = sub.add_parser("platform-product")
    product.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    product.add_argument("--output", type=Path, required=True)
    compare = sub.add_parser("compare-platform")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return_code, payload = fixture_evidence(args.bundle)
        print(json.dumps(payload, indent=2, sort_keys=True))
        if args.evidence is not None:
            _write_json(args.evidence, payload)
        return return_code
    if args.command == "platform-product":
        try:
            payload = platform_product(args.bundle)
        except FixtureError as exc:
            print(f"{exc.code}: {exc.detail}", file=sys.stderr)
            return 2
        _write_json(args.output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "compare-platform":
        return_code, payload = platform_equivalence_evidence(args.windows, args.linux)
        _write_json(args.evidence, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return return_code
    raise RuntimeError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
