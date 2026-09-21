#!/usr/bin/env python3
"""Cross-platform developer command dispatcher for TPAA M0.

The dispatcher is intentionally standard-library-only. Project dependencies and
quality tools are executed through the frozen toolchain contract rather than
being imported by this bootstrap script.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN_PATH = REPO_ROOT / "tools" / "dev" / "TOOLCHAIN.json"
BASELINE_VERIFY = REPO_ROOT / "tools" / "baseline" / "verify_baseline.py"
CANONICAL_VERIFY = REPO_ROOT / "tools" / "canonical" / "verify_loader.py"
CODEGEN_GENERATE = REPO_ROOT / "tools" / "codegen" / "generate.py"
CODEGEN_VERIFY_GENERATED = REPO_ROOT / "tools" / "codegen" / "verify_generated.py"
CODEGEN_REGENERATE_DIFF = REPO_ROOT / "tools" / "codegen" / "regenerate_diff.py"
ARCHITECTURE_VERIFY = REPO_ROOT / "tools" / "architecture" / "verify_dependencies.py"
STORAGE_BOOTSTRAP = REPO_ROOT / "tools" / "storage" / "bootstrap_db.py"
POSTGRES_STORAGE = REPO_ROOT / "tools" / "storage" / "postgres_db.py"

EXIT_OK = 0
EXIT_FAILURE = 2
EXIT_NOT_IMPLEMENTED = 3


@dataclass(frozen=True)
class CommandSpec:
    name: str
    milestone_task: str
    state: str
    description: str


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("bootstrap", "M0-DEV-001", "IMPLEMENTED", "Validate runtime/lock/baseline and sync the frozen project environment."),
    CommandSpec("generate", "M0-CORE-003", "IMPLEMENTED", "Generate deterministic projections from Canonical authorities."),
    CommandSpec("verify-generated", "M0-CORE-004", "IMPLEMENTED", "Verify exact generated tree and provenance without rewriting it."),
    CommandSpec("regenerate-diff", "M0-CORE-004", "IMPLEMENTED", "Regenerate and require zero Git diff for governed generated source."),
    CommandSpec("verify-architecture", "M0-CORE-005", "IMPLEMENTED", "Verify SDIB package/layer dependency direction using the static architecture gate."),
    CommandSpec("verify-baseline", "M0-CORE-001", "IMPLEMENTED", "Verify BASELINE_LOCK and controlled Canonical artifact hashes."),
    CommandSpec("verify-canonical", "M0-CORE-002", "IMPLEMENTED", "Verify Canonical loader compatibility and fail-closed contracts."),
    CommandSpec("db-bootstrap", "M0-STO-001", "IMPLEMENTED", "Bootstrap an empty SQLite Desktop DB from frozen schema 1.6.0 authority."),
    CommandSpec("db-verify", "M0-STO-001", "IMPLEMENTED", "Verify SQLite schema/version/provenance against frozen schema 1.6.0 authority."),
    CommandSpec("db-postgres-bootstrap", "M0-STO-001", "IMPLEMENTED", "Bootstrap PostgreSQL through the repository-controlled external psql harness."),
    CommandSpec("db-postgres-verify", "M0-STO-001", "IMPLEMENTED", "Verify PostgreSQL schema/version/provenance through the external psql harness."),
    CommandSpec("db-postgres-acceptance", "M0-STO-001", "IMPLEMENTED", "Run destructive M0-STO-001 PostgreSQL acceptance in a dedicated disposable database."),
    CommandSpec("format", "ADR-M0-003", "IMPLEMENTED", "Run the frozen Ruff formatter."),
    CommandSpec("lint", "ADR-M0-003", "IMPLEMENTED", "Run the frozen Ruff linter."),
    CommandSpec("typecheck", "ADR-M0-003", "IMPLEMENTED", "Run the frozen mypy type checker."),
    CommandSpec("test", "M0-TST-001", "IMPLEMENTED", "Run the current repository test suite."),
    CommandSpec("test-unit", "M0-TST-001", "IMPLEMENTED", "Run unit tests."),
    CommandSpec("test-contract", "M0-TST-001", "IMPLEMENTED", "Run contract tests."),
    CommandSpec("test-golden", "M0-TST-001", "IMPLEMENTED", "Run Golden tests."),
    CommandSpec("test-replay", "M0-TST-001", "IMPLEMENTED", "Run replay tests."),
    CommandSpec("test-migration", "M0-TST-001", "IMPLEMENTED", "Run migration tests."),
    CommandSpec("test-e2e", "M0-TST-001", "IMPLEMENTED", "Run end-to-end tests."),
    CommandSpec("run", "M0-API-002/M0-GUI-001", "RESERVED", "Dispatch an API or GUI runtime profile."),
    CommandSpec("run-api", "M0-API-002", "RESERVED", "Start the API profile once implemented."),
    CommandSpec("run-gui", "M0-GUI-001", "RESERVED", "Start the Desktop GUI profile once implemented."),
    CommandSpec("package", "M0-DEV-005", "RESERVED", "Build a platform development artifact once packaging is implemented."),
    CommandSpec("manifest", "M0-DEV-003", "RESERVED", "Generate build/package manifest and SBOM inputs."),
    CommandSpec("cold-start", "M0-DEV-006", "RESERVED", "Rebuild and execute all current milestone gates from clean state."),
    CommandSpec("doctor", "M0-DEV-001", "IMPLEMENTED", "Report runtime, resolver, lock and quality-tool availability."),
)


def _load_toolchain() -> dict[str, object]:
    data = json.loads(TOOLCHAIN_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "TPAA_M0_TOOLCHAIN_V1":
        raise RuntimeError("invalid TPAA toolchain contract")
    return data


def _run(args: Sequence[str], *, cwd: Path = REPO_ROOT) -> int:
    completed = subprocess.run(list(args), cwd=cwd, check=False)
    return completed.returncode


def _capture(args: Sequence[str], *, cwd: Path = REPO_ROOT) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return EXIT_FAILURE, str(exc)
    text = (completed.stdout or completed.stderr).strip()
    return completed.returncode, text


def _uv_executable() -> str | None:
    return shutil.which("uv")


def _version_text(executable: str, module: bool = False) -> str | None:
    args = [sys.executable, "-m", executable, "--version"] if module else [executable, "--version"]
    code, output = _capture(args)
    return output if code == 0 else None


def _quality_tool_command(tool: str, version: str, args: Sequence[str]) -> list[str]:
    executable = shutil.which(tool)
    if executable:
        code, output = _capture([executable, "--version"])
        if code == 0 and version in output:
            return [executable, *args]
    if tool == "pytest":
        code, output = _capture([sys.executable, "-m", "pytest", "--version"])
        if code == 0 and version in output:
            return [sys.executable, "-m", "pytest", *args]
    uv = _uv_executable()
    if uv is None:
        raise RuntimeError(f"{tool} {version} unavailable and uv is not on PATH")
    return [uv, "tool", "run", "--from", f"{tool}=={version}", tool, *args]


def _quality_version(tool: str, version: str) -> tuple[str, str]:
    """Report locally available exact tools without causing network access."""
    executable = shutil.which(tool)
    if executable:
        code, output = _capture([executable, "--version"])
        if code == 0 and version in output:
            return "READY", output
        if code == 0:
            return "VERSION_MISMATCH", output
    if tool == "pytest":
        code, output = _capture([sys.executable, "-m", "pytest", "--version"])
        if code == 0 and version in output:
            return "READY", output
        if code == 0:
            return "VERSION_MISMATCH", output
    return "UNAVAILABLE", f"{tool} {version} is not installed in the current execution environment"


def _runtime_check() -> tuple[bool, str]:
    actual = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 13)
    return ok, f"CPython {actual}" if sys.implementation.name == "cpython" else f"{sys.implementation.name} {actual}"


def _lock_check() -> tuple[bool, str]:
    uv = _uv_executable()
    if uv is None:
        return False, "uv unavailable"
    code, output = _capture([uv, "lock", "--check", "--offline"])
    return code == 0, output or ("uv.lock matches pyproject.toml" if code == 0 else "uv lock check failed")


def _baseline_check() -> int:
    return _run([sys.executable, str(BASELINE_VERIFY)])


def cmd_list(as_json: bool) -> int:
    payload = [spec.__dict__ for spec in COMMANDS]
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        width = max(len(item.name) for item in COMMANDS)
        for item in COMMANDS:
            print(f"{item.name:<{width}}  {item.state:<11}  {item.milestone_task:<22}  {item.description}")
    return EXIT_OK


def cmd_doctor(strict: bool) -> int:
    toolchain = _load_toolchain()
    runtime_ok, runtime_text = _runtime_check()
    lock_ok, lock_text = _lock_check()
    uv = _uv_executable()
    uv_text = _version_text(uv) if uv else None
    quality = toolchain["quality"]
    assert isinstance(quality, dict)
    report: dict[str, object] = {
        "runtime": {"status": "READY" if runtime_ok else "FAIL", "actual": runtime_text},
        "resolver": {"status": "READY" if uv else "FAIL", "actual": uv_text or "uv unavailable"},
        "dependency_lock": {"status": "READY" if lock_ok else "FAIL", "detail": lock_text},
        "quality": {},
    }
    quality_report = report["quality"]
    assert isinstance(quality_report, dict)
    all_quality_ready = True
    for role, raw in quality.items():
        assert isinstance(raw, dict)
        tool = str(raw["tool"])
        version = str(raw["version"])
        status, detail = _quality_version(tool, version)
        quality_report[role] = {"status": status, "tool": tool, "version": version, "detail": detail}
        all_quality_ready = all_quality_ready and status == "READY"
    print(json.dumps(report, indent=2, sort_keys=True))
    core_ready = runtime_ok and bool(uv) and lock_ok
    return EXIT_OK if core_ready and (all_quality_ready or not strict) else EXIT_FAILURE


def cmd_bootstrap(check_only: bool, with_quality_tools: bool) -> int:
    runtime_ok, runtime_text = _runtime_check()
    if not runtime_ok:
        print(f"BOOTSTRAP_FAIL runtime expected=CPython-3.13.x actual={runtime_text}", file=sys.stderr)
        return EXIT_FAILURE
    uv = _uv_executable()
    if uv is None:
        print("BOOTSTRAP_FAIL uv not found", file=sys.stderr)
        return EXIT_FAILURE
    lock_ok, lock_text = _lock_check()
    if not lock_ok:
        print(f"BOOTSTRAP_FAIL dependency_lock {lock_text}", file=sys.stderr)
        return EXIT_FAILURE
    if _baseline_check() != 0:
        print("BOOTSTRAP_FAIL baseline verify", file=sys.stderr)
        return EXIT_FAILURE
    if not check_only and _run([uv, "sync", "--frozen", "--offline"]) != 0:
        print("BOOTSTRAP_FAIL uv sync --frozen --offline", file=sys.stderr)
        return EXIT_FAILURE
    if with_quality_tools:
        return cmd_doctor(strict=True)
    print("BOOTSTRAP_PASS runtime+dependency-lock+baseline")
    return EXIT_OK


def cmd_quality(role: str, extra: Sequence[str]) -> int:
    toolchain = _load_toolchain()
    quality = toolchain["quality"]
    assert isinstance(quality, dict)
    raw = quality[role]
    assert isinstance(raw, dict)
    tool = str(raw["tool"])
    version = str(raw["version"])
    if role == "formatter":
        args = ["format", *extra, "tools", "tests", "src"]
    elif role == "linter":
        args = ["check", *extra, "tools", "tests", "src"]
    elif role == "type_checker":
        args = [*extra]
    else:
        raise RuntimeError(f"unsupported quality role {role}")
    try:
        command = _quality_tool_command(tool, version, args)
    except RuntimeError as exc:
        print(f"QUALITY_TOOL_FAIL {exc}", file=sys.stderr)
        return EXIT_FAILURE
    return _run(command)


def cmd_test(path: str | None) -> int:
    toolchain = _load_toolchain()
    quality = toolchain["quality"]
    assert isinstance(quality, dict)
    raw = quality["test_runner"]
    assert isinstance(raw, dict)
    tool = str(raw["tool"])
    version = str(raw["version"])
    args = [path] if path else ["tests"]
    try:
        command = _quality_tool_command(tool, version, args)
    except RuntimeError as exc:
        print(f"TEST_TOOL_FAIL {exc}", file=sys.stderr)
        return EXIT_FAILURE
    return _run(command)


def _reserved(task: str, command: str) -> int:
    print(
        f"NOT_IMPLEMENTED command={command} controlling_task={task}; "
        "the developer command is reserved but fails closed until that SDIB task is implemented.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TPAA unified developer command dispatcher")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List developer commands and implementation state")
    list_parser.add_argument("--json", action="store_true")

    bootstrap = sub.add_parser("bootstrap", help="Validate/sync the frozen development substrate")
    bootstrap.add_argument("--check-only", action="store_true", help="Do not modify .venv")
    bootstrap.add_argument(
        "--with-quality-tools",
        action="store_true",
        help="Also require exact Ruff/mypy/pytest versions (may need network/cache)",
    )

    sub.add_parser("verify-baseline", help="Verify frozen Canonical baseline")
    sub.add_parser("verify-canonical", help="Verify M0-CORE-002 Canonical loader contract")
    sub.add_parser("doctor", help="Report toolchain state").add_argument("--strict", action="store_true")
    generate = sub.add_parser("generate", help="Generate deterministic Canonical projections")
    generate.add_argument("--check", action="store_true", help="Fail if checked-in generated tree/provenance differs")
    sub.add_parser("verify-generated", help="Verify governed generated tree without rewriting")
    sub.add_parser("regenerate-diff", help="Regenerate generated source and require zero Git diff")
    sub.add_parser("verify-architecture", help="Verify SDIB package/layer architecture dependencies")
    db_bootstrap = sub.add_parser("db-bootstrap", help="Bootstrap empty SQLite Desktop DB to schema 1.6.0")
    db_bootstrap.add_argument("database", type=Path)
    db_verify = sub.add_parser("db-verify", help="Verify SQLite Desktop DB schema/version/provenance")
    db_verify.add_argument("database", type=Path)

    def add_postgres_client_args(command: argparse.ArgumentParser) -> None:
        command.add_argument("--user", default="tpaa")
        command.add_argument("--host")
        command.add_argument("--port", type=int)
        command.add_argument("--psql", default="psql")
        command.add_argument("--docker-container")

    pg_bootstrap = sub.add_parser("db-postgres-bootstrap", help="Bootstrap PostgreSQL schema 1.6.0 through external psql")
    add_postgres_client_args(pg_bootstrap)
    pg_bootstrap.add_argument("database")
    pg_verify = sub.add_parser("db-postgres-verify", help="Verify PostgreSQL schema/version/provenance through external psql")
    add_postgres_client_args(pg_verify)
    pg_verify.add_argument("database")
    pg_acceptance = sub.add_parser("db-postgres-acceptance", help="Run destructive PostgreSQL M0-STO-001 acceptance in a disposable database")
    add_postgres_client_args(pg_acceptance)
    pg_acceptance.add_argument("--admin-database", default="postgres")
    pg_acceptance.add_argument("--database", default="tpaa_m0_sto_001_acceptance")

    fmt = sub.add_parser("format", help="Run Ruff formatter")
    fmt.add_argument("--check", action="store_true")
    sub.add_parser("lint", help="Run Ruff linter")
    sub.add_parser("typecheck", help="Run mypy")

    for name in ("test", "test-unit", "test-contract", "test-golden", "test-replay", "test-migration", "test-e2e"):
        sub.add_parser(name, help=f"Run {name} suite")

    run = sub.add_parser("run", help="Dispatch runtime target")
    run.add_argument("target", choices=("api", "gui"))
    sub.add_parser("run-api", help="Reserved for M0-API-002")
    sub.add_parser("run-gui", help="Reserved for M0-GUI-001")
    sub.add_parser("package", help="Reserved for M0-DEV-005")
    sub.add_parser("manifest", help="Reserved for M0-DEV-003")
    sub.add_parser("cold-start", help="Reserved for M0-DEV-006")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if command == "list":
        return cmd_list(args.json)
    if command == "bootstrap":
        return cmd_bootstrap(args.check_only, args.with_quality_tools)
    if command == "verify-baseline":
        return _baseline_check()
    if command == "verify-canonical":
        return _run([sys.executable, str(CANONICAL_VERIFY)])
    if command == "doctor":
        return cmd_doctor(args.strict)
    if command == "format":
        return cmd_quality("formatter", ["--check"] if args.check else [])
    if command == "lint":
        return cmd_quality("linter", [])
    if command == "typecheck":
        return cmd_quality("type_checker", [])
    if command == "test":
        return cmd_test(None)
    suite_paths = {
        "test-unit": "tests/unit",
        "test-contract": "tests/contract",
        "test-golden": "tests/golden",
        "test-replay": "tests/replay",
        "test-migration": "tests/migration",
        "test-e2e": "tests/e2e",
    }
    if command in suite_paths:
        return cmd_test(suite_paths[command])
    if command == "generate":
        args_out = [sys.executable, str(CODEGEN_GENERATE)]
        if args.check:
            args_out.append("--check")
        return _run(args_out)
    if command == "verify-generated":
        return _run([sys.executable, str(CODEGEN_VERIFY_GENERATED)])
    if command == "regenerate-diff":
        return _run([sys.executable, str(CODEGEN_REGENERATE_DIFF)])
    if command == "verify-architecture":
        return _run([sys.executable, str(ARCHITECTURE_VERIFY)])
    if command == "db-bootstrap":
        return _run([sys.executable, str(STORAGE_BOOTSTRAP), "bootstrap", str(args.database)])
    if command == "db-verify":
        return _run([sys.executable, str(STORAGE_BOOTSTRAP), "verify", str(args.database)])
    if command in {"db-postgres-bootstrap", "db-postgres-verify", "db-postgres-acceptance"}:
        pg_args = [sys.executable, str(POSTGRES_STORAGE)]
        if args.user:
            pg_args.extend(["--user", args.user])
        if args.host:
            pg_args.extend(["--host", args.host])
        if args.port is not None:
            pg_args.extend(["--port", str(args.port)])
        if args.psql:
            pg_args.extend(["--psql", args.psql])
        if args.docker_container:
            pg_args.extend(["--docker-container", args.docker_container])
        if command == "db-postgres-acceptance":
            pg_args.extend(["acceptance", "--admin-database", args.admin_database, "--database", args.database])
        else:
            action = "bootstrap" if command == "db-postgres-bootstrap" else "verify"
            pg_args.extend([action, args.database])
        return _run(pg_args)
    if command == "run":
        return _reserved("M0-API-002" if args.target == "api" else "M0-GUI-001", f"run {args.target}")
    reserved = {
        "run-api": "M0-API-002",
        "run-gui": "M0-GUI-001",
        "package": "M0-DEV-005",
        "manifest": "M0-DEV-003",
        "cold-start": "M0-DEV-006",
    }
    if command in reserved:
        return _reserved(reserved[command], command)
    parser.error(f"unknown command: {command}")
    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
