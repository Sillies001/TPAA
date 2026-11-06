#!/usr/bin/env python3
"""Generate the CB-1.8.0 G3 security, Application and TypeScript authorities."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.8.0"
CANONICAL = BASELINE / "canonical"
OUTPUTS = {
    "security": ROOT / "src" / "tpaa_security" / "generated_g3_authority.py",
    "application": ROOT / "src" / "tpaa_application" / "generated_g3_gateway.py",
    "typescript": ROOT / "frontend" / "gui-v33" / "src" / "generated" / "g3-gateway.ts",
}
MANIFEST = ROOT / "generated" / "g3-cb-1.8.0" / "manifest.json"


class G3GatewayCodegenError(RuntimeError):
    """G3 machine authority is missing, malformed, or drifting."""


def _load(filename: str) -> dict[str, Any]:
    value = json.loads((CANONICAL / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G3GatewayCodegenError(f"expected object: {filename}")
    return value


def _objects(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise G3GatewayCodegenError(f"expected object array: {label}")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise G3GatewayCodegenError(f"expected object: {label}[{index}]")
        result.append(item)
    return result


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise G3GatewayCodegenError(f"expected string array: {label}")
    return tuple(value)


def _security() -> str:
    gui = _load("GUI_PERMISSION_AUDIT_AUTHORITY.json")
    routes = _load("API_ROUTE_SECURITY_AUTHORITY.json")
    role_authority = gui.get("role_authority")
    bindings = _objects(gui.get("business_permission_bindings"), "GUI bindings")
    active_routes = _objects(routes.get("active_routes"), "active_routes")
    if not isinstance(role_authority, dict):
        raise G3GatewayCodegenError("role authority invalid")
    if len(active_routes) != 89:
        raise G3GatewayCodegenError("G3 route authority must contain 89 routes")
    known_roles = _strings(role_authority.get("role_ids"), "role IDs")
    gui_rows: list[tuple[str, str, tuple[str, ...]]] = []
    for index, item in enumerate(bindings):
        permission_id = item.get("permission_id")
        binding_type = item.get("binding_type")
        if not isinstance(permission_id, str) or not isinstance(binding_type, str):
            raise G3GatewayCodegenError(f"invalid GUI binding: {index}")
        business = _strings(item.get("business_permissions"), f"GUI binding {index}")
        gui_rows.append((permission_id, binding_type, business))
    route_rows: list[tuple[str, str, str, str | None, str, str | None]] = []
    for index, item in enumerate(active_routes):
        route_id = item.get("route_id")
        method = item.get("method")
        path = item.get("path")
        permission_id = item.get("permission_id")
        audit_mode = item.get("audit_mode")
        gui_permission_id = item.get("gui_permission_id")
        if (
            not isinstance(route_id, str)
            or not isinstance(method, str)
            or not isinstance(path, str)
            or not isinstance(audit_mode, str)
        ):
            raise G3GatewayCodegenError(f"invalid route identity: {index}")
        if permission_id is not None and not isinstance(permission_id, str):
            raise G3GatewayCodegenError(f"invalid route permission: {index}")
        if gui_permission_id is not None and not isinstance(gui_permission_id, str):
            raise G3GatewayCodegenError(f"invalid GUI route permission: {index}")
        route_rows.append((route_id, method, path, permission_id, audit_mode, gui_permission_id))
    lines = [
        '"""Generated from approved CB-1.8.0 authorities; do not edit manually."""',
        "",
        "from typing import Final",
        "",
        "CORE_BASELINE: Final = 'CB-1.8.0'",
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
            (
                "ROUTE_SECURITY_BINDINGS: "
                "Final[tuple[tuple[str, str, str, str | None, str, str | None], ...]] = ("
            ),
        ]
    )
    lines.extend(f"    {row!r}," for row in route_rows)
    lines.extend([")", ""])
    return "\n".join(lines)


def _application() -> str:
    gateway = _load("GUI_ASYNC_GATEWAY_AUTHORITY.json")
    registry = _load("GUI_VIEW_CONTRACT.json")
    matrix = _load("GUI_ROLE_VIEW_ACCESS_MATRIX.json")
    modules_source = json.loads(
        (ROOT / "docs" / "gui" / "demo-v33" / "V33_FINAL_VIEW_REGISTRY.json").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(modules_source, dict):
        raise G3GatewayCodegenError("view registry invalid")
    modules = _objects(modules_source.get("modules"), "modules")
    views = _objects(registry.get("views"), "views")
    roles = _objects(matrix.get("role_summary"), "role_summary")
    selectors = _objects(gateway.get("selectors"), "selectors")
    routes = _objects(gateway.get("routes"), "gateway routes")
    view_records = []
    for item in views:
        view_records.append(
            {
                "view_id": item.get("view_id"),
                "title": item.get("title"),
                "module": item.get("module"),
                "entry_type": item.get("entry_type"),
                "required_permissions": item.get("required_permissions", []),
                "feature_gates": item.get("feature_gates", []),
                "query_route_ids": item.get("query_route_ids", []),
                "mutation_route_ids": item.get("mutation_route_ids", []),
            }
        )
    role_records = {
        str(item.get("role_id")): tuple(item.get("view_ids", []))
        for item in roles
        if isinstance(item.get("role_id"), str) and isinstance(item.get("view_ids"), list)
    }
    policy = {
        key: gateway[key]
        for key in (
            "request_policy",
            "cache_policy",
            "pagination_policy",
            "range_policy",
            "media_ticket_policy",
            "error_policy",
        )
    }
    lines = [
        '"""Generated G3 GUI gateway catalog; do not edit manually."""',
        "",
        "from typing import Final",
        "",
        "CORE_BASELINE: Final = 'CB-1.8.0'",
        f"GATEWAY_AUTHORITY_ID: Final = {gateway['authority_id']!r}",
        f"GATEWAY_AUTHORITY_VERSION: Final = {gateway['authority_version']!r}",
        "GATEWAY_ACTIVATION_STATUS: Final = 'ACTIVE'",
        f"GUI_MODULES: Final[tuple[dict[str, object], ...]] = {tuple(modules)!r}",
        f"GUI_VIEWS: Final[tuple[dict[str, object], ...]] = {tuple(view_records)!r}",
        f"GUI_ROLE_VIEW_IDS: Final[dict[str, tuple[str, ...]]] = {role_records!r}",
        f"GUI_SELECTORS: Final[tuple[dict[str, object], ...]] = {tuple(selectors)!r}",
        f"GUI_GATEWAY_ROUTES: Final[tuple[dict[str, object], ...]] = {tuple(routes)!r}",
        f"GUI_GATEWAY_POLICY: Final[dict[str, object]] = {policy!r}",
        "",
    ]
    return "\n".join(lines)


def _typescript() -> str:
    gateway = _load("GUI_ASYNC_GATEWAY_AUTHORITY.json")
    routes = _objects(gateway.get("routes"), "gateway routes")
    policy = {
        key: gateway[key]
        for key in (
            "request_policy",
            "cache_policy",
            "pagination_policy",
            "range_policy",
            "media_ticket_policy",
            "error_policy",
        )
    }
    route_map = {
        str(item["route_id"]): {
            "method": item["method"],
            "path": item["path"],
            "responseDto": item["response_dto"],
        }
        for item in routes
    }
    route_json = json.dumps(route_map, ensure_ascii=False, indent=2, sort_keys=True)
    policy_json = json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""// @generated from CB-1.8.0 GUI_ASYNC_GATEWAY_AUTHORITY; DO NOT EDIT.

export type GatewayStatus = "READY" | "EMPTY" | "DEGRADED" | "ERROR" | "FORBIDDEN" | "N_A";
export type GatewayLod = "SUMMARY" | "BALANCED" | "DETAIL";

export interface GatewayProvenance {{
  readonly authorityId: string;
  readonly authorityVersion: string;
  readonly coreBaseline: string;
  readonly generatedAt?: string;
}}

export interface GatewayEnvelope {{
  readonly schema: string;
  readonly request_id: string;
  readonly reason_code?: string;
  readonly provenance: Readonly<Record<string, unknown>>;
}}

export interface GuiCatalogDTO extends GatewayEnvelope {{
  readonly catalog_version: string;
  readonly views: readonly Readonly<Record<string, unknown>>[];
  readonly modules: readonly Readonly<Record<string, unknown>>[];
  readonly features: readonly Readonly<Record<string, unknown>>[];
  readonly selectors: readonly Readonly<Record<string, unknown>>[];
  readonly routes: Readonly<Record<string, unknown>>;
}}

export interface GuiBootstrapDTO extends GatewayEnvelope {{
  readonly catalog: GuiCatalogDTO;
  readonly principal: Readonly<Record<string, unknown>>;
  readonly cache_partition_key: string;
  readonly selectors: readonly Readonly<Record<string, unknown>>[];
}}

export interface GuiSelectorDTO extends GatewayEnvelope {{
  readonly selector_id: string;
  readonly query_context_id: string;
  readonly items: readonly Readonly<Record<string, unknown>>[];
  readonly next_cursor: string | null;
  readonly total_count: number;
}}

export interface SeriesRangeRequest {{
  readonly releaseId: string;
  readonly parameter: string;
  readonly startSessionTimeUs: string;
  readonly endSessionTimeUs: string;
  readonly lod: GatewayLod;
  readonly maxPoints: number;
}}

export interface MediaTicketDTO extends GatewayEnvelope {{
  readonly ticket: string;
  readonly release_id: string;
  readonly media_id: string;
  readonly content_type: string;
  readonly size_bytes: number;
  readonly range_supported: boolean;
  readonly expires_at: string;
}}

export const G3_GATEWAY_ROUTES = {route_json} as const;
export const G3_GATEWAY_POLICY = {policy_json} as const;
"""


def render() -> dict[str, str]:
    approval = _load("G3_GATEWAY_APPROVAL.json")
    if approval.get("status") != "APPROVED_LOCAL" or approval.get("activation_status") != "ACTIVE":
        raise G3GatewayCodegenError("G3 gateway is not locally approved and active")
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
        "schema": "TPAA_G3_GATEWAY_GENERATION_MANIFEST_V1",
        "core_baseline": "CB-1.8.0",
        "baseline_lock_sha256": hashlib.sha256(
            (BASELINE / "BASELINE_LOCK.json").read_bytes()
        ).hexdigest(),
        "files": sorted(files, key=lambda item: item["path"]),
        "release_claim": False,
    }


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=path.parent,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        rendered = render()
        manifest = _manifest(rendered)
        manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            for key, content in rendered.items():
                path = OUTPUTS[key]
                if not path.is_file() or path.read_text(encoding="utf-8") != content:
                    raise G3GatewayCodegenError(f"generated output drift: {path}")
            if not MANIFEST.is_file() or MANIFEST.read_text(encoding="utf-8") != manifest_text:
                raise G3GatewayCodegenError("generation manifest drift")
            print("G3_GATEWAY_CODEGEN_PASS routes=3 security_routes=89")
        else:
            for key, content in rendered.items():
                _write_atomic(OUTPUTS[key], content)
            _write_atomic(MANIFEST, manifest_text)
            print("G3_GATEWAY_CODEGEN_BUILT routes=3 security_routes=89")
    except (OSError, ValueError, KeyError, G3GatewayCodegenError) as exc:
        print(f"G3_GATEWAY_CODEGEN_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
