#!/usr/bin/env python3
"""Build or verify the local G3 CB-1.8.0 gateway successor baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "baseline" / "CB-1.7.0"
TARGET = ROOT / "baseline" / "CB-1.8.0"
CORE = "CB-1.8.0"
DECISION_ID = "G3-V33-ASYNC-GATEWAY-2026-11-06"
APPROVAL_ID = "G3-CB-1.8.0-LOCAL-CLOSURE-2026-11-06"


class G3SuccessorError(RuntimeError):
    """The G3 successor cannot be reproduced exactly."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G3SuccessorError(f"expected JSON object: {path}")
    return value


def _clone(value: object) -> Any:
    return json.loads(json.dumps(value))


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _field(name: str, transport: str, required: bool = True) -> dict[str, Any]:
    return {
        "field": name,
        "source": f"g3.{name}",
        "required": required,
        "transport_type": transport,
    }


def _dto_authority() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json"))
    value["core_baseline"] = CORE
    value["authority_version"] = "1.2.0"
    value["decision_id"] = DECISION_ID
    contracts = value.get("contracts")
    if not isinstance(contracts, dict):
        raise G3SuccessorError("DTO contracts missing")
    common = [
        _field("schema", "string"),
        _field("request_id", "string"),
        _field("reason_code", "string", False),
        _field("provenance", "object"),
    ]
    replacements = {
        "GuiCatalogDTO": common
        + [
            _field("catalog_version", "string"),
            _field("views", "object"),
            _field("modules", "object"),
            _field("features", "object"),
            _field("selectors", "object"),
            _field("routes", "object"),
        ],
        "GuiBootstrapDTO": common
        + [
            _field("catalog", "object"),
            _field("principal", "object"),
            _field("cache_partition_key", "string"),
            _field("selectors", "object"),
        ],
        "GuiSelectorDTO": common
        + [
            _field("selector_id", "string"),
            _field("query_context_id", "string"),
            _field("items", "object"),
            _field("next_cursor", "string?"),
            _field("total_count", "integer"),
        ],
        "GuiGatewayErrorDTO": common
        + [
            _field("status", "string"),
            _field("code", "string"),
            _field("retryable", "boolean"),
        ],
        "GuiCursorPageDTO": common
        + [
            _field("query_context_id", "string"),
            _field("items", "object"),
            _field("next_cursor", "string?"),
            _field("total_count", "integer"),
        ],
        "SeriesRangeDTO": common
        + [
            _field("release_id", "uuid-string"),
            _field("parameter", "string"),
            _field("unit", "string"),
            _field("time_base", "string"),
            _field("start_session_time_us", "decimal-string"),
            _field("end_session_time_us", "decimal-string"),
            _field("lod", "string"),
            _field("max_points", "integer"),
            _field("coverage", "number?"),
            _field("points", "object"),
        ],
        "MediaTicketDTO": common
        + [
            _field("ticket", "string"),
            _field("release_id", "uuid-string"),
            _field("media_id", "string"),
            _field("content_type", "string"),
            _field("size_bytes", "integer"),
            _field("range_supported", "boolean"),
            _field("expires_at", "string"),
        ],
    }
    for name, fields in replacements.items():
        contracts[name] = {"fields": fields}
    rules = value.setdefault("transport_rules", {})
    if not isinstance(rules, dict):
        raise G3SuccessorError("DTO transport_rules invalid")
    rules["g3_async_gateway"] = {
        "session_time_us": "decimal-string",
        "cursor": "opaque-versioned-string",
        "error_shape": "GuiGatewayErrorDTO",
        "reason_and_provenance_required": True,
        "absolute_local_path_forbidden": True,
    }
    return cast(dict[str, Any], value)


_G3_ROUTES = (
    (
        "gui.bootstrap",
        "GET",
        "/api/v1/gui/bootstrap",
        "bootstrap",
        "getGuiBootstrap",
        "GuiBootstrapDTO",
    ),
    (
        "gui.catalog",
        "GET",
        "/api/v1/gui/catalog",
        "catalog",
        "getGuiCatalog",
        "GuiCatalogDTO",
    ),
    (
        "gui.selector",
        "GET",
        "/api/v1/gui/selectors/{selector_id}",
        "selector",
        "getGuiSelector",
        "GuiSelectorDTO",
    ),
)


def _route_authority() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_AUTHORITY.json"))
    value.update(
        {
            "authority_version": "1.2.0",
            "core_baseline": CORE,
            "decision_id": DECISION_ID,
            "approval_status": "APPROVED_LOCAL",
            "scope": (
                "All implemented FastAPI routes plus G3 GUI catalog/bootstrap/selector reads; "
                "remaining GUI business routes stay reserved and unexposed."
            ),
        }
    )
    routes = value.get("routes")
    reserved = value.get("reserved_routes")
    if not isinstance(routes, list) or not isinstance(reserved, list):
        raise G3SuccessorError("API route authority sections invalid")
    active_ids = {route_id for route_id, *_ in _G3_ROUTES}
    remaining_reserved = [
        item
        for item in reserved
        if isinstance(item, dict) and item.get("route_id") not in active_ids
    ]
    for item in remaining_reserved:
        item["implementation_status"] = "RESERVED_G3_NOT_EXPOSED"
    value["reserved_routes"] = remaining_reserved
    for route_id, method, path, handler, operation_id, response_model in _G3_ROUTES:
        routes.append(
            {
                "method": method,
                "path": path,
                "handler": handler,
                "operation_id": operation_id,
                "response_model": response_model,
                "module": "tpaa_api.gui_gateway",
                "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
                "route_id": route_id,
                "gui_permission_id": "gui.view",
                "implementation_status": "IMPLEMENTED_G3",
            }
        )
    return cast(dict[str, Any], value)


def _route_security_authority() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"))
    routes = value.get("active_routes")
    if not isinstance(routes, list) or len(routes) != 86:
        raise G3SuccessorError("G2 route security authority must contain 86 routes")
    for offset, (logical_id, method, path, handler, _operation, _response) in enumerate(
        _G3_ROUTES,
        start=87,
    ):
        route_id = f"api.route.{offset:03d}"
        routes.append(
            {
                "route_id": route_id,
                "method": method,
                "path": path,
                "module": "tpaa_api.gui_gateway",
                "handler": handler,
                "authorization_mode": "AUTHENTICATED_GUI_PERMISSION",
                "permission_id": None,
                "gui_permission_id": "gui.view",
                "audit_mode": "ALWAYS",
                "audit_event": f"{logical_id}.read",
                "implementation_status": "IMPLEMENTED_G3",
            }
        )
    value.update(
        {
            "authority_version": "1.1.0",
            "core_baseline": CORE,
            "parent_core_baseline": "CB-1.7.0",
            "decision_id": DECISION_ID,
            "approval_id": APPROVAL_ID,
            "approval_status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "release_claim": False,
        }
    )
    value["mapping_basis"] = {
        "route_graph_source": (
            "CB-1.7.0 approved runtime graph plus three implemented G3 GUI read routes"
        ),
        "route_count": 89,
        "stable_id_rule": "Preserve api.route.001-086 and append G3 routes deterministically.",
    }
    return cast(dict[str, Any], value)


def _gateway_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_ASYNC_GATEWAY_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": CORE,
        "parent_core_baseline": "CB-1.7.0",
        "decision_id": DECISION_ID,
        "approval_id": APPROVAL_ID,
        "approval_status": "APPROVED_LOCAL",
        "activation_status": "ACTIVE",
        "routes": [
            {
                "route_id": route_id,
                "method": method,
                "path": path,
                "response_dto": response,
            }
            for route_id, method, path, _handler, _operation, response in _G3_ROUTES
        ],
        "selectors": [
            {"selector_id": "modules", "source": "MACHINE_AUTHORITY", "context": []},
            {"selector_id": "views", "source": "MACHINE_AUTHORITY", "context": []},
            {
                "selector_id": "releases",
                "source": "APPLICATION_QUERY",
                "context": ["principal", "session_id"],
            },
            {
                "selector_id": "contexts",
                "source": "APPLICATION_QUERY",
                "context": ["principal", "release_id"],
            },
            {
                "selector_id": "batches",
                "source": "APPLICATION_QUERY",
                "context": ["principal"],
            },
            {
                "selector_id": "weapon_events",
                "source": "APPLICATION_QUERY",
                "context": ["principal", "batch_id", "release_id"],
            },
            {
                "selector_id": "perspectives",
                "source": "APPLICATION_QUERY",
                "context": ["principal", "weapon_event_id"],
            },
        ],
        "request_policy": {
            "default_timeout_ms": 8000,
            "maximum_timeout_ms": 30000,
            "deduplicate_inflight": True,
            "cancel_superseded": True,
            "discard_stale_response": True,
            "retry_unsafe_methods": False,
        },
        "cache_policy": {
            "storage": "SESSION_MEMORY_ONLY",
            "partition_keys": ["principal_cache_key", "release_id"],
            "cross_principal": "FORBIDDEN",
            "cross_release": "FORBIDDEN",
            "clear_on_partition_change": True,
            "catalog_ttl_ms": 60000,
            "bootstrap_ttl_ms": 0,
            "selector_ttl_ms": 15000,
        },
        "pagination_policy": {
            "cursor": "OPAQUE_VERSIONED",
            "default_limit": 50,
            "maximum_limit": 100,
            "maximum_pages_per_collection": 100,
            "cursor_loop_policy": "ERROR",
        },
        "range_policy": {
            "session_time_transport": "DECIMAL_STRING",
            "lod_values": ["SUMMARY", "BALANCED", "DETAIL"],
            "default_max_points": 2000,
            "maximum_points": 10000,
            "preserve_extrema": True,
            "preserve_event_anchors": True,
        },
        "media_ticket_policy": {
            "ticket": "OPAQUE_SHORT_LIVED",
            "absolute_path": "FORBIDDEN",
            "range_required": True,
            "content_type_required": True,
            "size_required": True,
        },
        "error_policy": {
            "dto": "GuiGatewayErrorDTO",
            "codes": [
                "ABORTED",
                "TIMEOUT",
                "STALE_RESPONSE",
                "CURSOR_INVALID",
                "CURSOR_LOOP",
                "CONTEXT_REQUIRED",
                "FORBIDDEN",
                "NOT_FOUND",
                "BACKEND_UNAVAILABLE",
                "INVALID_RESPONSE",
                "SYSTEM_ERROR",
            ],
            "unknown": "SYSTEM_ERROR_FAIL_CLOSED",
            "reason_and_provenance_required": True,
        },
        "release_claim": False,
    }


def _approval_record() -> dict[str, Any]:
    return {
        "schema": "TPAA_G3_GATEWAY_APPROVAL_V1",
        "approval_id": APPROVAL_ID,
        "decision_id": DECISION_ID,
        "status": "APPROVED_LOCAL",
        "activation_status": "ACTIVE",
        "approved_core_baseline": CORE,
        "approved_at": "2026-11-06T00:00:00+08:00",
        "approver": "PROJECT_OWNER_G3_IMPLEMENTATION_DIRECTIVE",
        "scope": {
            "async_gateway": True,
            "catalog_bootstrap_selectors": True,
            "generated_client": True,
            "range_lod_media_ticket_contracts": True,
            "business_data_routes": False,
        },
        "restrictions": {
            "push": False,
            "production_deployment": False,
            "release_claim": False,
        },
    }


def _update_core_document(filename: str) -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / filename))
    value["core_baseline"] = CORE
    value["parent_core_baseline"] = "CB-1.7.0"
    value["decision_id"] = DECISION_ID
    value["approval_id"] = APPROVAL_ID
    value["approval_status"] = "APPROVED_LOCAL"
    value["activation_status"] = "ACTIVE"
    value["release_claim"] = False
    return cast(dict[str, Any], value)


def build_successor(output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(PARENT, output)
    canonical = output / "canonical"
    replacements = {
        "CROSS_LAYER_DTO_CONTRACTS.json": _dto_authority(),
        "API_ROUTE_AUTHORITY.json": _route_authority(),
        "API_ROUTE_SECURITY_AUTHORITY.json": _route_security_authority(),
        "GUI_PERMISSION_AUDIT_AUTHORITY.json": _update_core_document(
            "GUI_PERMISSION_AUDIT_AUTHORITY.json"
        ),
        "GUI_ROLE_VIEW_ACCESS_MATRIX.json": _update_core_document(
            "GUI_ROLE_VIEW_ACCESS_MATRIX.json"
        ),
        "GUI_VIEW_CONTRACT.json": _update_core_document("GUI_VIEW_CONTRACT.json"),
        "GUI_ASYNC_GATEWAY_AUTHORITY.json": _gateway_authority(),
        "G3_GATEWAY_APPROVAL.json": _approval_record(),
    }
    for filename, document in replacements.items():
        _write(canonical / filename, document)
    artifacts = [
        {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in sorted(canonical.glob("*.json"), key=lambda item: item.name)
    ]
    lock = {
        "baseline": {
            "overall": "TPAA V8.0",
            "engineering": "ED-2.1",
            "core": CORE,
            "db_schema": "1.10.0",
            "product": "P1_METRIC_CATALOG-1.14.0",
            "date": "2026-11-06",
            "rebaseline": "R3.5_G3_ASYNC_GATEWAY",
            "decision_id": DECISION_ID,
            "approval_id": APPROVAL_ID,
            "approval_status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "lock_lineage_sha256": [_sha256(PARENT / "BASELINE_LOCK.json")],
            "release_claim": False,
        },
        "artifacts": artifacts,
    }
    _write(output / "BASELINE_LOCK.json", lock)
    _write(
        output / "IMPORT_PROVENANCE.json",
        {
            "record_type": "G3_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": "CB-1.7.0",
            "source_baseline_lock_sha256": _sha256(PARENT / "BASELINE_LOCK.json"),
            "core_baseline": CORE,
            "db_schema_target": "1.10.0",
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (output / "README.md").write_text(
        "# CB-1.8.0 G3 async gateway successor baseline\n\n"
        f"Decision: `{DECISION_ID}`.\n\n"
        "CB-1.7.0 is the immutable direct parent. This local successor activates only "
        "GUI catalog/bootstrap/selectors and does not authorize push, production deployment "
        "or release.\n",
        encoding="utf-8",
    )


def check_successor() -> None:
    if not TARGET.is_dir():
        raise G3SuccessorError(f"successor is missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g3-successor-") as temporary:
        expected = Path(temporary) / CORE
        build_successor(expected)
        expected_digest = _directory_digest(expected)
    actual_digest = _directory_digest(TARGET)
    if actual_digest != expected_digest:
        raise G3SuccessorError(f"successor drift: {actual_digest} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.check:
            check_successor()
            print(f"G3_SUCCESSOR_PASS core={CORE} digest={_directory_digest(TARGET)}")
        else:
            build_successor(TARGET)
            print(f"G3_SUCCESSOR_BUILT core={CORE} digest={_directory_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G3SuccessorError) as exc:
        print(f"G3_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
