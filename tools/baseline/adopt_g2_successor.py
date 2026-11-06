#!/usr/bin/env python3
"""Build or verify the locally approved G2 CB-1.7.0 successor baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")

from tpaa_security import Permission  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "baseline" / "CB-1.6.0"
PROPOSAL = ROOT / "baseline" / "candidates" / "CB-1.7.0"
TARGET = ROOT / "baseline" / "CB-1.7.0"
DECISION_ID = "G2-V33-GUI-PERMISSION-MAPPING-CANDIDATE-2026-11-06"
APPROVAL_ID = "G2-CB-1.7.0-LOCAL-ACTIVATION-2026-11-06"


class G2SuccessorError(RuntimeError):
    """The approved G2 successor cannot be reproduced exactly."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G2SuccessorError(f"expected JSON object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _legacy_permission(method: str, path: str) -> Permission | None:
    """Freeze the pre-CB-1.7.0 classifier while building the explicit authority."""

    normalized_method = method.upper()
    lowered = path.lower()
    status_paths = {
        "/health",
        "/readiness",
        "/version",
        "/runtime/features",
        "/runtime/qualification",
        "/runtime/observability",
        "/runtime/metrics",
        "/security/session",
    }
    if path in status_paths or path in {"/ui", "/ui/{asset_path:path}"}:
        return None
    if lowered == "/security/approvals" and normalized_method == "POST":
        return None
    if lowered.startswith("/security/approvals"):
        return Permission.APPROVAL_REVIEW
    if "export" in lowered:
        return Permission.EXPORT_DEIDENTIFIED
    if "plugin" in lowered and normalized_method != "GET":
        return Permission.PLUGIN_INSTALL if "install" in lowered else Permission.PLUGIN_ENABLE
    if "override" in lowered and normalized_method != "GET":
        return Permission.PUBLICATION_OVERRIDE
    if "model" in lowered and any(term in lowered for term in ("publish", "release")):
        return Permission.MODEL_RELEASE
    if normalized_method != "GET" and lowered.endswith("/replay"):
        return Permission.COMPUTE_EXECUTE
    if normalized_method == "DELETE" and "release" in lowered:
        return Permission.WITHDRAW_RELEASE
    if normalized_method != "GET" and any(
        term in lowered for term in ("publish", "/release", "/releases")
    ):
        return Permission.PRODUCT_PUBLISH
    if "annotation" in lowered and normalized_method != "GET":
        return Permission.ANNOTATION_WRITE
    if normalized_method != "GET" and any(
        term in lowered for term in ("/source", "/import", "/ingest")
    ):
        return Permission.SOURCE_IMPORT
    if normalized_method != "GET" and any(
        term in lowered for term in ("/config", "/context", "/profile", "/rule")
    ):
        return Permission.CONFIGURATION_WRITE
    if normalized_method != "GET":
        return Permission.COMPUTE_EXECUTE
    if any(term in lowered for term in ("/source", "/raw")):
        return Permission.RAW_DATA_READ
    return Permission.DERIVED_DATA_READ


def _runtime_routes() -> list[dict[str, str]]:
    """Return the immutable route graph observed when G2 was approved.

    G3 and later stages add runtime routes.  Reconstructing a closed G2 baseline
    from the live graph would silently rewrite its historical evidence, so the
    graph is derived only from the frozen G2 proposal plus the 15 routes that
    were explicitly appended during local activation.
    """

    proposal = _load(PROPOSAL / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    source = proposal.get("active_routes")
    if not isinstance(source, list):
        raise G2SuccessorError("candidate active_routes missing")
    records = []
    for item in source:
        if not isinstance(item, dict):
            raise G2SuccessorError("candidate route entry is not an object")
        record = {key: item.get(key) for key in ("method", "path", "module", "handler")}
        if not all(isinstance(value, str) for value in record.values()):
            raise G2SuccessorError("candidate route graph metadata is incomplete")
        records.append(cast(dict[str, str], record))
    records.extend(
        [
            {
                "method": "GET",
                "path": "/api/v1/sources/adapters",
                "module": "tpaa_api.source_v1",
                "handler": "adapters",
            },
            {
                "method": "GET",
                "path": "/m1/releases/{release_id}/world-graph",
                "module": "tpaa_api.m1_app",
                "handler": "world_graph",
            },
            {
                "method": "GET",
                "path": "/runtime/external-capabilities",
                "module": "tpaa_api.runtime",
                "handler": "runtime_external_capabilities",
            },
            {
                "method": "GET",
                "path": "/runtime/final-qualification",
                "module": "tpaa_api.runtime",
                "handler": "runtime_final_qualification",
            },
            {
                "method": "GET",
                "path": "/runtime/operations",
                "module": "tpaa_api.runtime",
                "handler": "runtime_operations",
            },
            {
                "method": "GET",
                "path": "/security/approvals",
                "module": "tpaa_api.security",
                "handler": "approval_inbox",
            },
            {
                "method": "GET",
                "path": "/security/session",
                "module": "tpaa_api.security",
                "handler": "session_context",
            },
            {"method": "GET", "path": "/ui", "module": "tpaa_api.desktop", "handler": "web_index"},
            {
                "method": "GET",
                "path": "/ui/{asset_path:path}",
                "module": "tpaa_api.desktop",
                "handler": "web_asset",
            },
            {
                "method": "POST",
                "path": "/api/v1/sources/flight-csv/inspect",
                "module": "tpaa_api.source_v1",
                "handler": "inspect_flight_csv",
            },
            {
                "method": "POST",
                "path": "/api/v1/sources/flight-csv/stage",
                "module": "tpaa_api.source_v1",
                "handler": "stage_flight_csv",
            },
            {
                "method": "POST",
                "path": "/api/v1/sources/p1-request/stage",
                "module": "tpaa_api.source_v1",
                "handler": "stage_p1_request",
            },
            {
                "method": "POST",
                "path": "/m1/episodes/{episode_id}/revisions",
                "module": "tpaa_api.m1_app",
                "handler": "revise_episode",
            },
            {
                "method": "POST",
                "path": "/security/approvals",
                "module": "tpaa_api.security",
                "handler": "request_approval",
            },
            {
                "method": "POST",
                "path": "/security/approvals/{approval_id}/decision",
                "module": "tpaa_api.security",
                "handler": "decide_approval",
            },
        ]
    )
    records.sort(key=lambda item: (item["method"], item["path"]))
    if len({(item["method"], item["path"]) for item in records}) != len(records):
        raise G2SuccessorError("runtime route graph contains duplicate method/path bindings")
    return records


def _approved(value: dict[str, Any]) -> dict[str, Any]:
    result = cast(dict[str, Any], json.loads(json.dumps(value)))
    result["approval_status"] = "APPROVED_LOCAL"
    result["activation_status"] = "ACTIVE"
    version = result.get("authority_version")
    if isinstance(version, str):
        result["authority_version"] = version.removesuffix("-candidate")
    result["approval_id"] = APPROVAL_ID
    result["release_claim"] = False
    return result


def _route_authority() -> dict[str, Any]:
    source = _load(PROPOSAL / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    existing = source.get("active_routes")
    if not isinstance(existing, list):
        raise G2SuccessorError("candidate active_routes missing")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    used_ids: set[str] = set()
    for item in existing:
        if not isinstance(item, dict):
            raise G2SuccessorError("candidate route entry is not an object")
        method = item.get("method")
        path = item.get("path")
        route_id = item.get("route_id")
        if not all(isinstance(value, str) for value in (method, path, route_id)):
            raise G2SuccessorError("candidate route identity is invalid")
        key = (str(method), str(path))
        if key in by_key or str(route_id) in used_ids:
            raise G2SuccessorError("candidate route ID or method/path is duplicated")
        by_key[key] = dict(item)
        used_ids.add(str(route_id))

    runtime = _runtime_routes()
    runtime_keys = {(item["method"], item["path"]) for item in runtime}
    stale = sorted(set(by_key) - runtime_keys)
    if stale:
        raise G2SuccessorError(f"candidate contains stale routes: {stale}")
    next_id = max(int(value.rsplit(".", 1)[1]) for value in used_ids) + 1
    approved_routes: list[dict[str, Any]] = []
    for runtime_item in runtime:
        key = (runtime_item["method"], runtime_item["path"])
        permission = _legacy_permission(*key)
        permission_id = None if permission is None else permission.value
        prior = by_key.get(key)
        if prior is not None:
            if prior.get("permission_id") != permission_id:
                raise G2SuccessorError(
                    f"candidate permission drift for {key}: "
                    f"{prior.get('permission_id')} != {permission_id}"
                )
            route_id = str(prior["route_id"])
        else:
            route_id = f"api.route.{next_id:03d}"
            next_id += 1
        approved_routes.append(
            {
                "route_id": route_id,
                **runtime_item,
                "authorization_mode": (
                    "AUTHENTICATED_STATUS" if permission_id is None else "BUSINESS_PERMISSION"
                ),
                "permission_id": permission_id,
                "audit_mode": "NONE" if permission_id is None else "ALWAYS",
                "audit_event": f"{route_id}.authorization",
                "implementation_status": "EXISTING_RUNTIME_ROUTE",
            }
        )
    approved_routes.sort(key=lambda item: int(str(item["route_id"]).rsplit(".", 1)[1]))
    result = _approved(source)
    result["active_routes"] = approved_routes
    result["mapping_basis"] = {
        "route_graph_source": (
            "Union of FastAPI APIRoute graphs from create_unified_service_app "
            "and create_desktop_app"
        ),
        "permission_semantics_source": "frozen pre-CB-1.7.0 route classifier",
        "route_count": len(approved_routes),
        "stable_id_rule": "Preserve api.route.001-071; append newly observed routes deterministically.",
    }
    return result


def _approval_record(route_count: int) -> dict[str, Any]:
    return {
        "schema": "TPAA_G2_GUI_SECURITY_APPROVAL_V1",
        "approval_id": APPROVAL_ID,
        "decision_id": DECISION_ID,
        "status": "APPROVED_LOCAL",
        "activation_status": "ACTIVE",
        "approved_core_baseline": "CB-1.7.0",
        "approved_at": "2026-11-06T00:00:00+08:00",
        "approver": "PROJECT_OWNER_DIRECT_AUTHORIZATION",
        "authorization_text": (
            "正式批准 TPAA CB-1.7.0 G2 GUI 权限与 API 路由安全权威候选，"
            "并授权仅在本地激活、验收及关闭 G2。"
        ),
        "scope": {
            "gui_permissions": True,
            "role_view_matrix": True,
            "api_route_security_authority": True,
            "runtime_route_count": route_count,
            "g2_local_closure": True,
        },
        "restrictions": {
            "push": False,
            "production_deployment": False,
            "release_claim": False,
        },
    }


def build_successor(output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(PARENT, output)
    canonical = output / "canonical"
    replacements = {
        "GUI_VIEW_CONTRACT.json": _approved(
            _load(PROPOSAL / "canonical" / "GUI_VIEW_CONTRACT.json")
        ),
        "GUI_PERMISSION_AUDIT_AUTHORITY.json": _approved(
            _load(PROPOSAL / "canonical" / "GUI_PERMISSION_AUDIT_AUTHORITY.json")
        ),
        "GUI_ROLE_VIEW_ACCESS_MATRIX.json": _approved(
            _load(PROPOSAL / "canonical" / "GUI_ROLE_VIEW_ACCESS_MATRIX.json")
        ),
        "API_ROUTE_SECURITY_AUTHORITY.json": _route_authority(),
    }
    for filename, document in replacements.items():
        _write(canonical / filename, document)
    _write(
        canonical / "G2_GUI_SECURITY_APPROVAL.json",
        _approval_record(len(replacements["API_ROUTE_SECURITY_AUTHORITY.json"]["active_routes"])),
    )
    artifacts = []
    for path in sorted(canonical.glob("*.json"), key=lambda item: item.name):
        artifacts.append({"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size})
    lock = {
        "baseline": {
            "overall": "TPAA V8.0",
            "engineering": "ED-2.1",
            "core": "CB-1.7.0",
            "db_schema": "1.10.0",
            "product": "P1_METRIC_CATALOG-1.14.0",
            "date": "2026-11-06",
            "rebaseline": "R3.4_G2_GUI_SECURITY_ACTIVATION",
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


def check_successor() -> None:
    if not TARGET.is_dir():
        raise G2SuccessorError(f"approved successor is missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g2-successor-") as temporary:
        expected = Path(temporary) / "CB-1.7.0"
        build_successor(expected)
        expected_digest = _directory_digest(expected)
    actual_digest = _directory_digest(TARGET)
    if actual_digest != expected_digest:
        raise G2SuccessorError(f"CB-1.7.0 successor drift: {actual_digest} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.check:
            check_successor()
            print(f"G2_SUCCESSOR_PASS core=CB-1.7.0 digest={_directory_digest(TARGET)}")
        else:
            build_successor(TARGET)
            print(f"G2_SUCCESSOR_BUILT core=CB-1.7.0 digest={_directory_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G2SuccessorError) as exc:
        print(f"G2_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
