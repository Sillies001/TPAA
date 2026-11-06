#!/usr/bin/env python3
"""Verify every G3 exit gate and write formal local closure evidence."""

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

from tools.baseline.adopt_g2_successor import check_successor as check_g2_successor  # noqa: E402
from tools.baseline.adopt_g3_successor import check_successor  # noqa: E402
from tools.codegen.g3_gateway_generate import OUTPUTS, render  # noqa: E402
from tools.gui.g1_frontend_build import verify as verify_frontend_build  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.8.0"
CANONICAL = BASELINE / "canonical"
OUTPUT = ROOT / "evidence" / "gui-g3-v33-closure.json"
WEBENGINE = (
    ROOT / "evidence" / "gui-g3-v33-webengine-100.json",
    ROOT / "evidence" / "gui-g3-v33-webengine-150.json",
)


class G3ClosureError(RuntimeError):
    """A mandatory G3 local closure gate failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G3ClosureError(message)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G3ClosureError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: Sequence[str], *, cwd: Path = ROOT) -> dict[str, object]:
    env = os.environ.copy()
    env["POLARS_SKIP_CPU_CHECK"] = "1"
    env["UV_CACHE_DIR"] = str(Path(env.get("TEMP", str(ROOT))) / "tpaa-uv-cache")
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if completed.returncode != 0:
        raise G3ClosureError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return {
        "command": list(command),
        "status": "PASS",
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
    }


def _git_head() -> str:
    return str(
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    )


def _verify_authorities() -> dict[str, object]:
    lock = _load(BASELINE / "BASELINE_LOCK.json")
    baseline = lock.get("baseline")
    if not isinstance(baseline, Mapping):
        raise G3ClosureError("CB-1.8.0 lock baseline missing")
    _require(baseline.get("core") == "CB-1.8.0", "core baseline drift")
    _require(baseline.get("db_schema") == "1.10.0", "database baseline drift")
    _require(baseline.get("approval_status") == "APPROVED_LOCAL", "baseline not approved")
    _require(baseline.get("activation_status") == "ACTIVE", "baseline not active")
    _require(baseline.get("release_claim") is False, "baseline contains release claim")
    approval = _load(CANONICAL / "G3_GATEWAY_APPROVAL.json")
    _require(approval.get("status") == "APPROVED_LOCAL", "G3 approval missing")
    _require(approval.get("activation_status") == "ACTIVE", "G3 approval inactive")
    routes = _load(CANONICAL / "API_ROUTE_SECURITY_AUTHORITY.json").get("active_routes")
    if not isinstance(routes, list) or len(routes) != 89:
        raise G3ClosureError("security route count must be 89")
    tail = [item for item in routes[-3:] if isinstance(item, dict)]
    _require(
        [item.get("route_id") for item in tail]
        == ["api.route.087", "api.route.088", "api.route.089"],
        "G3 route IDs drift",
    )
    _require(all(item.get("gui_permission_id") == "gui.view" for item in tail), "GUI guard missing")
    _require(
        all(item.get("permission_id") is None for item in tail), "business permission over-bound"
    )
    api = _load(CANONICAL / "API_ROUTE_AUTHORITY.json")
    reserved = api.get("reserved_routes")
    if not isinstance(reserved, list) or len(reserved) != 12:
        raise G3ClosureError("reserved GUI route count drift")
    _require(
        all(
            isinstance(item, dict)
            and item.get("implementation_status") == "RESERVED_G3_NOT_EXPOSED"
            for item in reserved
        ),
        "reserved route exposure/status drift",
    )
    gateway = _load(CANONICAL / "GUI_ASYNC_GATEWAY_AUTHORITY.json")
    _require(gateway.get("activation_status") == "ACTIVE", "gateway authority inactive")
    return {
        "status": "PASS",
        "core_baseline": "CB-1.8.0",
        "database_schema": "1.10.0",
        "active_route_count": 89,
        "g3_route_count": 3,
        "reserved_business_route_count": 12,
        "gateway_authority_sha256": _sha256(CANONICAL / "GUI_ASYNC_GATEWAY_AUTHORITY.json"),
    }


def _verify_webengine(path: Path, scale: float) -> dict[str, object]:
    evidence = _load(path)
    _require(evidence.get("status") == "PASS", f"WebEngine failed: {path}")
    _require(evidence.get("scale") == scale, f"WebEngine scale drift: {path}")
    _require(evidence.get("off_the_record") is True, f"WebEngine profile persisted: {path}")
    _require(evidence.get("shutdown_state") == "EXITED", f"desktop did not exit: {path}")
    _require(evidence.get("release_claim") is False, f"release claim present: {path}")
    bootstrap = evidence.get("bootstrap")
    pagination = evidence.get("pagination")
    dynamic = evidence.get("dynamic_selector")
    probe = evidence.get("webengine_probe")
    _require(
        isinstance(bootstrap, Mapping)
        and bootstrap.get("core_baseline") == "CB-1.8.0"
        and bootstrap.get("view_count") == 26,
        "WebEngine bootstrap invalid",
    )
    _require(
        isinstance(pagination, Mapping)
        and pagination.get("page_one_count") == 7
        and pagination.get("page_two_count") == 7
        and pagination.get("overlap") is False,
        "WebEngine pagination invalid",
    )
    _require(
        isinstance(dynamic, Mapping)
        and dynamic.get("items") == []
        and dynamic.get("reason_code") == "CONTEXT_REQUIRED",
        "WebEngine dynamic selector fabricated data",
    )
    _require(
        isinstance(probe, Mapping)
        and probe.get("status") == 200
        and probe.get("schema") == "TPAA_GUI_BOOTSTRAP_V1",
        "WebEngine native-header gateway probe failed",
    )
    return {
        "status": "PASS",
        "scale": scale,
        "exact_origin": evidence.get("exact_origin"),
        "sha256": _sha256(path),
    }


def verify() -> dict[str, object]:
    check_g2_successor()
    check_successor()
    for key, expected in render().items():
        _require(OUTPUTS[key].read_text(encoding="utf-8") == expected, f"generated drift: {key}")
    commands = [
        _run(
            [
                str(ROOT / ".venv" / "Scripts" / "python.exe"),
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "tests/unit/application/test_g3_gui_gateway_application.py",
                "tests/unit/api/test_g3_gui_gateway_api.py",
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
        "schema": "TPAA_GUI_G3_V33_CLOSURE_EVIDENCE_V1",
        "status": "PASS",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_revision": _git_head(),
        "source_state": "LOCAL_WORKING_TREE_NO_PUSH_NO_DEPLOYMENT",
        "approval_id": "G3-CB-1.8.0-LOCAL-CLOSURE-2026-11-06",
        "authorities": _verify_authorities(),
        "generated_client_drift": "NONE",
        "dynamic_gates": commands,
        "frontend_build": frontend,
        "webengine_acceptance": [
            _verify_webengine(WEBENGINE[0], 1.0),
            _verify_webengine(WEBENGINE[1], 1.5),
        ],
        "stale_response_overwrite": "REJECTED",
        "cross_principal_cache": "FORBIDDEN",
        "cross_release_cache": "FORBIDDEN",
        "pagination_cancel_error_gates": "PASS",
        "business_data_truth": "NO_DEMO_OR_RANDOM_VALUES",
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
    except (G3ClosureError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"G3_V33_CLOSE_FAIL {exc}", file=sys.stderr)
        return 2
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"G3_V33_CLOSED status={result['phase_status']} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
