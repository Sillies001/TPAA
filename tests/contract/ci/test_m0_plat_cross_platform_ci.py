from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFY_PATH = REPO_ROOT / "tools" / "ci" / "verify_ci.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
DISPATCHER = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
GATE_RUNNER = REPO_ROOT / "tools" / "ci" / "run_gate.py"


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location("tpaa_ci_verify", VERIFY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_orchestration_contract_passes() -> None:
    verifier = _load_verifier()
    result = verifier.verify()
    assert result["status"] == "PASS", json.dumps(result, indent=2)


def test_workflow_is_real_windows_and_linux_matrix() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runner: ubuntu-24.04" in text
    assert "runner: windows-2025" in text
    assert "fail-fast: false" in text
    assert "macos" not in text.lower()


def test_workflow_calls_one_governed_ci_gate_command() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py ci-check" in text
    assert "--expected-platform ${{ matrix.platform }}" in text
    assert "continue-on-error" not in text
    assert "|| true" not in text


def test_dispatcher_exposes_step8_commands() -> None:
    text = DISPATCHER.read_text(encoding="utf-8")
    assert 'CommandSpec("verify-ci", "M0-PLAT-004/M0-PLAT-005", "IMPLEMENTED"' in text
    assert 'CommandSpec("ci-check", "M0-PLAT-004/M0-PLAT-005", "IMPLEMENTED"' in text


def test_ci_gate_contains_formal_step8_minimum_and_current_required_gates() -> None:
    text = GATE_RUNNER.read_text(encoding="utf-8")
    required = (
        '_dispatcher("bootstrap", "--check-only")',
        '_dispatcher("test-unit")',
        '_dispatcher("verify-governance")',
        '_dispatcher("test-contract")',
        '_dispatcher("test-golden")',
        '_dispatcher("test-replay")',
        '_dispatcher("test-e2e")',
        '_dispatcher("api-smoke")',
        '_dispatcher("gui-smoke", "--headless")',
        '_dispatcher("ui-automation-smoke")',
        '_dispatcher("verify-baseline")',
        '_dispatcher("verify-generated")',
        '_dispatcher("verify-architecture")',
        '_dispatcher("lint")',
        '_dispatcher("typecheck")',
    )
    for token in required:
        assert token in text


def test_ci_gate_does_not_dispatch_later_step_work() -> None:
    text = GATE_RUNNER.read_text(encoding="utf-8")
    for token in (
        '_dispatcher("package")',
        '_dispatcher("manifest")',
        '_dispatcher("cold-start")',
    ):
        assert token not in text


def test_linux_runner_installs_required_qt_egl_runtime() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: ${{ matrix.platform == 'linux' }}" in text
    assert "sudo apt-get update && sudo apt-get install --no-install-recommends -y libegl1" in text


def test_pytest_and_mypy_resolve_repository_tool_packages() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["pytest"]["ini_options"]["pythonpath"] == [".", "src"]
    mypy = config["tool"]["mypy"]
    assert mypy["explicit_package_bases"] is True
    assert mypy["mypy_path"] == ["src", "."]
    assert mypy["files"] == ["tools", "src"]
    assert "tests" not in mypy["files"]


def test_step9_fixture_and_logical_equivalence_are_fail_closed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py fixture-check" in text
    assert "--evidence evidence/tests/framework-${{ matrix.platform }}.json" in text
    assert "python tools/dev/tpaa_dev.py platform-logical-product" in text
    assert "--output evidence/cross-platform/${{ matrix.platform }}.json" in text
    assert "m0-logical-equivalence:" in text
    assert "needs: m0-cross-platform" in text
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in text
    assert "python tools/dev/tpaa_dev.py compare-platform-logical" in text
    assert "--windows downloaded/cross-platform/windows.json" in text
    assert "--linux downloaded/cross-platform/linux.json" in text
    assert "--evidence evidence/cross-platform/logical-equivalence.json" in text
