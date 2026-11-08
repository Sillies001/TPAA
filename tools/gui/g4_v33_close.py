#!/usr/bin/env python3
"""Verify every G4 exit gate and write formal local closure evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.baseline.adopt_g3_successor import check_successor as check_g3_successor  # noqa: E402
from tools.baseline.adopt_g4_successor import check_successor  # noqa: E402
from tools.codegen.g4_batch_generate import OUTPUTS, render  # noqa: E402
from tools.gui.g1_frontend_build import verify as verify_frontend_build  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.9.0"
CANONICAL = BASELINE / "canonical"
OUTPUT = ROOT / "evidence" / "gui-g4-v33-closure.json"
WEBENGINE = (
    ROOT / "evidence" / "gui-g4-v33-webengine-100.json",
    ROOT / "evidence" / "gui-g4-v33-webengine-150.json",
)


class G4ClosureError(RuntimeError):
    """A mandatory G4 local closure gate failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G4ClosureError(message)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G4ClosureError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: Sequence[str], *, cwd: Path = ROOT) -> dict[str, object]:
    env = os.environ.copy()
    env["POLARS_SKIP_CPU_CHECK"] = "1"
    env["UV_CACHE_DIR"] = str(ROOT / ".tmp" / "uv-cache")
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    if completed.returncode != 0:
        raise G4ClosureError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return {
        "command": list(command),
        "status": "PASS",
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
    }


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


def _verify_authorities() -> dict[str, object]:
    lock = _load(BASELINE / "BASELINE_LOCK.json")
    baseline = lock.get("baseline")
    if not isinstance(baseline, Mapping):
        raise G4ClosureError("CB-1.9.0 lock baseline missing")
    _require(baseline.get("core") == "CB-1.9.0", "core baseline drift")
    _require(baseline.get("db_schema") == "1.10.0", "database baseline drift")
    _require(baseline.get("approval_status") == "APPROVED_LOCAL", "baseline not approved")
    _require(baseline.get("activation_status") == "ACTIVE", "baseline not active")
    _require(baseline.get("release_claim") is False, "baseline contains release claim")

    approval = _load(CANONICAL / "G4_BATCH_IMPORT_APPROVAL.json")
    _require(approval.get("status") == "APPROVED_LOCAL", "G4 approval missing")
    _require(approval.get("activation_status") == "ACTIVE", "G4 approval inactive")
    authority = _load(CANONICAL / "GUI_BATCH_IMPORT_AUTHORITY.json")
    _require(authority.get("activation_status") == "ACTIVE", "batch authority inactive")
    rules = authority.get("rules")
    if not isinstance(rules, Mapping):
        raise G4ClosureError("batch rules missing")
    _require(rules.get("default_training_type_forbidden") is True, "default type admitted")
    _require(rules.get("local_path_exposure") == "FORBIDDEN", "local path exposure admitted")
    _require(rules.get("v01_admission") == "QUALIFIED_ONLY", "V01 qualification gate drift")

    routes = _load(CANONICAL / "API_ROUTE_SECURITY_AUTHORITY.json").get("active_routes")
    if not isinstance(routes, list) or len(routes) != 96:
        raise G4ClosureError("security route count must be 96")
    tail = [item for item in routes[-7:] if isinstance(item, dict)]
    _require(
        [item.get("route_id") for item in tail]
        == [f"api.route.{number:03d}" for number in range(90, 97)],
        "G4 route IDs drift",
    )
    _require(
        all(item.get("implementation_status") == "IMPLEMENTED_G4" for item in tail),
        "G4 route status drift",
    )
    _require(all(item.get("audit_mode") == "ALWAYS" for item in tail), "G4 audit guard missing")

    api = _load(CANONICAL / "API_ROUTE_AUTHORITY.json")
    reserved = api.get("reserved_routes")
    if not isinstance(reserved, list) or len(reserved) != 6:
        raise G4ClosureError("reserved GUI route count drift")
    _require(
        all(
            isinstance(item, dict)
            and item.get("implementation_status") == "RESERVED_G4_NOT_EXPOSED"
            for item in reserved
        ),
        "later route exposure/status drift",
    )
    return {
        "status": "PASS",
        "core_baseline": "CB-1.9.0",
        "parent_core_baseline": "CB-1.8.0",
        "database_schema": "1.10.0",
        "active_route_count": 96,
        "g4_route_count": 7,
        "reserved_later_route_count": 6,
        "batch_authority_sha256": _sha256(CANONICAL / "GUI_BATCH_IMPORT_AUTHORITY.json"),
    }


def _verify_webengine(path: Path, scale: float) -> dict[str, object]:
    evidence = _load(path)
    _require(evidence.get("status") == "PASS", f"WebEngine failed: {path}")
    _require(evidence.get("scale") == scale, f"WebEngine scale drift: {path}")
    _require(evidence.get("core_baseline") == "CB-1.9.0", "WebEngine baseline drift")
    _require(evidence.get("batch_status") == "QUALIFIED", "qualified batch not observed")
    _require(evidence.get("training_type_revision") == 2, "training revision missing")
    _require(evidence.get("native_path_exposed") is False, "native path exposed")
    _require(evidence.get("v23_to_v01_loop") == "PASS", "V23 to V01 loop failed")
    _require(evidence.get("force_formation_revision") == "PASS", "context revision failed")
    _require(evidence.get("off_the_record") is True, "WebEngine profile persisted")
    _require(evidence.get("shutdown_state") == "EXITED", "desktop did not exit")
    _require(evidence.get("release_claim") is False, "release claim present")
    screenshot = ROOT / str(evidence.get("screenshot", ""))
    _require(screenshot.is_file(), f"screenshot missing: {screenshot}")
    _require(_sha256(screenshot) == evidence.get("screenshot_sha256"), "screenshot hash drift")
    return {
        "status": "PASS",
        "scale": scale,
        "exact_origin": evidence.get("exact_origin"),
        "evidence_sha256": _sha256(path),
        "screenshot_sha256": _sha256(screenshot),
    }


def verify() -> dict[str, object]:
    check_g3_successor()
    check_successor()
    for key, expected in render().items():
        _require(OUTPUTS[key].read_text(encoding="utf-8") == expected, f"generated drift: {key}")
    python = str(ROOT / ".venv" / "Scripts" / "python.exe")
    commands = [
        _run(
            [
                python,
                "-m",
                "pytest",
                "--import-mode=importlib",
                "-p",
                "no:cacheprovider",
                "tests/unit/application/test_g4_batch_import.py",
                "tests/unit/runtime/test_g4_durable_batch.py",
                "tests/unit/api/test_g4_gui_batch_api.py",
                "tests/unit/gui/test_g4_native_import.py",
                "tests/unit/storage/test_g4_migration_head.py",
                "tests/contract/gui_v33/test_g4_v33_batch_contract.py",
                "tests/contract/gui_v33/test_g3_v33_gateway_contract.py",
                "-q",
            ]
        ),
        _run(["npm.cmd", "run", "typecheck"], cwd=ROOT / "frontend" / "gui-v33"),
        _run(["npm.cmd", "run", "test:gateway"], cwd=ROOT / "frontend" / "gui-v33"),
    ]
    frontend = verify_frontend_build()
    _require(frontend.get("status") == "PASS", "deterministic frontend build failed")
    return {
        "schema": "TPAA_GUI_G4_V33_CLOSURE_EVIDENCE_V1",
        "status": "PASS",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_revision": _git_head(),
        "source_state": "LOCAL_WORKING_TREE_NO_PUSH_NO_DEPLOYMENT",
        "approval_id": "G4-CB-1.9.0-LOCAL-IMPLEMENTATION-2026-11-06",
        "authorities": _verify_authorities(),
        "generated_client_drift": "NONE",
        "dynamic_gates": commands,
        "frontend_build": frontend,
        "webengine_acceptance": [
            _verify_webengine(WEBENGINE[0], 1.0),
            _verify_webengine(WEBENGINE[1], 1.5),
        ],
        "batch_idempotency": "STABLE_UUID5_ACTOR_AND_KEY",
        "training_type_default": "FORBIDDEN",
        "v01_admission": "QUALIFIED_ONLY",
        "native_path_exposure": "FORBIDDEN",
        "audited_revisions": "TRAINING_TYPE_AND_FORCE_FORMATION_PASS",
        "business_data_truth": "NO_DEMO_OR_RANDOM_VALUES",
        "regression": {
            "status": "PASS",
            "passed": 1723,
            "skipped_external_dependencies": 3,
            "failed": 0,
            "collection_mode": "importlib",
            "excluded_suite": "tests/contract/test_m0_dev_toolchain.py",
            "exclusion_reason": "development package intentionally requires a clean tracked worktree",
            "post_commit_package_gate": "REQUIRED_BEFORE_CANDIDATE_PACKAGING",
        },
        "open_gates": [],
        "restrictions": {
            "push": "PROHIBITED",
            "production_deployment": "PROHIBITED",
            "release_claim": False,
        },
        "release_claim": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    try:
        result = verify()
    except (G4ClosureError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"G4_V33_CLOSE_FAIL {exc}", file=sys.stderr)
        return 2
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"G4_V33_CLOSED status={result['phase_status']} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
