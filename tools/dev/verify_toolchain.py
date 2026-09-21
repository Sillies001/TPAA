#!/usr/bin/env python3
"""Verify the M0 toolchain decisions and emit machine-readable evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS = ["M0-DEV-001", "M0-DEV-002"]
ADRS = ["ADR-M0-001", "ADR-M0-002", "ADR-M0-003"]
REQUIRED_COMMANDS = {
    "bootstrap",
    "generate",
    "verify-baseline",
    "test-unit",
    "test-contract",
    "test-golden",
    "test-replay",
    "test-migration",
    "test-e2e",
    "run-api",
    "run-gui",
    "package",
    "manifest",
    "cold-start",
}
KEY_FILES = [
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    "tools/dev/TOOLCHAIN.json",
    "tools/dev/tpaa_dev.py",
    "docs/adr/ADR-M0-001-python-runtime-baseline.md",
    "docs/adr/ADR-M0-002-dependency-resolver-lock.md",
    "docs/adr/ADR-M0-003-static-quality-toolchain.md",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(args: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 2, str(exc)
    text = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    return completed.returncode, text


def _git_revision() -> str:
    code, output = _run(["git", "rev-parse", "HEAD"])
    return output if code == 0 else "UNAVAILABLE"


def _tool_version(command: list[str]) -> str | None:
    code, output = _run(command)
    return output if code == 0 else None


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    pyproject_path = REPO_ROOT / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    record(
        "python_minor",
        pyproject["project"]["requires-python"] == ">=3.13,<3.14"
        and (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.13",
        "requires-python=>=3.13,<3.14; .python-version=3.13",
    )

    uv_required = pyproject["tool"]["uv"]["required-version"]
    record("resolver", uv_required == ">=0.10,<0.13", f"uv required-version={uv_required}")

    lock_text = (REPO_ROOT / "uv.lock").read_text(encoding="utf-8")
    record(
        "canonical_lock",
        'requires-python = "==3.13.*"' in lock_text and 'name = "tpaa"' in lock_text,
        "uv.lock is present and constrained to Python 3.13",
    )
    competing = ["poetry.lock", "Pipfile.lock", "requirements.lock", "pdm.lock"]
    present_competing = [name for name in competing if (REPO_ROOT / name).exists()]
    record(
        "single_lock_authority",
        not present_competing,
        "no competing project lock" if not present_competing else ",".join(present_competing),
    )

    uv = shutil.which("uv")
    if uv:
        code, output = _run([uv, "lock", "--check", "--offline"])
        record("uv_lock_check", code == 0, output or "uv lock --check --offline")
    else:
        record("uv_lock_check", False, "uv executable unavailable")

    toolchain = json.loads((REPO_ROOT / "tools/dev/TOOLCHAIN.json").read_text(encoding="utf-8"))
    record(
        "toolchain_schema",
        toolchain.get("schema") == "TPAA_M0_TOOLCHAIN_V1" and toolchain.get("status") == "FROZEN",
        f"schema={toolchain.get('schema')} status={toolchain.get('status')}",
    )
    quality = toolchain["quality"]
    expected_quality = {
        "formatter": ("ruff", "0.16.8"),
        "linter": ("ruff", "0.16.8"),
        "type_checker": ("mypy", "2.3.1"),
        "test_runner": ("pytest", "9.0.2"),
    }
    quality_ok = all(
        quality[role]["tool"] == expected[0] and quality[role]["version"] == expected[1]
        for role, expected in expected_quality.items()
    )
    record("quality_tool_pins", quality_ok, json.dumps(expected_quality, sort_keys=True))

    dataframe = toolchain["dataframe_policy"]
    record(
        "polars_first_policy",
        dataframe["preferred_engine"] == "polars" and dataframe["pandas_default_dependency"] is False,
        "preferred_engine=polars; pandas_default_dependency=false",
    )

    cli = REPO_ROOT / "tools/dev/tpaa_dev.py"
    code, output = _run([sys.executable, str(cli), "list", "--json"])
    if code == 0:
        commands = {row["name"] for row in json.loads(output)}
        missing = sorted(REQUIRED_COMMANDS - commands)
        record(
            "developer_command_discovery",
            not missing,
            "all SDIB command semantics present" if not missing else f"missing={missing}",
        )
    else:
        record("developer_command_discovery", False, output)

    code, output = _run([sys.executable, str(cli), "bootstrap", "--check-only"])
    record("bootstrap_check_only", code == 0, output)

    adr_files = {
        "ADR-M0-001": "docs/adr/ADR-M0-001-python-runtime-baseline.md",
        "ADR-M0-002": "docs/adr/ADR-M0-002-dependency-resolver-lock.md",
        "ADR-M0-003": "docs/adr/ADR-M0-003-static-quality-toolchain.md",
    }
    for adr_id, relative in adr_files.items():
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        ok = "**Status:** CLOSED" in text and "**Owner role:**" in text and "## Decision" in text
        record(f"{adr_id}_closed", ok, relative)

    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    files = {
        relative: {
            "sha256": _sha256(REPO_ROOT / relative),
            "bytes": (REPO_ROOT / relative).stat().st_size,
        }
        for relative in KEY_FILES
    }
    environment = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "uv": _tool_version([uv, "--version"]) if uv else None,
        "pytest": _tool_version([sys.executable, "-m", "pytest", "--version"]),
        "ruff": _tool_version(["ruff", "--version"]) if shutil.which("ruff") else None,
        "mypy": _tool_version(["mypy", "--version"]) if shutil.which("mypy") else None,
    }
    return {
        "evidence_schema": "TPAA_M0_TOOLCHAIN_EVIDENCE_V1",
        "status": status,
        "generated_at_utc": _utc_now(),
        "git_revision": _git_revision(),
        "tasks": TASKS,
        "adrs": ADRS,
        "checks": checks,
        "files": files,
        "environment": environment,
        "execution_limitations": [
            "Ruff and mypy execution is not claimed when the exact frozen binaries are absent from the current offline host.",
            "Windows execution is not claimed by this Linux-host evidence; Windows CI evidence remains a later M0 gate.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    payload = verify()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.evidence:
        target = args.evidence if args.evidence.is_absolute() else REPO_ROOT / args.evidence
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
