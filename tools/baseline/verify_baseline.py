#!/usr/bin/env python3
"""Fail-closed verification for the SDIB-1.0 M0-CORE-001 baseline snapshot.

This command deliberately depends only on the Python standard library so the
repository can establish its machine-authority root before ADR-M0-001..003
freeze the runtime/dependency/static-toolchain choices.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

EXPECTED_CORE_BASELINE = "CB-1.4.0"
EXPECTED_BASELINE_LOCK_SHA256 = (
    "d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d"
)
EXPECTED_CONTROLLED_ARTIFACT_COUNT = 22
TASK_ID = "M0-CORE-001"
GATE_ID = "M0-CORE-001.BASELINE_VERIFY"
PRODUCT_BUILD_VERSION = "M0-BOOTSTRAP-UNVERSIONED"


@dataclass(frozen=True)
class ArtifactResult:
    file: str
    expected_sha256: str
    actual_sha256: str | None
    expected_bytes: int
    actual_bytes: int | None
    status: str
    reason: str | None = None


class BaselineVerificationError(RuntimeError):
    """Raised for a fail-closed baseline verification error."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_revision(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BaselineVerificationError(f"missing required file: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineVerificationError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BaselineVerificationError(f"expected JSON object: {path}")
    return data


def _validate_artifact_entry(entry: Any) -> tuple[str, str, int]:
    if not isinstance(entry, dict):
        raise BaselineVerificationError("BASELINE_LOCK artifacts entry must be an object")
    file_name = entry.get("file")
    expected_hash = entry.get("sha256")
    expected_bytes = entry.get("bytes")
    if not isinstance(file_name, str) or not file_name:
        raise BaselineVerificationError("artifact entry has invalid file name")
    # The lock uses simple basenames. Reject path traversal or alternate trees.
    if Path(file_name).name != file_name or file_name in {".", ".."}:
        raise BaselineVerificationError(f"unsafe artifact file name: {file_name!r}")
    if not file_name.endswith(".json"):
        raise BaselineVerificationError(f"controlled artifact must be JSON: {file_name}")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise BaselineVerificationError(f"invalid sha256 for artifact: {file_name}")
    try:
        int(expected_hash, 16)
    except ValueError as exc:
        raise BaselineVerificationError(f"non-hex sha256 for artifact: {file_name}") from exc
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise BaselineVerificationError(f"invalid byte count for artifact: {file_name}")
    return file_name, expected_hash.lower(), expected_bytes


def verify(baseline_root: Path) -> tuple[dict[str, Any], list[ArtifactResult], list[str]]:
    errors: list[str] = []
    lock_path = baseline_root / "BASELINE_LOCK.json"
    canonical_root = baseline_root / "canonical"

    if not lock_path.is_file():
        raise BaselineVerificationError(f"missing BASELINE_LOCK.json: {lock_path}")
    actual_lock_hash = _sha256_file(lock_path)
    if actual_lock_hash != EXPECTED_BASELINE_LOCK_SHA256:
        raise BaselineVerificationError(
            "BASELINE_LOCK hash mismatch: "
            f"expected={EXPECTED_BASELINE_LOCK_SHA256} actual={actual_lock_hash}"
        )

    lock = _load_json(lock_path)
    metadata = lock.get("baseline")
    entries = lock.get("artifacts")
    if not isinstance(metadata, dict):
        raise BaselineVerificationError("BASELINE_LOCK missing baseline object")
    if metadata.get("core") != EXPECTED_CORE_BASELINE:
        raise BaselineVerificationError(
            f"core baseline mismatch: expected={EXPECTED_CORE_BASELINE} actual={metadata.get('core')!r}"
        )
    if not isinstance(entries, list):
        raise BaselineVerificationError("BASELINE_LOCK missing artifacts list")
    if len(entries) != EXPECTED_CONTROLLED_ARTIFACT_COUNT:
        raise BaselineVerificationError(
            "controlled artifact count mismatch: "
            f"expected={EXPECTED_CONTROLLED_ARTIFACT_COUNT} actual={len(entries)}"
        )
    if not canonical_root.is_dir():
        raise BaselineVerificationError(f"missing canonical directory: {canonical_root}")

    parsed_entries = [_validate_artifact_entry(entry) for entry in entries]
    names = [item[0] for item in parsed_entries]
    if len(set(names)) != len(names):
        raise BaselineVerificationError("duplicate controlled artifact file names in BASELINE_LOCK")

    listed = set(names)
    present = {path.name for path in canonical_root.glob("*.json") if path.is_file()}
    missing = sorted(listed - present)
    unexpected = sorted(present - listed)
    if missing:
        errors.append("missing controlled artifacts: " + ", ".join(missing))
    if unexpected:
        errors.append("unexpected/uncontrolled canonical artifacts: " + ", ".join(unexpected))

    results: list[ArtifactResult] = []
    for file_name, expected_hash, expected_bytes in parsed_entries:
        artifact_path = canonical_root / file_name
        if not artifact_path.is_file():
            results.append(
                ArtifactResult(
                    file=file_name,
                    expected_sha256=expected_hash,
                    actual_sha256=None,
                    expected_bytes=expected_bytes,
                    actual_bytes=None,
                    status="FAIL",
                    reason="MISSING_CONTROLLED_ARTIFACT",
                )
            )
            continue
        actual_bytes = artifact_path.stat().st_size
        actual_hash = _sha256_file(artifact_path)
        mismatch: list[str] = []
        if actual_bytes != expected_bytes:
            mismatch.append(f"bytes expected={expected_bytes} actual={actual_bytes}")
        if actual_hash != expected_hash:
            mismatch.append(f"sha256 expected={expected_hash} actual={actual_hash}")
        if mismatch:
            errors.append(f"{file_name}: " + "; ".join(mismatch))
            results.append(
                ArtifactResult(
                    file=file_name,
                    expected_sha256=expected_hash,
                    actual_sha256=actual_hash,
                    expected_bytes=expected_bytes,
                    actual_bytes=actual_bytes,
                    status="FAIL",
                    reason="CONTROLLED_ARTIFACT_DRIFT",
                )
            )
        else:
            results.append(
                ArtifactResult(
                    file=file_name,
                    expected_sha256=expected_hash,
                    actual_sha256=actual_hash,
                    expected_bytes=expected_bytes,
                    actual_bytes=actual_bytes,
                    status="PASS",
                )
            )

    return lock, results, errors


def _artifact_hash_from_lock(lock: dict[str, Any], name: str) -> str | None:
    entries = lock.get("artifacts", [])
    for entry in entries:
        if isinstance(entry, dict) and entry.get("file") == name:
            value = entry.get("sha256")
            return value if isinstance(value, str) else None
    return None


def _read_version(path: Path, keys: Iterable[str]) -> str | None:
    try:
        data = _load_json(path)
    except BaselineVerificationError:
        return None
    for key in keys:
        value = data.get(key)
        if isinstance(value, (str, int, float)):
            return str(value)
    return None


def _evidence_payload(
    *,
    repo_root: Path,
    baseline_root: Path,
    lock: dict[str, Any] | None,
    results: list[ArtifactResult],
    errors: list[str],
    started_at: str,
    finished_at: str,
    status: str,
) -> dict[str, Any]:
    metadata = lock.get("baseline", {}) if isinstance(lock, dict) else {}
    canonical_root = baseline_root / "canonical"
    p1_catalog_hash = _artifact_hash_from_lock(lock or {}, "P1_METRIC_CATALOG.json")
    stage_hash = _artifact_hash_from_lock(lock or {}, "STAGE_REGISTRY.json")
    dto_hash = _artifact_hash_from_lock(lock or {}, "CROSS_LAYER_DTO_CONTRACTS.json")
    request_hash = hashlib.sha256(
        f"{GATE_ID}|{EXPECTED_CORE_BASELINE}|{EXPECTED_BASELINE_LOCK_SHA256}".encode("utf-8")
    ).hexdigest()

    return {
        "evidence_schema": "TPAA_M0_GATE_EVIDENCE_V1",
        "task_id": TASK_ID,
        "workstream": "WS-CORE",
        "gate_id": GATE_ID,
        "status": status,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "product_build_version": PRODUCT_BUILD_VERSION,
        "source_revision": _git_revision(repo_root),
        "core_baseline": metadata.get("core", EXPECTED_CORE_BASELINE),
        "baseline_lock_sha256": EXPECTED_BASELINE_LOCK_SHA256,
        "db_schema_version": metadata.get("db_schema"),
        "p1_metric_catalog": {
            "version": _read_version(canonical_root / "P1_METRIC_CATALOG.json", ["catalog_version", "version"]),
            "sha256": p1_catalog_hash,
        },
        "stage_authority": {
            "version": _read_version(canonical_root / "STAGE_REGISTRY.json", ["version"]),
            "sha256": stage_hash,
        },
        "dto_authority": {
            "version": _read_version(canonical_root / "CROSS_LAYER_DTO_CONTRACTS.json", ["version"]),
            "sha256": dto_hash,
        },
        "dependency_lock_hash": "NOT_ESTABLISHED_ADR_M0_002_PENDING",
        "platform_certification_profile": "HOST_UNCERTIFIED_DEV",
        "host": {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "fixture": {
            "id": "NOT_APPLICABLE",
            "version": "NOT_APPLICABLE",
            "input_hash": "NOT_APPLICABLE",
        },
        "command_request_hash": request_hash,
        "job_identity": TASK_ID,
        "numeric_tolerance_profile_hash": "NOT_APPLICABLE",
        "release_identity": "NOT_APPLICABLE",
        "replay_source_release": "NOT_APPLICABLE",
        "controlled_artifact_count_expected": EXPECTED_CONTROLLED_ARTIFACT_COUNT,
        "controlled_artifact_count_verified": sum(r.status == "PASS" for r in results),
        "artifacts": [asdict(item) for item in results],
        "errors": errors,
        "error_classification": "NONE" if status == "PASS" else "BASELINE_INTEGRITY_FAILURE",
    }


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify frozen CB-1.4.0 controlled artifacts exactly.")
    parser.add_argument(
        "--baseline-root",
        type=Path,
        default=_repo_root() / "baseline" / EXPECTED_CORE_BASELINE,
        help="Override baseline root (primarily for isolated tests).",
    )
    parser.add_argument("--json", action="store_true", help="Emit result as JSON instead of human text.")
    parser.add_argument("--evidence", type=Path, help="Write machine-readable gate evidence JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _repo_root()
    baseline_root = args.baseline_root.resolve()
    started_at = _utc_now()
    lock: dict[str, Any] | None = None
    results: list[ArtifactResult] = []
    errors: list[str] = []

    try:
        lock, results, errors = verify(baseline_root)
        if errors:
            raise BaselineVerificationError("; ".join(errors))
        status = "PASS"
        exit_code = 0
    except BaselineVerificationError as exc:
        if not errors:
            errors = [str(exc)]
        status = "FAIL"
        exit_code = 2

    finished_at = _utc_now()
    evidence = _evidence_payload(
        repo_root=repo_root,
        baseline_root=baseline_root,
        lock=lock,
        results=results,
        errors=errors,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
    )

    if args.evidence:
        _write_evidence(args.evidence, evidence)

    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        if status == "PASS":
            print(
                "PASS BASELINE_LOCK "
                f"core={EXPECTED_CORE_BASELINE} sha256={EXPECTED_BASELINE_LOCK_SHA256}"
            )
            for result in results:
                print(
                    f"PASS {result.file} bytes={result.actual_bytes} sha256={result.actual_sha256}"
                )
            print(
                f"SUMMARY PASS task={TASK_ID} controlled={len(results)}/{EXPECTED_CONTROLLED_ARTIFACT_COUNT} "
                f"baseline={EXPECTED_CORE_BASELINE}"
            )
        else:
            print(f"SUMMARY FAIL task={TASK_ID} baseline={EXPECTED_CORE_BASELINE}", file=sys.stderr)
            for error in errors:
                print(f"FAIL {error}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
