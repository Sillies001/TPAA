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
        '_dispatcher("verify-repository-bootstrap")',
        '_dispatcher("verify-m0-delta-closure")',
        '_dispatcher("verify-governance")',
        '_dispatcher("openapi-snapshot", "--check")',
        '_dispatcher("migration-smoke")',
        '_dispatcher("backup-restore-smoke")',
        '_dispatcher("security-smoke")',
        '_dispatcher("package-smoke")',
        '"cold-start"',
        '_dispatcher("test-contract")',
        '_dispatcher("test-golden")',
        '_dispatcher("test-replay")',
        '_dispatcher("test-e2e")',
        '_dispatcher("test-platform")',
        '_dispatcher("platform-smoke")',
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


def test_ci_gate_dispatches_step10_package_and_cold_start_fail_closed() -> None:
    text = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("package-smoke")' in text
    assert '"cold-start"' in text
    assert "TPAA_COLD_START_INNER" in text


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
    assert "--windows downloaded/evidence/cross-platform/windows.json" in text
    assert "--linux downloaded/evidence/cross-platform/linux.json" in text
    assert "--evidence evidence/cross-platform/logical-equivalence.json" in text


def test_step10_workflow_archives_build_evidence_and_packages() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py manifest" in text
    assert "python tools/dev/tpaa_dev.py package" in text
    assert "evidence/devops/${{ matrix.platform }}" in text
    assert "dist/" in text


def test_m1_entry_preparation_is_fail_closed_and_archived() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py verify-m1-entry-preparation" in text
    assert "python tools/dev/tpaa_dev.py m1-entry-manifest" in text
    assert "--profile ${{ matrix.desktop_profile }}" in text
    assert "--output evidence/m1-entry/${{ matrix.platform }}/build-manifest.json" in text
    assert "evidence/m1-entry/${{ matrix.platform }}/build-manifest.json" in text


def test_m1_entry_gate_state_is_verified_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py verify-m1-entry-gate-state" in text


def test_m0_exit_postgres_and_review_jobs_are_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "m0-exit-postgres:" in text
    assert "image: postgres:16" in text
    assert "python tools/dev/tpaa_dev.py db-postgres-acceptance" in text
    assert "python tools/dev/tpaa_dev.py db-postgres-repository-acceptance" in text
    assert "python tools/ci/cold_start.py" in text
    assert "--postgres-conninfo-template" in text
    assert "m0-exit-review:" in text
    assert "needs:" in text
    assert "python tools/ci/m0_exit_review.py" in text
    assert "--output evidence/m0-exit/review.json" in text
