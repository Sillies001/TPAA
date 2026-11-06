#!/usr/bin/env python3
"""Static G2 v33 contract verifier; deliberately does not close the phase."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evidence" / "gui-g2-v33-progress.json"


class G2VerificationError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G2VerificationError(f"expected JSON object: {path}")
    return value


def _object_list(value: object, label: str) -> list[dict[str, Any]]:
    """Validate a JSON array of objects before iterating over its members."""

    if not isinstance(value, list):
        raise G2VerificationError(f"expected JSON object array: {label}")
    items: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or not all(isinstance(key, str) for key in item):
            raise G2VerificationError(f"expected JSON object at {label}[{index}]")
        items.append(item)
    return items


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G2VerificationError(message)


def _unbound_view_permissions(views: list[dict[str, Any]]) -> list[str]:
    """Return every view lacking an explicit non-empty permission binding."""

    unbound: list[str] = []
    for item in views:
        view_id = item.get("view_id")
        required = item.get("required_permissions")
        if (
            not isinstance(view_id, str)
            or not isinstance(required, list)
            or not required
            or not all(isinstance(permission, str) and permission.strip() for permission in required)
        ):
            if isinstance(view_id, str):
                unbound.append(view_id)
    return unbound


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    )
    return result.stdout.strip()


def verify() -> dict[str, Any]:
    registry = _load(ROOT / "docs/gui/demo-v33/V33_FINAL_VIEW_REGISTRY.json")
    contract = _load(ROOT / "baseline/CB-1.6.0/canonical/GUI_VIEW_CONTRACT.json")
    permissions = _load(ROOT / "baseline/CB-1.6.0/canonical/GUI_PERMISSION_AUDIT_AUTHORITY.json")
    routes = _load(ROOT / "baseline/CB-1.6.0/canonical/API_ROUTE_AUTHORITY.json")
    openapi = _load(ROOT / "generated/g1-cb-1.6.0/api/openapi-gui-v33.json")
    g0r = _load(ROOT / "evidence/gui-g0-v33/g0r-v33-closure.json")
    g1 = _load(ROOT / "evidence/gui-g1-v33-closure.json")
    main = (ROOT / "frontend/gui-v33/src/main.ts").read_text(encoding="utf-8")
    css = (ROOT / "frontend/gui-v33/src/style.css").read_text(encoding="utf-8")
    desktop = (ROOT / "src/tpaa_api/desktop.py").read_text(encoding="utf-8")

    ids = [f"V{index:02d}" for index in range(1, 27)]
    registry_views = _object_list(registry.get("views"), "registry.views")
    contract_views = _object_list(contract.get("views"), "contract.views")
    _require(registry.get("view_count") == 26, "registry count drift")
    _require(
        isinstance(registry_views, list) and [item.get("id") for item in registry_views] == ids,
        "registry IDs drift",
    )
    _require(
        isinstance(contract_views, list)
        and [item.get("view_id") for item in contract_views] == ids,
        "view contract IDs drift",
    )
    registry_modules = _object_list(registry.get("modules"), "registry.modules")
    modules = {item.get("id"): item for item in registry_modules}
    _require(
        len(modules) == 5 and modules.get("training", {}).get("landing") == "V26",
        "module landing drift",
    )
    v24 = next((item for item in contract_views if item.get("view_id") == "V24"), {})
    _require(v24.get("entry_type") == "CONDITIONAL_V08_ONLY", "V24 entry type drift")
    _require(
        v24.get("allowed_predecessor") == ["V08"] and v24.get("return_target") == "V08",
        "V24 predecessor/return drift",
    )

    _require(
        "V33_FINAL_VIEW_REGISTRY.json" in main and "GUI_VIEW_CONTRACT.json" in main,
        "frontend authority imports missing",
    )
    _require(
        'view.id !== "V24"' in main and "V24_REQUIRES_V08_CONTEXT" in main,
        "frontend V24 direct guard missing",
    )
    _require(
        'fetch("/security/session"' in main
        and "required_permissions.every" in main
        and "function hasViewPermissions" in main
        and "contract.required_permissions.length === 0" in main,
        "fail-closed permission-aware navigation missing",
    )
    _require('theme: "graphite"' in main, "Graphite is not the session default")
    _require(
        all(
            f':root[data-tpaa-theme="{theme}"]' in css
            for theme in ("tactical", "graphite", "light")
        ),
        "theme tokens missing",
    )
    _require(
        "domainSelection" in main and "replayState" in main and "returnStack" in main,
        "shared state layers missing",
    )
    _require(
        not re.search(
            r"\b(?:localStorage|sessionStorage)\.(?:setItem|removeItem|clear)\s*\(",
            main,
        ),
        "browser business persistence write found",
    )
    _require("Math.random(" not in main, "random business data found")
    _require(
        "_is_direct_v24_navigation" in desktop and "V24_REQUIRES_V08_CONTEXT" in desktop,
        "server V24 direct guard missing",
    )

    reserved = _object_list(routes.get("reserved_routes"), "routes.reserved_routes")
    _require(len(reserved) == 14, "G1 reserved route count drift")
    paths = openapi.get("paths", {})
    _require(
        not any(item.get("path") in paths for item in reserved),
        "G1 reserved route was exposed",
    )
    _require(
        g0r.get("status") == "PASS" and g0r.get("release_claim") is False,
        "G0R evidence invalid",
    )
    _require(g1.get("status") == "PASS" and g1.get("release_claim") is False, "G1 evidence invalid")
    permission_records = _object_list(permissions.get("permissions"), "permissions.permissions")
    _require(
        all(item.get("unknown_policy") == "DENY" for item in permission_records),
        "permission unknown policy is not deny",
    )
    unbound_view_ids = _unbound_view_permissions(contract_views)
    open_gates = [
        "Run npm ci, npm run typecheck and npm run build on the Windows workspace",
        "Regenerate src/tpaa_gui/web_dist and pass tools/gui/g1_frontend_build.py",
        "Run targeted Ruff and pytest for the new G2 contract and V24 server guard tests",
        "Run the G0R/G1 verifier commands after the frontend build and confirm zero drift",
        "Execute Windows WebEngine loopback, three-theme, keyboard, focus, ribbon and high-DPI checks",
        "Inspect npm audit high severity advisory and assess the affected dependency path",
    ]
    if unbound_view_ids:
        open_gates.insert(
            0,
            "Create a controlled successor authority diff binding explicit permissions to all 26 views; "
            "current GUI_VIEW_CONTRACT has empty required_permissions for: "
            + ", ".join(unbound_view_ids),
        )

    return {
        "schema": "TPAA_GUI_G2_V33_PROGRESS_EVIDENCE_V1",
        "status": "IN_PROGRESS",
        "phase_status": "IN_PROGRESS",
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_revision": _git_head(),
        "authority_checks": "PASS_STATIC_CATALOG",
        "permissioned_navigation": (
            "BLOCKED_MISSING_VIEW_PERMISSION_BINDINGS" if unbound_view_ids else "PASS"
        ),
        "unbound_view_ids": unbound_view_ids,
        "v24_ui_and_server_guard_static_checks": "PASS",
        "theme_and_shared_state_static_checks": "PASS",
        "g0r_g1_evidence_review": "PASS_STATIC_REVIEW",
        "frontend_typecheck": "NOT_RUN",
        "vite_build_and_web_dist_sync": "PENDING",
        "python_targeted_tests": "NOT_RUN",
        "webengine_visual_keyboard_hidpi_tests": "PENDING",
        "open_gates": open_gates,
        "release_claim": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    try:
        result = verify()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, G2VerificationError) as exc:
        print(f"G2_V33_VERIFY_FAIL {exc}", file=sys.stderr)
        return 2
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"G2_V33_PROGRESS status={result['status']} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
