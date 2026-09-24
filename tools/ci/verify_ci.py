#!/usr/bin/env python3
"""Verify the governed M0-PLAT-004/005 GitHub Actions CI contract.

This verifier intentionally uses only the Python standard library.  It checks
provider orchestration constraints derived from SDIB-1.0.1 without becoming a
business-schema authority.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
TOOLCHAIN = REPO_ROOT / "tools" / "dev" / "TOOLCHAIN.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"
GATE_RUNNER = REPO_ROOT / "tools" / "ci" / "run_gate.py"

EXPECTED_PYTHON = "3.13.5"
EXPECTED_UV = "0.12.17"
EXPECTED_RUNNERS = {
    "linux": "ubuntu-24.04",
    "windows": "windows-2025",
}
EXPECTED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",  # v7.0.1
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",  # v7.0.0
    "astral-sh/setup-uv": "c18668ad3cf93ea998bef934396af7bb5c839dc7",  # v10.2.0
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",  # v7.0.1
    "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",  # v8
}


def _fail(code: str, detail: str) -> tuple[str, str, str]:
    return (code, "FAIL", detail)


def _pass(code: str, detail: str) -> tuple[str, str, str]:
    return (code, "PASS", detail)


def verify() -> dict[str, object]:
    checks: list[tuple[str, str, str]] = []
    if not WORKFLOW.is_file():
        checks.append(_fail("workflow_exists", str(WORKFLOW)))
        return {"m0_plat_004_005": checks, "status": "FAIL"}

    text = WORKFLOW.read_text(encoding="utf-8")
    gate_text = GATE_RUNNER.read_text(encoding="utf-8") if GATE_RUNNER.is_file() else ""
    toolchain = json.loads(TOOLCHAIN.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    checks.append(_pass("workflow_exists", WORKFLOW.relative_to(REPO_ROOT).as_posix()))
    checks.append(
        _pass("no_continue_on_error", "required gates fail closed")
        if "continue-on-error" not in text
        else _fail("no_continue_on_error", "continue-on-error is forbidden for this workflow")
    )
    checks.append(
        _pass("no_failure_mask", "no shell failure masking tokens")
        if "|| true" not in text
        else _fail("no_failure_mask", "found forbidden '|| true'")
    )
    checks.append(
        _pass("read_only_permissions", "contents: read")
        if re.search(r"(?m)^permissions:\s*\n\s+contents:\s+read\s*$", text)
        else _fail("read_only_permissions", "workflow must declare contents: read")
    )
    checks.append(
        _pass("matrix_fail_fast", "fail-fast: false preserves both OS evidence")
        if re.search(r"(?m)^\s+fail-fast:\s+false\s*$", text)
        else _fail("matrix_fail_fast", "matrix must use fail-fast: false")
    )

    for platform_name, runner in EXPECTED_RUNNERS.items():
        token = f"platform: {platform_name}"
        runner_token = f"runner: {runner}"
        checks.append(
            _pass(f"runner_{platform_name}", runner)
            if token in text and runner_token in text
            else _fail(f"runner_{platform_name}", f"missing {token!r} / {runner_token!r}")
        )

    checks.append(
        _pass("python_exact", EXPECTED_PYTHON)
        if f"python-version: \"{EXPECTED_PYTHON}\"" in text
        else _fail("python_exact", f"CI must pin CPython {EXPECTED_PYTHON}")
    )
    checks.append(
        _pass("uv_exact", EXPECTED_UV)
        if f"version: \"{EXPECTED_UV}\"" in text
        else _fail("uv_exact", f"CI must pin uv {EXPECTED_UV}")
    )

    uses = re.findall(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", text)
    expected_uses = {f"{name}@{sha}" for name, sha in EXPECTED_ACTIONS.items()}
    actual_uses = set(uses)
    checks.append(
        _pass("action_sha_pins", ", ".join(sorted(expected_uses)))
        if actual_uses == expected_uses
        else _fail(
            "action_sha_pins",
            f"expected={sorted(expected_uses)!r} actual={sorted(actual_uses)!r}",
        )
    )
    unpinned = [value for value in uses if not re.search(r"@[0-9a-f]{40}$", value)]
    checks.append(
        _pass("all_actions_immutable", "all uses: references are full commit SHAs")
        if not unpinned
        else _fail("all_actions_immutable", f"unpinned actions: {unpinned!r}")
    )

    required_tokens = (
        "if: ${{ matrix.platform == 'linux' }}",
        "sudo apt-get update && sudo apt-get install --no-install-recommends -y libegl1",
        "uv sync --locked --python 3.13.5",
        "uv lock --check",
        "python tools/dev/tpaa_dev.py verify-ci",
        "python tools/dev/tpaa_dev.py ci-check",
        "--expected-platform ${{ matrix.platform }}",
        "--evidence evidence/ci/${{ matrix.platform }}.json",
        "python tools/dev/tpaa_dev.py fixture-check",
        "--evidence evidence/tests/framework-${{ matrix.platform }}.json",
        "python tools/dev/tpaa_dev.py platform-logical-product",
        "--output evidence/cross-platform/${{ matrix.platform }}.json",
        "needs: m0-cross-platform",
        "python tools/dev/tpaa_dev.py compare-platform-logical",
        "--windows downloaded/evidence/cross-platform/windows.json",
        "--linux downloaded/evidence/cross-platform/linux.json",
        "--evidence evidence/cross-platform/logical-equivalence.json",
        "python tools/dev/tpaa_dev.py manifest",
        "python tools/dev/tpaa_dev.py verify-m1-entry-preparation",
        "python tools/dev/tpaa_dev.py verify-m1-entry-gate-state",
        "python tools/dev/tpaa_dev.py verify-m1-detailed-design",
        "python tools/dev/tpaa_dev.py m1-fixture-check",
        "python tools/dev/tpaa_dev.py m1-source-adapter-check",
        "--evidence evidence/m1-data-001/${{ matrix.platform }}/source-adapter.json",
        "python tools/dev/tpaa_dev.py m1-source-registry-check",
        "--evidence evidence/m1-data-002/${{ matrix.platform }}/source-registry.json",
        "python tools/dev/tpaa_dev.py m1-session-time-check",
        "--evidence evidence/m1-data-003/${{ matrix.platform }}/session-time.json",
        "--evidence evidence/m1-fixtures/${{ matrix.platform }}/fixture-evidence.json",
        "python tools/dev/tpaa_dev.py m1-entry-manifest",
        "--output evidence/m1-entry/${{ matrix.platform }}/build-manifest.json",
        "- name: Verify or activate M1 Entry",
        "python tools/dev/tpaa_dev.py m1-entry-activation",
        "--mode auto",
        "--event-name ${{ github.event_name }}",
        "--git-ref ${{ github.ref }}",
        "--source-revision ${{ github.sha }}",
        "--windows-manifest downloaded/platform/evidence/m1-entry/windows/build-manifest.json",
        "--linux-manifest downloaded/platform/evidence/m1-entry/linux/build-manifest.json",
        "--output evidence/m1-entry/activation.json",
        "tpaa-m1-entry-activation-${{ github.sha }}",
        "python tools/dev/tpaa_dev.py package",
        "evidence/devops/${{ matrix.platform }}",
        "evidence/m1-entry/${{ matrix.platform }}/build-manifest.json",
        "evidence/m1-fixtures/${{ matrix.platform }}/fixture-evidence.json",
        "evidence/m1-data-001/${{ matrix.platform }}/source-adapter.json",
        "evidence/m1-data-002/${{ matrix.platform }}/source-registry.json",
        "evidence/m1-data-003/${{ matrix.platform }}/session-time.json",
        "dist/",
        "m0-exit-postgres:",
        "image: postgres:16",
        "python tools/dev/tpaa_dev.py db-postgres-acceptance",
        "python tools/dev/tpaa_dev.py db-postgres-repository-acceptance",
        "python tools/ci/cold_start.py",
        "--postgres-conninfo-template",
        "m0-exit-review:",
        "python tools/ci/m0_exit_review.py",
        "--output evidence/m0-exit/review.json",
        "if: ${{ always() }}",
    )
    for token in required_tokens:
        code = "workflow_command_" + re.sub(r"[^a-z0-9]+", "_", token.lower()).strip("_")[:48]
        checks.append(
            _pass(code, token) if token in text else _fail(code, f"missing workflow token: {token}")
        )

    required_gate_tokens = (
        '_dispatcher("verify-baseline")',
        '_dispatcher("bootstrap", "--check-only")',
        '_dispatcher("verify-canonical")',
        '_dispatcher("generate", "--check")',
        '_dispatcher("verify-generated")',
        '_dispatcher("regenerate-diff")',
        '_dispatcher("verify-architecture")',
        '_dispatcher("verify-repository-policy")',
        '_dispatcher("verify-desktop-lifecycle-policy")',
        '_dispatcher("verify-repository-bootstrap")',
        '_dispatcher("verify-m0-delta-closure")',
        '_dispatcher("m1-fixture-check")',
        '_dispatcher("m1-source-adapter-check")',
        '_dispatcher("m1-source-registry-check")',
        '_dispatcher("m1-session-time-check")',
        '_dispatcher("verify-governance")',
        '_dispatcher("openapi-snapshot", "--check")',
        '_dispatcher("migration-smoke")',
        '_dispatcher("backup-restore-smoke")',
        '_dispatcher("security-smoke")',
        '_dispatcher("package-smoke")',
        '"cold-start"',
        '_dispatcher("lint")',
        '_dispatcher("typecheck")',
        '_dispatcher("test-unit")',
        '_dispatcher("test-contract")',
        '_dispatcher("test-golden")',
        '_dispatcher("test-replay")',
        '_dispatcher("test-e2e")',
        '_dispatcher("test-platform")',
        '_dispatcher("platform-smoke")',
        '_dispatcher("test-migration")',
        '_dispatcher("db-sqlite-repository-acceptance")',
        '_dispatcher("api-smoke")',
        '_dispatcher("gui-smoke", "--headless")',
        '_dispatcher("desktop-backend-smoke")',
        '_dispatcher("ui-automation-smoke")',
    )
    missing_gate_tokens = [token for token in required_gate_tokens if token not in gate_text]
    checks.append(
        _pass("governed_gate_set", f"required tokens={len(required_gate_tokens)}")
        if not missing_gate_tokens
        else _fail("governed_gate_set", f"missing gate tokens: {missing_gate_tokens!r}")
    )

    checks.append(
        _pass("step10_devops_active", "package-smoke and cold-start are governed")
        if '_dispatcher("package-smoke")' in gate_text and '"cold-start"' in gate_text
        else _fail("step10_devops_active", "Step 10 package/cold-start gates missing")
    )

    quality = toolchain.get("quality")
    quality_ok = isinstance(quality, dict) and quality.get("linter") == {
        "tool": "ruff",
        "version": "0.16.8",
        "command": "ruff check",
    } and quality.get("type_checker") == {
        "tool": "mypy",
        "version": "2.3.1",
        "command": "mypy",
    }
    checks.append(
        _pass("quality_authority", "workflow delegates exact Ruff/mypy versions to TOOLCHAIN.json")
        if quality_ok
        else _fail("quality_authority", "unexpected frozen quality-tool contract")
    )

    pytest_pythonpath = pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("pythonpath")
    checks.append(
        _pass("pytest_repo_root_importable", repr(pytest_pythonpath))
        if pytest_pythonpath == [".", "src"]
        else _fail("pytest_repo_root_importable", f"expected=['.', 'src'] actual={pytest_pythonpath!r}")
    )
    mypy_config = pyproject.get("tool", {}).get("mypy", {})
    mypy_explicit_bases = mypy_config.get("explicit_package_bases")
    checks.append(
        _pass("mypy_explicit_package_bases", "true")
        if mypy_explicit_bases is True
        else _fail("mypy_explicit_package_bases", f"expected=true actual={mypy_explicit_bases!r}")
    )
    mypy_path = mypy_config.get("mypy_path")
    checks.append(
        _pass("mypy_repository_path", repr(mypy_path))
        if mypy_path == ["src", "."]
        else _fail("mypy_repository_path", f"expected=['src', '.'] actual={mypy_path!r}")
    )
    mypy_files = mypy_config.get("files")
    checks.append(
        _pass("mypy_governed_scope", repr(mypy_files))
        if mypy_files == ["tools", "src"]
        else _fail("mypy_governed_scope", f"expected=['tools', 'src'] actual={mypy_files!r}")
    )

    status = "PASS" if all(check[1] == "PASS" for check in checks) else "FAIL"
    return {"m0_plat_004_005": checks, "status": status}


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
