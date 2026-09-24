from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_CLI = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
TOOLCHAIN = REPO_ROOT / "tools" / "dev" / "TOOLCHAIN.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"
UV_LOCK = REPO_ROOT / "uv.lock"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV_CLI), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_python_minor_is_frozen_to_313() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert project["project"]["requires-python"] == ">=3.13,<3.14"
    assert (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.13"


def test_uv_is_single_project_resolver_and_lock() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert project["tool"]["uv"]["required-version"] == ">=0.10,<0.13"
    assert UV_LOCK.is_file()
    lock_text = UV_LOCK.read_text(encoding="utf-8")
    assert 'requires-python = "==3.13.*"' in lock_text
    assert 'name = "tpaa"' in lock_text
    competing = ["poetry.lock", "Pipfile.lock", "requirements.lock", "pdm.lock"]
    assert not any((REPO_ROOT / name).exists() for name in competing)


def test_toolchain_decisions_are_machine_readable() -> None:
    data = json.loads(TOOLCHAIN.read_text(encoding="utf-8"))
    assert data["status"] == "FROZEN"
    assert data["python"]["minor"] == "3.13"
    assert data["dependency"]["resolver"] == "uv"
    assert data["dependency"]["canonical_lock"] == "uv.lock"
    assert data["quality"]["formatter"] == {
        "tool": "ruff",
        "version": "0.16.8",
        "command": "ruff format",
    }
    assert data["quality"]["linter"]["tool"] == "ruff"
    assert data["quality"]["type_checker"]["tool"] == "mypy"
    assert data["quality"]["test_runner"] == {
        "tool": "pytest",
        "version": "9.0.2",
        "command": "pytest",
    }
    assert data["dataframe_policy"]["preferred_engine"] == "polars"
    assert data["dataframe_policy"]["pandas_default_dependency"] is False


def test_all_sdib_developer_command_semantics_are_discoverable() -> None:
    result = _run("list", "--json")
    assert result.returncode == 0, result.stderr
    records = json.loads(result.stdout)
    names = {record["name"] for record in records}
    required = {
        "bootstrap",
        "verify-repository-bootstrap",
        "verify-m0-delta-closure",
        "verify-m1-entry-preparation",
        "verify-m1-entry-gate-state",
        "m1-entry-activation",
        "m1-entry-assign-roles",
        "verify-m1-detailed-design",
        "m1-entry-manifest",
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
    assert required <= names


def test_codegen_and_devops_commands_are_implemented_and_run_api_remains_reserved(
    tmp_path: Path,
) -> None:
    generate = _run("generate", "--check")
    assert generate.returncode == 0, generate.stderr
    assert "CODEGEN_CHECK_PASS" in generate.stdout

    profile = "WINDOWS_DESKTOP_X64" if sys.platform == "win32" else "LINUX_DESKTOP_X64"
    manifest = _run(
        "manifest",
        "--profile",
        profile,
        "--output",
        str(tmp_path / "manifest"),
    )
    assert manifest.returncode == 0, manifest.stderr
    assert (tmp_path / "manifest" / "build-manifest.json").is_file()
    assert (tmp_path / "manifest" / "sbom.cdx.json").is_file()

    package = _run(
        "package",
        "--profile",
        profile,
        "--output",
        str(tmp_path / "dist"),
    )
    assert package.returncode == 0, package.stderr
    assert any((tmp_path / "dist").glob("tpaa-0.0.0-*"))

    run_api = _run("run-api")
    assert run_api.returncode == 3
    assert "M0-API-002" in run_api.stderr


def test_baseline_verification_is_available_through_unified_cli() -> None:
    result = _run("verify-baseline")
    assert result.returncode == 0, result.stderr
    assert "PASS" in result.stdout


def test_bootstrap_check_only_passes_on_approved_runtime() -> None:
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 13):
        return
    result = _run("bootstrap", "--check-only")
    assert result.returncode == 0, result.stderr
    assert "BOOTSTRAP_PASS" in result.stdout


def test_machine_readable_toolchain_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools/dev/verify_toolchain.py")],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["tasks"] == ["M0-DEV-001", "M0-DEV-002"]
    assert evidence["adrs"] == ["ADR-M0-001", "ADR-M0-002", "ADR-M0-003"]


def test_quality_tool_fallback_runs_inside_locked_project_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("tpaa_dev_toolchain", DEV_CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    command = module._quality_tool_command("mypy", "2.3.1", [])
    assert command == [
        "/usr/bin/uv",
        "run",
        "--locked",
        "--with",
        "mypy==2.3.1",
        "mypy",
    ]
