#!/usr/bin/env python3
"""Verify every local G2 exit gate and write the formal closure evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.baseline.adopt_g2_successor import _runtime_routes, check_successor  # noqa: E402
from tools.codegen.g2_security_generate import OUTPUT as GENERATED_AUTHORITY  # noqa: E402
from tools.codegen.g2_security_generate import render as render_generated_authority  # noqa: E402
from tools.gui.g1_frontend_build import verify as verify_frontend_build  # noqa: E402
from tools.gui.g2_v33_verify import verify as verify_static_shell  # noqa: E402
from tpaa_security import (  # noqa: E402
    SecurityRole,
    derive_gui_permissions,
    load_security_policy,
    route_security,
)

BASELINE = ROOT / "baseline" / "CB-1.7.0"
CANONICAL = BASELINE / "canonical"
OUTPUT = ROOT / "evidence" / "gui-g2-v33-closure.json"
WEBENGINE_EVIDENCE = (
    ROOT / "evidence" / "gui-g2-v33-webengine-100.json",
    ROOT / "evidence" / "gui-g2-v33-webengine-150.json",
)


class G2ClosureError(RuntimeError):
    """A mandatory G2 local closure gate did not pass."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G2ClosureError(message)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G2ClosureError(f"expected JSON object: {path}")
    return value


def _objects(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise G2ClosureError(f"expected JSON object array: {label}")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise G2ClosureError(f"expected JSON object: {label}[{index}]")
        result.append(item)
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _concrete(template: str) -> str:
    return re.sub(r"\{[^}/]+(?::path)?\}", "exact-id", template)


def _verify_role_matrix() -> dict[str, Any]:
    matrix = _load(CANONICAL / "GUI_ROLE_VIEW_ACCESS_MATRIX.json")
    contract = _load(CANONICAL / "GUI_VIEW_CONTRACT.json")
    summaries = _objects(matrix.get("role_summary"), "matrix.role_summary")
    views = _objects(contract.get("views"), "contract.views")
    _require(matrix.get("approval_status") == "APPROVED_LOCAL", "role matrix not approved")
    _require(matrix.get("activation_status") == "ACTIVE", "role matrix not active")
    _require(len(summaries) == 9, "role matrix must cover nine roles")
    _require(len(views) == 26, "view contract must cover 26 views")
    expected_by_role: dict[str, set[str]] = {}
    for item in summaries:
        role_id = item.get("role_id")
        view_ids = item.get("view_ids")
        if not isinstance(role_id, str):
            raise G2ClosureError("role summary role_id invalid")
        if not isinstance(view_ids, list) or not all(isinstance(value, str) for value in view_ids):
            raise G2ClosureError(f"role summary view_ids invalid: {role_id}")
        expected_by_role[role_id] = set(cast(list[str], view_ids))

    policy = load_security_policy()
    runtime_counts: dict[str, int] = {}
    for role in SecurityRole:
        grants = set(derive_gui_permissions((role,), policy.role_permissions[role]))
        actual = {
            str(item["view_id"])
            for item in views
            if isinstance(item.get("required_permissions"), list)
            and set(item["required_permissions"]).issubset(grants)
        }
        _require(actual == expected_by_role.get(role.value), f"role/view drift: {role.value}")
        runtime_counts[role.value] = len(actual)
    _require(set(expected_by_role) == {role.value for role in SecurityRole}, "role set drift")
    return {"status": "PASS", "role_count": 9, "view_count": 26, "view_counts": runtime_counts}


def _verify_route_authority() -> dict[str, Any]:
    authority = _load(CANONICAL / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = _objects(authority.get("active_routes"), "route_authority.active_routes")
    _require(authority.get("approval_status") == "APPROVED_LOCAL", "route authority not approved")
    _require(authority.get("activation_status") == "ACTIVE", "route authority not active")
    _require(authority.get("default_unknown_route_policy") == "DENY", "unknown route not denied")
    expected = {(str(item.get("method")), str(item.get("path"))) for item in routes}
    actual = {(item["method"], item["path"]) for item in _runtime_routes()}
    _require(len(routes) == 86 and len(expected) == 86, "approved route count must be 86")
    _require(actual == expected, "runtime FastAPI graph differs from approved route authority")
    route_ids: set[str] = set()
    business_routes = 0
    status_routes = 0
    for item in routes:
        route_id = item.get("route_id")
        method = item.get("method")
        template = item.get("path")
        if not isinstance(route_id, str) or not isinstance(method, str) or not isinstance(template, str):
            raise G2ClosureError("invalid route identity")
        _require(route_id not in route_ids, f"duplicate route ID: {route_id}")
        route_ids.add(route_id)
        binding = route_security(method, _concrete(template))
        if binding is None or binding.route_id != route_id:
            raise G2ClosureError(f"route lookup drift: {route_id}")
        expected_permission = item.get("permission_id")
        actual_permission = None if binding.permission is None else binding.permission.value
        _require(actual_permission == expected_permission, f"route permission drift: {route_id}")
        _require(binding.audit_mode == item.get("audit_mode"), f"route audit drift: {route_id}")
        if expected_permission is None:
            status_routes += 1
        else:
            business_routes += 1
            _require(binding.audit_mode == "ALWAYS", f"business route audit not ALWAYS: {route_id}")
    _require(route_security("GET", "/not-an-approved-route") is None, "unknown route lookup did not deny")
    return {
        "status": "PASS",
        "route_count": len(routes),
        "business_permission_routes": business_routes,
        "authenticated_status_routes": status_routes,
        "unknown_route_policy": "DENY",
    }


def _verify_webengine(path: Path, expected_scale: float) -> dict[str, Any]:
    evidence = _load(path)
    _require(evidence.get("status") == "PASS", f"WebEngine evidence failed: {path}")
    _require(evidence.get("scale") == expected_scale, f"WebEngine scale drift: {path}")
    _require(evidence.get("device_pixel_ratio") == expected_scale, f"WebEngine DPR drift: {path}")
    _require(evidence.get("off_the_record") is True, f"WebEngine profile persisted: {path}")
    _require(evidence.get("direct_v24_http_status") == 403, f"V24 server guard failed: {path}")
    _require(evidence.get("shutdown_state") == "EXITED", f"desktop did not exit: {path}")
    _require(evidence.get("release_claim") is False, f"release claim present: {path}")
    authority = evidence.get("session_authority")
    if not isinstance(authority, Mapping):
        raise G2ClosureError(f"session authority missing: {path}")
    _require(authority.get("id") == "GUI_PERMISSION_AUDIT_AUTHORITY", "GUI authority ID drift")
    _require(authority.get("version") == "1.1.0", "GUI authority version drift")
    _require(authority.get("activation") == "ACTIVE", "GUI authority inactive")
    keyboard = evidence.get("keyboard_training_landing")
    focus = evidence.get("focus_transaction")
    v24 = evidence.get("v24_ui_guard")
    geometry = evidence.get("final_geometry")
    _require(isinstance(keyboard, Mapping) and keyboard.get("currentView") == "V26", "Alt+2 landing failed")
    _require(
        isinstance(focus, Mapping)
        and focus.get("before") == "overview"
        and focus.get("after") == "overview"
        and focus.get("currentView") == "V01",
        "focus restoration failed",
    )
    _require(
        isinstance(v24, Mapping)
        and v24.get("disabled") is True
        and v24.get("ariaDisabled") == "true"
        and v24.get("directNavPresent") is False
        and v24.get("currentView") == "V08",
        "V24 UI conditional entry failed",
    )
    _require(
        isinstance(geometry, Mapping)
        and geometry.get("horizontalOverflow") is False
        and geometry.get("mainWithinViewport") is True
        and geometry.get("clippedButtons") == [],
        "high-DPI geometry gate failed",
    )
    themes = _objects(evidence.get("themes"), f"{path}.themes")
    _require({item.get("theme") for item in themes} == {"tactical", "graphite", "light"}, "theme set drift")
    screenshots: list[dict[str, Any]] = []
    for item in themes:
        relative = item.get("path")
        if not isinstance(relative, str):
            raise G2ClosureError("screenshot path invalid")
        screenshot = ROOT / relative
        _require(screenshot.is_file(), f"screenshot missing: {relative}")
        _require(_sha256(screenshot) == item.get("sha256"), f"screenshot hash drift: {relative}")
        screenshots.append({"path": relative, "sha256": item.get("sha256")})
    return {
        "status": "PASS",
        "scale": expected_scale,
        "exact_origin": evidence.get("exact_origin"),
        "off_the_record": True,
        "screenshots": screenshots,
    }


def verify() -> dict[str, Any]:
    check_successor()
    _require(
        GENERATED_AUTHORITY.read_text(encoding="utf-8") == render_generated_authority(),
        "generated G2 security authority drift",
    )
    approval = _load(CANONICAL / "G2_GUI_SECURITY_APPROVAL.json")
    lock = _load(BASELINE / "BASELINE_LOCK.json")
    baseline = lock.get("baseline")
    if not isinstance(baseline, Mapping):
        raise G2ClosureError("CB-1.7.0 lock baseline missing")
    _require(approval.get("status") == "APPROVED_LOCAL", "local approval missing")
    _require(approval.get("activation_status") == "ACTIVE", "local activation missing")
    _require(baseline.get("core") == "CB-1.7.0", "core baseline drift")
    _require(baseline.get("approval_status") == "APPROVED_LOCAL", "lock not locally approved")
    _require(baseline.get("activation_status") == "ACTIVE", "lock not active")
    _require(baseline.get("release_claim") is False, "lock contains release claim")

    static = verify_static_shell()
    _require(static.get("permissioned_navigation") == "PASS", "static permission navigation failed")
    _require(static.get("unbound_view_ids") == [], "view permission bindings incomplete")
    _require(static.get("v24_ui_and_server_guard_static_checks") == "PASS", "static V24 guard failed")
    _require(static.get("theme_and_shared_state_static_checks") == "PASS", "static theme/state gate failed")
    _require(static.get("g0r_g1_evidence_review") == "PASS_STATIC_REVIEW", "G0R/G1 regression review failed")

    frontend = verify_frontend_build()
    _require(frontend.get("status") == "PASS", "deterministic frontend build failed")
    webengine = [
        _verify_webengine(WEBENGINE_EVIDENCE[0], 1.0),
        _verify_webengine(WEBENGINE_EVIDENCE[1], 1.5),
    ]
    return {
        "schema": "TPAA_GUI_G2_V33_CLOSURE_EVIDENCE_V1",
        "status": "PASS",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_revision": _git_head(),
        "source_state": "LOCAL_WORKING_TREE_NO_PUSH_NO_DEPLOYMENT",
        "approval_id": approval.get("approval_id"),
        "core_baseline": "CB-1.7.0",
        "authority_activation": "ACTIVE_LOCAL_ONLY",
        "baseline_reproducibility": "PASS",
        "generated_authority_drift": "NONE",
        "static_shell_contract": "PASS",
        "route_authority": _verify_route_authority(),
        "role_view_authority": _verify_role_matrix(),
        "frontend_build": frontend,
        "webengine_acceptance": webengine,
        "g0r_g1_regression_review": "PASS",
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
    except (
        G2ClosureError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"G2_V33_CLOSE_FAIL {exc}", file=sys.stderr)
        return 2
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"G2_V33_CLOSED status={result['phase_status']} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
