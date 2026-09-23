#!/usr/bin/env python3
"""Aggregate SDIB-1.0 M0 Exit evidence and fail closed on any unmet Gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def _gate(ci: dict[str, Any], name: str) -> bool:
    gates = ci.get("required_gates")
    if not isinstance(gates, list):
        return False
    for item in gates:
        if isinstance(item, dict) and item.get("name") == name:
            return item.get("status") == "PASS" and item.get("return_code") == 0
    return False


def _cold_ok(payload: dict[str, Any]) -> bool:
    return (
        payload.get("status") == "PASS"
        and payload.get("clean_clone") is True
        and payload.get("uv_sync_locked") is True
        and payload.get("m0_gates") == "PASS"
        and payload.get("worktree_clean") is True
    )


def _postgres_bootstrap_ok(payload: dict[str, Any]) -> bool:
    verification = payload.get("verification")
    return (
        payload.get("mid_bootstrap_rollback") == "PASS"
        and payload.get("clean_bootstrap_verify") == "PASS"
        and payload.get("missing_table_fail_closed") == "PASS"
        and payload.get("manifest_tamper_fail_closed") == "PASS"
        and payload.get("ddl_tamper_fail_closed") == "PASS"
        and payload.get("unexpected_index_fail_closed") == "PASS"
        and isinstance(verification, dict)
        and verification.get("schema_version") == "1.6.0"
        and verification.get("engine_profile") == "postgresql-service"
    )


def _postgres_repository_ok(payload: dict[str, Any]) -> bool:
    bootstrap = payload.get("bootstrap")
    return (
        payload.get("bootstrap_verify") == "PASS"
        and payload.get("repository_conformance") == "PASS"
        and payload.get("transaction_smoke") == "PASS"
        and isinstance(bootstrap, dict)
        and bootstrap.get("schema_version") == "1.6.0"
        and bootstrap.get("engine_profile") == "postgresql-service"
    )


def _check(
    gate_id: int,
    criterion: str,
    passed: bool,
    evidence: list[str],
) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "criterion": criterion,
        "status": "PASS" if passed else "FAIL",
        "evidence": evidence,
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    windows = _load(args.windows_ci)
    linux = _load(args.linux_ci)
    logical = _load(args.logical)
    windows_cold = _load(args.windows_cold_start)
    linux_cold = _load(args.linux_cold_start)
    postgres_bootstrap = _load(args.postgres_bootstrap)
    postgres_repository = _load(args.postgres_repository)
    postgres_cold = _load(args.postgres_cold_start)

    expected = args.expected_revision
    source_payloads = (
        windows,
        linux,
        logical,
        windows_cold,
        linux_cold,
        postgres_cold,
    )
    source_revision_ok = all(payload.get("source_revision") == expected for payload in source_payloads)

    both = lambda name: _gate(windows, name) and _gate(linux, name)

    summaries = [
        args.artifact_root / "dist" / "tpaa-0.0.0-WINDOWS_DESKTOP_X64.zip.summary.json",
        args.artifact_root / "dist" / "tpaa-0.0.0-WINDOWS_SERVICE_X64.zip.summary.json",
        args.artifact_root / "dist" / "tpaa-0.0.0-LINUX_DESKTOP_X64.tar.gz.summary.json",
        args.artifact_root / "dist" / "tpaa-0.0.0-LINUX_SERVICE_X64.tar.gz.summary.json",
    ]
    manifests = [
        args.artifact_root / "evidence" / "devops" / platform / profile / filename
        for platform in ("windows", "linux")
        for profile in ("desktop", "service")
        for filename in ("build-manifest.json", "sbom.cdx.json", "license-report.json")
    ]
    package_files_ok = all(path.is_file() for path in summaries)
    manifest_files_ok = all(path.is_file() for path in manifests)

    checks = [
        _check(
            1,
            "Baseline snapshot/hash verification is automated.",
            both("verify-baseline"),
            ["windows/linux: verify-baseline"],
        ),
        _check(
            2,
            "Canonical generation is repeatable and regenerate diff is zero.",
            all(
                both(name)
                for name in ("generate-check", "verify-generated", "regenerate-diff")
            ),
            ["windows/linux: generate-check, verify-generated, regenerate-diff"],
        ),
        _check(
            3,
            "Schema 1.6.0 clean bootstrap passes for SQLite and PostgreSQL.",
            both("sqlite-repository-acceptance")
            and both("sqlite-bootstrap-verify")
            and _postgres_bootstrap_ok(postgres_bootstrap)
            and _postgres_repository_ok(postgres_repository),
            [
                "windows/linux: sqlite repository + bootstrap verify",
                "exit-postgres: clean bootstrap/fail-closed acceptance",
                "exit-postgres: repository conformance/transaction smoke",
            ],
        ),
        _check(
            4,
            "Application/API shell starts and Core/schema mismatch remains fail-closed.",
            both("api-smoke") and both("contract"),
            ["windows/linux: api-smoke + contract"],
        ),
        _check(
            5,
            "PySide6 Desktop starts, handshakes and exits on Windows/Linux.",
            all(
                both(name)
                for name in (
                    "gui-smoke-headless",
                    "desktop-backend-smoke",
                    "ui-automation-smoke",
                )
            ),
            ["windows/linux: GUI, backend lifecycle and UI automation smoke"],
        ),
        _check(
            6,
            "Worker uses spawn-compatible serialization.",
            both("platform-smoke") and both("platform-tests"),
            ["windows/linux: platform-smoke + platform-tests"],
        ),
        _check(
            7,
            "Windows/Linux unit and contract suites both pass.",
            both("unit") and both("contract"),
            ["windows/linux: unit + contract"],
        ),
        _check(
            8,
            "Path/case/Unicode/temp/lock/atomic-replace tests pass.",
            both("platform-smoke") and both("platform-tests"),
            ["windows/linux: platform adapter tests/smoke"],
        ),
        _check(
            9,
            "Request/logical/artifact hash primitives are covered by tests.",
            both("unit") and both("contract"),
            ["windows/linux: governed unit/contract suites include M0-STO-006"],
        ),
        _check(
            10,
            "Audit/logging/security minimum controls exist and pass.",
            both("security-smoke"),
            ["windows/linux: security-smoke"],
        ),
        _check(
            11,
            "Dependency lock/build manifest/SBOM skeleton is generated.",
            both("uv-lock-check-offline") and manifest_files_ok,
            ["windows/linux: lock check", "four profile build/SBOM/license evidence sets"],
        ),
        _check(
            12,
            "Development packages clean install/start/stop.",
            both("package-smoke") and package_files_ok,
            ["windows/linux: package-smoke", "four package summary artifacts"],
        ),
        _check(
            13,
            "All ten M0 ADRs are CLOSED with no unresolved blocker carried into M1.",
            both("verify-governance"),
            ["windows/linux: verify-governance"],
        ),
        _check(
            14,
            "Cold-start from clean workspace reproduces the complete M0 results.",
            _cold_ok(windows_cold)
            and _cold_ok(linux_cold)
            and _cold_ok(postgres_cold)
            and postgres_cold.get("postgres_bootstrap") == "PASS"
            and postgres_cold.get("postgres_repository") == "PASS",
            [
                "windows clean-clone cold-start",
                "linux clean-clone cold-start",
                "linux clean-clone cold-start with live PostgreSQL bootstrap/repository acceptance",
            ],
        ),
    ]

    logical_ok = logical.get("status") == "PASS" and logical.get("mismatches") == []
    status = (
        "PASS"
        if source_revision_ok
        and logical_ok
        and all(item["status"] == "PASS" for item in checks)
        else "FAIL"
    )
    return {
        "schema": "TPAA_M0_EXIT_REVIEW_V1",
        "status": status,
        "decision": "GO" if status == "PASS" else "NO-GO",
        "source_revision": expected,
        "source_revision_consistent": source_revision_ok,
        "logical_equivalence": {
            "status": logical.get("status"),
            "mismatches": logical.get("mismatches"),
        },
        "exit_gates": checks,
        "known_limitations": [
            "M0 GO is engineering-substrate admission only; P1 capability is not admitted.",
            "Development packages are DEVELOPMENT_NOT_M5_QUALIFIED.",
            "Production Metric/Stage/Release qualification remains M1+ scope.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--windows-ci", type=Path, required=True)
    parser.add_argument("--linux-ci", type=Path, required=True)
    parser.add_argument("--logical", type=Path, required=True)
    parser.add_argument("--windows-cold-start", type=Path, required=True)
    parser.add_argument("--linux-cold-start", type=Path, required=True)
    parser.add_argument("--postgres-bootstrap", type=Path, required=True)
    parser.add_argument("--postgres-repository", type=Path, required=True)
    parser.add_argument("--postgres-cold-start", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = run(args)
        code = 0 if result["status"] == "PASS" else 2
    except Exception as exc:
        result = {
            "schema": "TPAA_M0_EXIT_REVIEW_V1",
            "status": "FAIL",
            "decision": "NO-GO",
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
