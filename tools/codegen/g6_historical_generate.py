#!/usr/bin/env python3
"""Generate CB-1.11.0 G6 security, gateway and TypeScript Historical-overview authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.11.0"
CANONICAL = BASELINE / "canonical"
OUTPUTS = {
    "security": ROOT / "src" / "tpaa_security" / "generated_g6_authority.py",
    "application": ROOT / "src" / "tpaa_application" / "generated_g6_gateway.py",
    "typescript": ROOT / "frontend" / "gui-v33" / "src" / "generated" / "g6-historical.ts",
}
MANIFEST = ROOT / "generated" / "g6-cb-1.11.0" / "manifest.json"


class G6CodegenError(RuntimeError):
    pass


def _load(name: str) -> dict[str, Any]:
    value = json.loads((CANONICAL / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G6CodegenError(f"expected object: {name}")
    return value


def _objects(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise G6CodegenError(f"expected object array: {label}")
    return list(value)


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise G6CodegenError(f"expected strings: {label}")
    return tuple(value)


def _security() -> str:
    gui = _load("GUI_PERMISSION_AUDIT_AUTHORITY.json")
    route_authority = _load("API_ROUTE_SECURITY_AUTHORITY.json")
    role_authority = gui.get("role_authority")
    if not isinstance(role_authority, dict):
        raise G6CodegenError("role authority invalid")
    bindings = _objects(gui.get("business_permission_bindings"), "GUI bindings")
    routes = _objects(route_authority.get("active_routes"), "active routes")
    if len(routes) != 100:
        raise G6CodegenError("G6 route authority must contain 100 routes")
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
            raise G6CodegenError("route permission invalid")
        if gui_permission is not None and not isinstance(gui_permission, str):
            raise G6CodegenError("GUI route permission invalid")
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
        '"""Generated from approved CB-1.11.0 authorities; do not edit manually."""',
        "",
        "from typing import Final",
        "",
        "CORE_BASELINE: Final = 'CB-1.11.0'",
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
    parent = (ROOT / "src" / "tpaa_application" / "generated_g5_gateway.py").read_text(
        encoding="utf-8"
    )
    return parent.replace("Generated G5", "Generated G6").replace("CB-1.10.0", "CB-1.11.0")


_G6_DTOS = (
    "BatchOverviewSummaryDTO",
    "TaskMetricTrendDTO",
    "EquipmentMetricTrendDTO",
    "HistoricalTrainingOverviewDTO",
)


def _dto_fields() -> dict[str, list[dict[str, Any]]]:
    contracts = _load("CROSS_LAYER_DTO_CONTRACTS.json").get("contracts")
    if not isinstance(contracts, dict):
        raise G6CodegenError("DTO contracts invalid")
    result: dict[str, list[dict[str, Any]]] = {}
    for name in _G6_DTOS:
        contract = contracts.get(name)
        if not isinstance(contract, dict):
            raise G6CodegenError(f"missing DTO contract: {name}")
        result[name] = _objects(contract.get("fields"), f"{name}.fields")
    return result


def _typescript_type(transport_type: str) -> str:
    mapping = {
        "string": "string",
        "string?": "string | null",
        "uuid-string": "string",
        "uuid-string?": "string | null",
        "decimal-string": "string",
        "decimal-string?": "string | null",
        "integer": "number",
        "integer?": "number | null",
        "boolean": "boolean",
        "object": "Readonly<Record<string, unknown>>",
    }
    try:
        return mapping[transport_type]
    except KeyError as exc:
        raise G6CodegenError(f"unsupported G6 TypeScript DTO type: {transport_type}") from exc


def _typescript() -> str:
    approval = _load("G6_HISTORICAL_OVERVIEW_APPROVAL.json")
    authority = _load("GUI_HISTORICAL_OVERVIEW_AUTHORITY.json")
    if authority.get("activation_status") != "ACTIVE":
        raise G6CodegenError("G6 historical authority is not active")
    routes = _objects(_load("API_ROUTE_AUTHORITY.json").get("routes"), "routes")
    g6_routes = {
        str(item["route_id"]): {
            "method": item["method"],
            "path": item["path"],
            "responseDto": item["response_model"],
        }
        for item in routes
        if item.get("implementation_status") == "IMPLEMENTED_G6"
    }
    lines = ["// @generated from CB-1.11.0 Canonical DTO/Historical-overview authorities; DO NOT EDIT.", ""]
    for name, fields in _dto_fields().items():
        lines.append(f"export interface {name} {{")
        for field in fields:
            lines.append(
                f"  readonly {field['field']}: {_typescript_type(str(field['transport_type']))};"
            )
        lines.extend(["}", ""])
    lines.extend(
        [
            "export const G6_HISTORICAL_ROUTES = "
            + json.dumps(g6_routes, ensure_ascii=False, indent=2, sort_keys=True)
            + " as const;",
            "export const G6_HISTORICAL_AUTHORITY = "
            + json.dumps(approval | authority, ensure_ascii=False, indent=2, sort_keys=True)
            + " as const;",
            "",
        ]
    )
    return "\n".join(lines)


def render() -> dict[str, str]:
    approval = _load("G6_HISTORICAL_OVERVIEW_APPROVAL.json")
    if approval.get("status") != "APPROVED_LOCAL" or approval.get("activation_status") != "ACTIVE":
        raise G6CodegenError("G6 authority is not active")
    return {
        "security": _security(),
        "application": _application(),
        "typescript": _typescript(),
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
        "schema": "TPAA_G6_HISTORICAL_GENERATION_MANIFEST_V1",
        "core_baseline": "CB-1.11.0",
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
                    raise G6CodegenError(f"generated output drift: {OUTPUTS[key]}")
            if not MANIFEST.is_file() or MANIFEST.read_text(encoding="utf-8") != manifest:
                raise G6CodegenError("manifest drift")
        else:
            for key, content in rendered.items():
                _write(OUTPUTS[key], content)
            _write(MANIFEST, manifest)
        print("G6_HISTORICAL_CODEGEN_PASS routes=1 security_routes=100 files=3")
    except (OSError, ValueError, KeyError, G6CodegenError) as exc:
        print(f"G6_HISTORICAL_CODEGEN_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
