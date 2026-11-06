#!/usr/bin/env python3
"""Generate the immutable CB-1.7.0 runtime security authority module."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "baseline" / "CB-1.7.0" / "canonical"
OUTPUT = ROOT / "src" / "tpaa_security" / "generated_g2_authority.py"


class G2SecurityCodegenError(RuntimeError):
    """The approved security authority is missing, malformed, or drifting."""


def _load(filename: str) -> dict[str, Any]:
    value = json.loads((CANONICAL / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G2SecurityCodegenError(f"expected object: {filename}")
    if value.get("approval_status") != "APPROVED_LOCAL":
        raise G2SecurityCodegenError(f"authority is not approved: {filename}")
    if value.get("activation_status") != "ACTIVE":
        raise G2SecurityCodegenError(f"authority is not active: {filename}")
    return value


def _string_tuple(values: object, label: str) -> tuple[str, ...]:
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise G2SecurityCodegenError(f"expected string array: {label}")
    return tuple(values)


def render() -> str:
    gui = _load("GUI_PERMISSION_AUDIT_AUTHORITY.json")
    routes = _load("API_ROUTE_SECURITY_AUTHORITY.json")
    role_authority = gui.get("role_authority")
    bindings = gui.get("business_permission_bindings")
    active_routes = routes.get("active_routes")
    if not isinstance(role_authority, dict) or not isinstance(bindings, list):
        raise G2SecurityCodegenError("GUI authority role/binding sections are invalid")
    if not isinstance(active_routes, list) or len(active_routes) != 86:
        raise G2SecurityCodegenError("explicit route authority must contain 86 routes")
    known_roles = _string_tuple(role_authority.get("role_ids"), "role_authority.role_ids")
    gui_rows: list[tuple[str, str, tuple[str, ...]]] = []
    for index, item in enumerate(bindings):
        if not isinstance(item, dict):
            raise G2SecurityCodegenError(f"GUI binding {index} is not an object")
        permission_id = item.get("permission_id")
        binding_type = item.get("binding_type")
        if not isinstance(permission_id, str) or not isinstance(binding_type, str):
            raise G2SecurityCodegenError(f"GUI binding {index} identity is invalid")
        business = _string_tuple(
            item.get("business_permissions"),
            f"business_permission_bindings[{index}].business_permissions",
        )
        gui_rows.append((permission_id, binding_type, business))
    route_rows: list[tuple[str, str, str, str | None, str]] = []
    for index, item in enumerate(active_routes):
        if not isinstance(item, dict):
            raise G2SecurityCodegenError(f"route {index} is not an object")
        route_id = item.get("route_id")
        method = item.get("method")
        path = item.get("path")
        permission_id = item.get("permission_id")
        audit_mode = item.get("audit_mode")
        if (
            not isinstance(route_id, str)
            or not isinstance(method, str)
            or not isinstance(path, str)
            or not isinstance(audit_mode, str)
        ):
            raise G2SecurityCodegenError(f"route {index} identity is invalid")
        if permission_id is not None and not isinstance(permission_id, str):
            raise G2SecurityCodegenError(f"route {index} permission is invalid")
        route_rows.append((route_id, method, path, permission_id, audit_mode))
    lines = [
        '"""Generated from approved CB-1.7.0 authorities; do not edit manually."""',
        "",
        "from typing import Final",
        "",
        f"CORE_BASELINE: Final = {gui['core_baseline']!r}",
        f"GUI_AUTHORITY_ID: Final = {gui['authority_id']!r}",
        f"GUI_AUTHORITY_VERSION: Final = {gui['authority_version']!r}",
        "GUI_ACTIVATION_STATUS: Final = 'ACTIVE'",
        f"KNOWN_GUI_ROLES: Final[tuple[str, ...]] = {known_roles!r}",
        "GUI_PERMISSION_BINDINGS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (",
    ]
    lines.extend(f"    {row!r}," for row in gui_rows)
    lines.extend(
        [
            ")",
            "ROUTE_SECURITY_BINDINGS: Final[tuple[tuple[str, str, str, str | None, str], ...]] = (",
        ]
    )
    lines.extend(f"    {row!r}," for row in route_rows)
    lines.extend([")", ""])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        rendered = render()
        if args.check:
            if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
                raise G2SecurityCodegenError("generated runtime authority drift")
            print("G2_SECURITY_CODEGEN_PASS routes=86")
        else:
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="\n", delete=False, dir=OUTPUT.parent
            ) as temporary:
                temporary.write(rendered)
                temporary_path = Path(temporary.name)
            temporary_path.replace(OUTPUT)
            print(f"G2_SECURITY_CODEGEN_BUILT routes=86 output={OUTPUT}")
    except (OSError, ValueError, KeyError, G2SecurityCodegenError) as exc:
        print(f"G2_SECURITY_CODEGEN_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
