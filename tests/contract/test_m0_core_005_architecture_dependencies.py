from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_CLI = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
VERIFY = REPO_ROOT / "tools" / "architecture" / "verify_dependencies.py"
SRC = REPO_ROOT / "src"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_current_repository_architecture_gate_passes() -> None:
    result = _run(sys.executable, str(VERIFY))
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task_id"] == "M0-CORE-005"
    assert evidence["violation_count"] == 0
    assert all(check["status"] == "PASS" for check in evidence["checks"])
    assert evidence["semantic_constraints_not_proven_by_import_scan"]


def test_unified_developer_command_exposes_architecture_gate() -> None:
    listed = _run(sys.executable, str(DEV_CLI), "list", "--json")
    records = json.loads(listed.stdout)
    state = {row["name"]: row["state"] for row in records}
    assert state["verify-architecture"] == "IMPLEMENTED"

    result = _run(sys.executable, str(DEV_CLI), "verify-architecture")
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout


def _fault_inject(package: str, text: str, expected_reason: str) -> None:
    target_dir = SRC / package
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "_m0_core_005_fault.py"
    assert not target.exists()
    try:
        target.write_text(text, encoding="utf-8", newline="\n")
        result = _run(sys.executable, str(DEV_CLI), "verify-architecture")
        assert result.returncode == 2
        evidence = json.loads(result.stdout)
        assert evidence["status"] == "FAIL"
        assert expected_reason in {item["reason"] for item in evidence["violations"]}
    finally:
        target.unlink(missing_ok=True)


def test_fault_injection_lower_layer_to_gui_fails_closed() -> None:
    _fault_inject("tpaa_metric", "import tpaa_gui\n", "LOWER_LAYER_TRANSPORT_DEPENDENCY")


def test_fault_injection_lower_layer_to_api_fails_closed() -> None:
    _fault_inject("tpaa_world", "from tpaa_api import routes\n", "LOWER_LAYER_TRANSPORT_DEPENDENCY")


def test_fault_injection_business_core_to_platform_fails_closed() -> None:
    _fault_inject(
        "tpaa_application",
        "from tpaa_platform import native\n",
        "BUSINESS_CORE_PLATFORM_IMPLEMENTATION_DEPENDENCY",
    )


def test_fault_injection_api_to_storage_fails_closed() -> None:
    _fault_inject("tpaa_api", "import tpaa_storage\n", "FORBIDDEN_FIRST_PARTY_DEPENDENCY")


def test_fault_injection_canonical_to_fastapi_fails_closed() -> None:
    _fault_inject("tpaa_canonical", "import fastapi\n", "FORBIDDEN_EXTERNAL_DEPENDENCY")
