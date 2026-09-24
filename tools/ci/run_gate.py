#!/usr/bin/env python3
"""Run the current M0 cross-platform CI gate set and emit auditable evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"


def _platform_name() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system or str(sys.platform)


def _capture(args: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            list(args),
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"UNAVAILABLE: {exc}"
    return (completed.stdout or completed.stderr).strip()


def _git_revision() -> str:
    value = _capture(["git", "rev-parse", "HEAD"])
    return value if len(value) == 40 else "UNKNOWN"


def _run_gate(name: str, args: Sequence[str]) -> dict[str, object]:
    print(f"CI_GATE_START {name}", flush=True)
    started = time.monotonic()
    try:
        completed = subprocess.run(list(args), cwd=REPO_ROOT, check=False)
        return_code = completed.returncode
    except OSError as exc:
        print(f"CI_GATE_EXECUTION_ERROR {name}: {exc}", file=sys.stderr, flush=True)
        return_code = 127
    duration = round(time.monotonic() - started, 3)
    status = "PASS" if return_code == 0 else "FAIL"
    print(f"CI_GATE_{status} {name} return_code={return_code} duration_seconds={duration}", flush=True)
    return {
        "name": name,
        "command": list(args),
        "status": status,
        "return_code": return_code,
        "duration_seconds": duration,
    }


def _dispatcher(*args: str) -> list[str]:
    return [sys.executable, str(DISPATCHER), *args]


def _sqlite_bootstrap_gate() -> dict[str, object]:
    name = "sqlite-bootstrap-verify"
    print(f"CI_GATE_START {name}", flush=True)
    started = time.monotonic()
    return_code = 0
    commands: list[list[str]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-ci-") as raw:
        db = Path(raw) / "bootstrap.sqlite3"
        for command in (
            _dispatcher("db-bootstrap", str(db)),
            _dispatcher("db-verify", str(db)),
        ):
            commands.append(command)
            try:
                completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
                return_code = completed.returncode
            except OSError as exc:
                print(f"CI_GATE_EXECUTION_ERROR {name}: {exc}", file=sys.stderr, flush=True)
                return_code = 127
            if return_code != 0:
                break
    duration = round(time.monotonic() - started, 3)
    status = "PASS" if return_code == 0 else "FAIL"
    print(f"CI_GATE_{status} {name} return_code={return_code} duration_seconds={duration}", flush=True)
    return {
        "name": name,
        "command": commands,
        "status": status,
        "return_code": return_code,
        "duration_seconds": duration,
    }


def _write_evidence(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(*, expected_platform: str | None, evidence: Path | None) -> int:
    actual_platform = _platform_name()
    started_at = dt.datetime.now(dt.UTC).isoformat()
    gates: list[dict[str, object]] = []

    preflight_failure: str | None = None
    if actual_platform not in {"windows", "linux"}:
        preflight_failure = f"UNSUPPORTED_PLATFORM:{actual_platform}"
    elif expected_platform is not None and expected_platform != actual_platform:
        preflight_failure = f"PLATFORM_MISMATCH:expected={expected_platform}:actual={actual_platform}"

    if preflight_failure is None:
        commands: tuple[tuple[str, list[str]], ...] = (
            ("verify-ci", _dispatcher("verify-ci")),
            ("verify-baseline", _dispatcher("verify-baseline")),
            ("bootstrap-check-only", _dispatcher("bootstrap", "--check-only")),
            ("verify-canonical", _dispatcher("verify-canonical")),
            ("generate-check", _dispatcher("generate", "--check")),
            ("verify-generated", _dispatcher("verify-generated")),
            ("regenerate-diff", _dispatcher("regenerate-diff")),
            ("verify-architecture", _dispatcher("verify-architecture")),
            ("verify-repository-policy", _dispatcher("verify-repository-policy")),
            ("verify-desktop-lifecycle-policy", _dispatcher("verify-desktop-lifecycle-policy")),
            ("verify-repository-bootstrap", _dispatcher("verify-repository-bootstrap")),
            ("verify-m0-delta-closure", _dispatcher("verify-m0-delta-closure")),
            ("m1-fixture-contract", _dispatcher("m1-fixture-check")),
            ("m1-source-adapter", _dispatcher("m1-source-adapter-check")),
            ("m1-source-registry", _dispatcher("m1-source-registry-check")),
            ("m1-session-time", _dispatcher("m1-session-time-check")),
            ("m1-aircraft-identity", _dispatcher("m1-aircraft-identity-check")),
            ("m1-canonical-flight-channels", _dispatcher("m1-canonical-flight-channels-check")),
            ("m1-evaluation-context", _dispatcher("m1-evaluation-context-check")),
            ("m1-lineage-quality", _dispatcher("m1-lineage-quality-check")),\n            ("m1-basic-episode", _dispatcher("m1-basic-episode-check")),
            ("verify-governance", _dispatcher("verify-governance")),
            ("openapi-snapshot", _dispatcher("openapi-snapshot", "--check")),
            ("migration-smoke", _dispatcher("migration-smoke")),
            ("backup-restore-smoke", _dispatcher("backup-restore-smoke")),
            ("security-smoke", _dispatcher("security-smoke")),
            ("lint", _dispatcher("lint")),
            ("typecheck", _dispatcher("typecheck")),
            ("unit", _dispatcher("test-unit")),
            ("contract", _dispatcher("test-contract")),
            ("golden-framework", _dispatcher("test-golden")),
            ("replay-framework", _dispatcher("test-replay")),
            ("e2e-framework", _dispatcher("test-e2e")),
            ("platform-tests", _dispatcher("test-platform")),
            ("platform-smoke", _dispatcher("platform-smoke")),
            ("migration", _dispatcher("test-migration")),
            ("sqlite-repository-acceptance", _dispatcher("db-sqlite-repository-acceptance")),
            ("api-smoke", _dispatcher("api-smoke")),
            ("gui-smoke-headless", _dispatcher("gui-smoke", "--headless")),
            ("desktop-backend-smoke", _dispatcher("desktop-backend-smoke")),
            ("ui-automation-smoke", _dispatcher("ui-automation-smoke")),
            ("package-smoke", _dispatcher("package-smoke")),
            ("uv-lock-check-offline", [shutil.which("uv") or "uv", "lock", "--check", "--offline"]),
            ("git-diff-check", ["git", "diff", "--check"]),
            ("git-diff-exit-code", ["git", "diff", "--exit-code"]),
        )
        command_list = list(commands)
        if os.environ.get("TPAA_COLD_START_INNER") != "1":
            cold_evidence = f"evidence/devops/{actual_platform}/cold-start.json"
            command_list.append(
                (
                    "cold-start",
                    _dispatcher(
                        "cold-start",
                        "--expected-platform",
                        actual_platform,
                        "--evidence",
                        cold_evidence,
                    ),
                )
            )
        for name, command in command_list:
            gates.append(_run_gate(name, command))
            if name == "sqlite-repository-acceptance":
                gates.append(_sqlite_bootstrap_gate())

    failed = [gate for gate in gates if gate["status"] != "PASS"]
    status = "FAIL" if preflight_failure or failed else "PASS"
    payload: dict[str, object] = {
        "schema": "TPAA_M0_CROSS_PLATFORM_CI_EVIDENCE_V1",
        "tasks": ["M0-PLAT-004", "M0-PLAT-005", "M1-TST-001", "M1-DATA-001", "M1-DATA-002", "M1-DATA-003", "M1-DATA-004", "M1-DATA-005", "M1-DATA-006", "M1-DATA-007", "M1-WORLD-001"],
        "status": status,
        "preflight_failure": preflight_failure,
        "source_revision": _git_revision(),
        "platform": {
            "logical": actual_platform,
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "uv": _capture([shutil.which("uv") or "uv", "--version"]),
        "runner": {
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "runner_os": os.environ.get("RUNNER_OS"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
        },
        "started_at_utc": started_at,
        "finished_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "required_gates": gates,
        "failed_gate_names": [str(gate["name"]) for gate in failed],
        "scope": {
            "included": "SDIB-1.0.1 Windows/Linux CI over implemented M0 gates plus M1-TST-001 fixture validation, M1-DATA-001 source-adapter validation, M1-DATA-002 immutable registry validation, M1-DATA-003 explicit Session Time validation, M1-DATA-004 replay-stable aircraft identity validation, M1-DATA-005 Canonical flight-channel validation, M1-DATA-006 immutable Evaluation Context validation, and M1-DATA-007 lineage/quality propagation validation, plus M1-WORLD-001 replay-stable Basic Episode validation, package/SBOM/cold-start",
            "excluded": [
                "M0 Exit Gate",
                "M1-C execution beyond M1-WORLD-001; Stage/World-product/Metric/Release production execution",
                "real PostgreSQL server acceptance is retained from M0-STO-003 and is not redefined by this runner task",
            ],
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if evidence is not None:
        _write_evidence(evidence, payload)
        print(f"CI_EVIDENCE_WRITTEN {evidence}")
    return 0 if status == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-platform", choices=("windows", "linux"))
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    return run(expected_platform=args.expected_platform, evidence=args.evidence)


if __name__ == "__main__":
    raise SystemExit(main())
