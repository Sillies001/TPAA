#!/usr/bin/env python3
"""Machine-readable acceptance verifier for M0-CORE-002."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_canonical import (  # noqa: E402
    EXPECTED_BASELINE_LOCK_SHA256,
    EXPECTED_CONTROLLED_ARTIFACT_COUNT,
    EXPECTED_CORE_BASELINE,
    ArtifactExpectation,
    CanonicalArtifactError,
    CanonicalArtifactLoader,
)

TASK_ID = "M0-CORE-002"
GATE_ID = "M0-CORE-002.CANONICAL_ARTIFACT_LOADER"
BASELINE_ROOT = REPO_ROOT / "baseline" / EXPECTED_CORE_BASELINE


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    detail: str


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _git_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"
    return completed.stdout.strip()


def _negative_check(
    *,
    check_id: str,
    expected_reason: str,
    action: Callable[[], object],
) -> CheckResult:
    try:
        action()
    except CanonicalArtifactError as exc:
        if exc.reason != expected_reason:
            return CheckResult(
                check_id,
                "FAIL",
                f"expected reason={expected_reason} actual={exc.reason}: {exc}",
            )
        if "artifact_id=" not in str(exc) or "version_" not in str(exc):
            return CheckResult(check_id, "FAIL", f"error context incomplete: {exc}")
        return CheckResult(check_id, "PASS", str(exc))
    except Exception as exc:  # pragma: no cover - defensive evidence boundary
        return CheckResult(check_id, "FAIL", f"unexpected exception {type(exc).__name__}: {exc}")
    return CheckResult(check_id, "FAIL", "operation unexpectedly succeeded")


def _run_checks() -> tuple[list[CheckResult], list[dict[str, object]]]:
    checks: list[CheckResult] = []
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    artifacts = loader.load_all()
    if len(artifacts) == EXPECTED_CONTROLLED_ARTIFACT_COUNT:
        checks.append(
            CheckResult(
                "LOAD-ALL-CONTROLLED",
                "PASS",
                f"loaded={len(artifacts)} controlled artifacts",
            )
        )
    else:
        checks.append(
            CheckResult(
                "LOAD-ALL-CONTROLLED",
                "FAIL",
                f"expected={EXPECTED_CONTROLLED_ARTIFACT_COUNT} actual={len(artifacts)}",
            )
        )

    records = [
        {
            "artifact_id": artifact.artifact_id,
            "filename": artifact.filename,
            "declared_id": artifact.declared_id,
            "declared_version": artifact.declared_version,
            "schema_version": artifact.schema_version,
            "core_baseline": artifact.core_baseline,
            "sha256": artifact.sha256,
            "bytes": artifact.byte_size,
        }
        for artifact in artifacts
    ]

    checks.append(
        _negative_check(
            check_id="VERSION-MISMATCH-FAIL-CLOSED",
            expected_reason="VERSION_MISMATCH",
            action=lambda: loader.load(
                "STAGE_REGISTRY",
                expectation=ArtifactExpectation(version="0.0.0"),
            ),
        )
    )
    checks.append(
        _negative_check(
            check_id="SCHEMA-VERSION-MISMATCH-FAIL-CLOSED",
            expected_reason="SCHEMA_VERSION_MISMATCH",
            action=lambda: loader.load(
                "CORE_LOGICAL_MODEL",
                expectation=ArtifactExpectation(schema_version="0.0.0"),
            ),
        )
    )
    checks.append(
        _negative_check(
            check_id="SCHEMA-SHAPE-MISMATCH-FAIL-CLOSED",
            expected_reason="SCHEMA_MISMATCH",
            action=lambda: loader.load(
                "STAGE_REGISTRY",
                expectation=ArtifactExpectation(
                    required_top_level_keys=("__TPAA_REQUIRED_TEST_KEY__",)
                ),
            ),
        )
    )
    checks.append(
        _negative_check(
            check_id="UNKNOWN-ARTIFACT-FAIL-CLOSED",
            expected_reason="UNKNOWN_ARTIFACT",
            action=lambda: loader.load("NOT_A_CONTROLLED_ARTIFACT"),
        )
    )

    with tempfile.TemporaryDirectory(prefix="tpaa_m0_core_002_") as temp_dir:
        copied = Path(temp_dir) / EXPECTED_CORE_BASELINE
        shutil.copytree(BASELINE_ROOT, copied)
        lock_path = copied / "BASELINE_LOCK.json"
        lock_path.write_bytes(lock_path.read_bytes() + b"\n")
        checks.append(
            _negative_check(
                check_id="BASELINE-LOCK-HASH-DRIFT-FAIL-CLOSED",
                expected_reason="BASELINE_LOCK_HASH_MISMATCH",
                action=lambda: CanonicalArtifactLoader(copied),
            )
        )

    with tempfile.TemporaryDirectory(prefix="tpaa_m0_core_002_") as temp_dir:
        copied = Path(temp_dir) / EXPECTED_CORE_BASELINE
        shutil.copytree(BASELINE_ROOT, copied)
        stage = copied / "canonical" / "STAGE_REGISTRY.json"
        stage.write_bytes(stage.read_bytes() + b"\n")
        drift_loader = CanonicalArtifactLoader(copied)
        checks.append(
            _negative_check(
                check_id="HASH-BYTE-DRIFT-FAIL-CLOSED",
                expected_reason="CONTROLLED_ARTIFACT_DRIFT",
                action=lambda: drift_loader.load("STAGE_REGISTRY"),
            )
        )

    with tempfile.TemporaryDirectory(prefix="tpaa_m0_core_002_") as temp_dir:
        copied = Path(temp_dir) / EXPECTED_CORE_BASELINE
        shutil.copytree(BASELINE_ROOT, copied)
        (copied / "canonical" / "STAGE_REGISTRY.json").unlink()
        missing_loader = CanonicalArtifactLoader(copied)
        checks.append(
            _negative_check(
                check_id="MISSING-ARTIFACT-FAIL-CLOSED",
                expected_reason="MISSING_CONTROLLED_ARTIFACT",
                action=lambda: missing_loader.load("STAGE_REGISTRY"),
            )
        )

    return checks, records


def _payload(checks: list[CheckResult], records: list[dict[str, object]]) -> dict[str, object]:
    failed = [check for check in checks if check.status != "PASS"]
    return {
        "evidence_schema": "TPAA_M0_GATE_EVIDENCE_V1",
        "task_id": TASK_ID,
        "workstream": "WS-CORE",
        "gate_id": GATE_ID,
        "status": "PASS" if not failed else "FAIL",
        "generated_at_utc": _utc_now(),
        "source_revision": _git_revision(),
        "environment": {
            "python": sys.version.split()[0],
            "implementation": sys.implementation.name,
            "platform": platform.platform(),
        },
        "core_baseline": EXPECTED_CORE_BASELINE,
        "baseline_lock_sha256": EXPECTED_BASELINE_LOCK_SHA256,
        "controlled_artifact_count": EXPECTED_CONTROLLED_ARTIFACT_COUNT,
        "checks": [asdict(check) for check in checks],
        "artifacts": records,
        "acceptance": {
            "version_errors_fail_closed": True,
            "schema_errors_fail_closed": True,
            "hash_errors_fail_closed": True,
            "errors_include_artifact_id_and_version_context": True,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify M0-CORE-002 Canonical loader contract")
    parser.add_argument("--evidence", type=Path, help="Optional JSON evidence output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checks, records = _run_checks()
    payload = _payload(checks, records)
    encoded = json.dumps(payload, indent=2, sort_keys=True)
    print(encoded)
    if args.evidence is not None:
        output = args.evidence
        if not output.is_absolute():
            output = REPO_ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
