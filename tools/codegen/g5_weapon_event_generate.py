#!/usr/bin/env python3
"""Generate CB-1.10.0 G5 security, gateway and TypeScript Weapon-Event authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.10.0"
CANONICAL = BASELINE / "canonical"
OUTPUTS = {
    "security": ROOT / "src" / "tpaa_security" / "generated_g5_authority.py",
    "application": ROOT / "src" / "tpaa_application" / "generated_g5_gateway.py",
    "typescript": ROOT / "frontend" / "gui-v33" / "src" / "generated" / "g5-weapon-event.ts",
    "python_dto": ROOT / "src" / "tpaa_application" / "generated_g5_dto.py",
}
MANIFEST = ROOT / "generated" / "g5-cb-1.10.0" / "manifest.json"


class G5CodegenError(RuntimeError):
    pass


def _load(name: str) -> dict[str, Any]:
    value = json.loads((CANONICAL / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G5CodegenError(f"expected object: {name}")
    return value


def _objects(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise G5CodegenError(f"expected object array: {label}")
    return list(value)


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise G5CodegenError(f"expected strings: {label}")
    return tuple(value)


def _security() -> str:
    gui = _load("GUI_PERMISSION_AUDIT_AUTHORITY.json")
    route_authority = _load("API_ROUTE_SECURITY_AUTHORITY.json")
    role_authority = gui.get("role_authority")
    if not isinstance(role_authority, dict):
        raise G5CodegenError("role authority invalid")
    bindings = _objects(gui.get("business_permission_bindings"), "GUI bindings")
    routes = _objects(route_authority.get("active_routes"), "active routes")
    if len(routes) != 99:
        raise G5CodegenError("G5 route authority must contain 99 routes")
    gui_rows = []
    for item in bindings:
        gui_rows.append(
            (
                str(item["permission_id"]),
                str(item["binding_type"]),
                _strings(item.get("business_permissions"), "business permissions"),
            )
        )
    route_rows = []
    for item in routes:
        permission = item.get("permission_id")
        gui_permission = item.get("gui_permission_id")
        if permission is not None and not isinstance(permission, str):
            raise G5CodegenError("route permission invalid")
        if gui_permission is not None and not isinstance(gui_permission, str):
            raise G5CodegenError("GUI route permission invalid")
        route_rows.append(
            (
                str(item["route_id"]),
                str(item["method"]),
                str(item["path"]),
                permission,
                str(item["audit_mode"]),
                gui_permission,
            )
        )
    lines = [
        '"""Generated from approved CB-1.10.0 authorities; do not edit manually."""',
        "",
        "from typing import Final",
        "",
        "CORE_BASELINE: Final = 'CB-1.10.0'",
        f"GUI_AUTHORITY_ID: Final = {gui['authority_id']!r}",
        f"GUI_AUTHORITY_VERSION: Final = {gui['authority_version']!r}",
        "GUI_ACTIVATION_STATUS: Final = 'ACTIVE'",
        f"KNOWN_GUI_ROLES: Final[tuple[str, ...]] = {_strings(role_authority.get('role_ids'), 'roles')!r}",
        "GUI_PERMISSION_BINDINGS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (",
    ]
    lines.extend(f"    {row!r}," for row in gui_rows)
    lines.extend(
        [
            ")",
            "ROUTE_SECURITY_BINDINGS: Final[tuple[tuple[str, str, str, str | None, str, str | None], ...]] = (",
        ]
    )
    lines.extend(f"    {row!r}," for row in route_rows)
    lines.extend([")", ""])
    return "\n".join(lines)


def _application() -> str:
    parent = (ROOT / "src" / "tpaa_application" / "generated_g4_gateway.py").read_text(
        encoding="utf-8"
    )
    return parent.replace("Generated G4", "Generated G5").replace("CB-1.9.0", "CB-1.10.0")


_G5_DTOS = (
    "WeaponEventDetailDTO",
    "WeaponEventWindowDTO",
    "WeaponEventPerspectiveDTO",
)


def _dto_fields() -> dict[str, list[dict[str, Any]]]:
    contracts = _load("CROSS_LAYER_DTO_CONTRACTS.json").get("contracts")
    if not isinstance(contracts, dict):
        raise G5CodegenError("DTO contracts invalid")
    result: dict[str, list[dict[str, Any]]] = {}
    for name in _G5_DTOS:
        contract = contracts.get(name)
        if not isinstance(contract, dict):
            raise G5CodegenError(f"missing DTO contract: {name}")
        result[name] = _objects(contract.get("fields"), f"{name}.fields")
    return result


def _python_type(transport_type: str) -> str:
    mapping = {
        "string": "str",
        "string?": "str | None",
        "uuid-string": "str",
        "uuid-string?": "str | None",
        "decimal-string": "str",
        "decimal-string?": "str | None",
        "boolean": "bool",
        "object": "dict[str, object]",
    }
    try:
        return mapping[transport_type]
    except KeyError as exc:
        raise G5CodegenError(f"unsupported G5 Python DTO type: {transport_type}") from exc


def _typescript_type(transport_type: str) -> str:
    mapping = {
        "string": "string",
        "string?": "string | null",
        "uuid-string": "string",
        "uuid-string?": "string | null",
        "decimal-string": "string",
        "decimal-string?": "string | null",
        "boolean": "boolean",
        "object": "Readonly<Record<string, unknown>>",
    }
    try:
        return mapping[transport_type]
    except KeyError as exc:
        raise G5CodegenError(f"unsupported G5 TypeScript DTO type: {transport_type}") from exc


def _python_dto() -> str:
    lines = [
        '"""Generated from CROSS_LAYER_DTO_CONTRACTS; do not edit manually."""',
        "",
        "from typing import TypedDict",
        "",
        "",
    ]
    for name, fields in _dto_fields().items():
        lines.append(f"class {name}(TypedDict):")
        for field in fields:
            lines.append(
                f"    {field['field']}: {_python_type(str(field['transport_type']))}"
            )
        lines.append("")
    return "\n".join(lines)


def _typescript() -> str:
    authority = _load("GUI_WEAPON_EVENT_AUTHORITY.json")
    routes = _objects(_load("API_ROUTE_AUTHORITY.json").get("routes"), "routes")
    g5_routes = {
        str(item["route_id"]): {
            "method": item["method"],
            "path": item["path"],
            "responseDto": item["response_model"],
        }
        for item in routes
        if item.get("implementation_status") == "IMPLEMENTED_G5"
    }
    lines = ["// @generated from CB-1.10.0 Canonical DTO/Weapon-Event authorities; DO NOT EDIT.", ""]
    for name, fields in _dto_fields().items():
        lines.append(f"export interface {name} {{")
        for field in fields:
            lines.append(
                f"  readonly {field['field']}: {_typescript_type(str(field['transport_type']))};"
            )
        lines.extend(["}", ""])
    lines.extend(
        [
            "export const G5_WEAPON_EVENT_ROUTES = "
            + json.dumps(g5_routes, ensure_ascii=False, indent=2, sort_keys=True)
            + " as const;",
            "export const G5_WEAPON_EVENT_AUTHORITY = "
            + json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True)
            + " as const;",
            "",
        ]
    )
    return "\n".join(lines)


def render() -> dict[str, str]:
    approval = _load("G5_WEAPON_EVENT_APPROVAL.json")
    if approval.get("status") != "APPROVED_LOCAL" or approval.get("activation_status") != "ACTIVE":
        raise G5CodegenError("G5 authority is not active")
    return {
        "security": _security(),
        "application": _application(),
        "typescript": _typescript(),
        "python_dto": _python_dto(),
    }


def _manifest(rendered: Mapping[str, str]) -> dict[str, Any]:
    files = []
    for key, content in rendered.items():
        raw = content.encode("utf-8")
        files.append(
            {
                "key": key,
                "path": OUTPUTS[key].relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
    return {
        "schema": "TPAA_G5_WEAPON_EVENT_GENERATION_MANIFEST_V1",
        "core_baseline": "CB-1.10.0",
        "baseline_lock_sha256": hashlib.sha256((BASELINE / "BASELINE_LOCK.json").read_bytes()).hexdigest(),
        "files": sorted(files, key=lambda item: item["path"]),
        "release_claim": False,
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=path.parent) as temporary:
        temporary.write(content)
        candidate = Path(temporary.name)
    candidate.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        rendered = render()
        manifest = json.dumps(_manifest(rendered), ensure_ascii=False, indent=2) + "\n"
        if args.check:
            for key, content in rendered.items():
                if not OUTPUTS[key].is_file() or OUTPUTS[key].read_text(encoding="utf-8") != content:
                    raise G5CodegenError(f"generated output drift: {OUTPUTS[key]}")
            if not MANIFEST.is_file() or MANIFEST.read_text(encoding="utf-8") != manifest:
                raise G5CodegenError("manifest drift")
        else:
            for key, content in rendered.items():
                _write(OUTPUTS[key], content)
            _write(MANIFEST, manifest)
        print("G5_WEAPON_EVENT_CODEGEN_PASS routes=3 security_routes=99")
    except (OSError, ValueError, KeyError, G5CodegenError) as exc:
        print(f"G5_WEAPON_EVENT_CODEGEN_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
