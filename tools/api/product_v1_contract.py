#!/usr/bin/env python3
"""Generate/check PIQB B4 Product API v1 OpenAPI and client contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
for entry in (str(ROOT), str(SRC_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from tools.api.openapi_snapshot import build_snapshot  # noqa: E402

CONTRACT = ROOT / "docs" / "baseline" / "PIQB-1.0" / "B4_PRODUCT_API_V1_CONTRACT.json"
DEFAULT_OPENAPI = ROOT / "api" / "openapi-product-v1.json"
DEFAULT_CLIENT = ROOT / "api" / "product-v1-client-contract.json"
_PATH_PARAM = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _load_contract() -> dict[str, Any]:
    raw = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("B4 Product API contract root must be object")
    return cast(dict[str, Any], raw)


def _validate_contract(contract: dict[str, Any]) -> list[dict[str, Any]]:
    if contract.get("schema") != "TPAA_PRODUCT_API_V1_CONTRACT_V1":
        raise ValueError("Product API contract schema mismatch")
    if contract.get("api_version") != "v1":
        raise ValueError("Product API version mismatch")
    base_path = contract.get("base_path")
    authority = contract.get("canonical_dto_authority")
    invariants = contract.get("invariants")
    routes = contract.get("routes")
    if (
        not isinstance(base_path, str)
        or not isinstance(authority, dict)
        or not isinstance(invariants, dict)
        or not isinstance(routes, list)
    ):
        raise ValueError("Product API contract structure invalid")
    required_invariants = {
        "exact_ids_only",
        "mutable_latest_routes_forbidden",
        "aliases_forbidden",
        "hidden_recomputation_forbidden",
        "existing_stage_routes_remain_compatibility_surface",
        "m8_p6_security_policies_remain_authoritative",
    }
    if any(invariants.get(key) is not True for key in required_invariants):
        raise ValueError("Product API invariant is not fail-closed")

    normalized: list[dict[str, Any]] = []
    operation_ids: set[str] = set()
    paths: set[str] = set()
    for raw in routes:
        if not isinstance(raw, dict):
            raise ValueError("Product API route must be object")
        route = cast(dict[str, Any], raw)
        method = route.get("method")
        path = route.get("path")
        operation_id = route.get("operation_id")
        exact_id_params = route.get("exact_id_params")
        phase = route.get("phase")
        product_kind = route.get("product_kind")
        delegates_to = route.get("delegates_to")
        if (
            method != "GET"
            or not isinstance(path, str)
            or not path.startswith(base_path + "/")
            or not isinstance(operation_id, str)
            or not operation_id
            or not isinstance(exact_id_params, list)
            or not exact_id_params
            or not all(isinstance(item, str) and item for item in exact_id_params)
            or not isinstance(phase, str)
            or phase not in {"P1", "P2", "P3", "P4", "P5", "P6"}
            or not isinstance(product_kind, str)
            or not product_kind
            or not isinstance(delegates_to, str)
            or not delegates_to.startswith("ApplicationService.")
        ):
            raise ValueError(f"Product API route invalid: {route!r}")
        declared = _PATH_PARAM.findall(path)
        if declared != exact_id_params:
            raise ValueError(f"Product API exact-ID parameter drift: {path}")
        lowered = path.lower()
        if "latest" in lowered or "alias" in lowered:
            raise ValueError(f"mutable alias/latest route forbidden: {path}")
        if operation_id in operation_ids or path in paths:
            raise ValueError("duplicate Product API route identity")
        operation_ids.add(operation_id)
        paths.add(path)
        normalized.append(route)
    if len(normalized) != 10:
        raise ValueError("Product API v1 must expose exactly 10 frozen read routes")
    return normalized


def _authority_exact(
    contract: dict[str, Any],
    canonical_openapi: dict[str, object],
) -> dict[str, object]:
    contract_authority = contract["canonical_dto_authority"]
    canonical_authority = canonical_openapi.get("x-tpaa-authority")
    if contract_authority != canonical_authority:
        raise ValueError("Product API canonical DTO authority drift")
    return cast(dict[str, object], dict(contract_authority))


def build_product_openapi() -> dict[str, object]:
    contract = _load_contract()
    routes = _validate_contract(contract)
    output = build_snapshot()
    authority = _authority_exact(contract, output)

    output["info"] = {
        "title": "TPAA Product API v1",
        "version": "1.0.0",
    }
    components = output["components"]
    if not isinstance(components, dict):
        raise ValueError("canonical OpenAPI components invalid")
    schemas = components["schemas"]
    if not isinstance(schemas, dict):
        raise ValueError("canonical OpenAPI schemas invalid")

    schemas["ProductV1Authority"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "artifact_id": {"type": "string"},
            "artifact_version": {"type": "string"},
            "core_baseline": {"type": "string"},
            "sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
        },
        "required": [
            "artifact_id",
            "artifact_version",
            "core_baseline",
            "sha256",
        ],
    }
    schemas["ProductV1Envelope"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "api_version": {"type": "string", "const": "v1"},
            "phase": {
                "type": "string",
                "enum": ["P1", "P2", "P3", "P4", "P5", "P6"],
            },
            "product_kind": {"type": "string"},
            "exact_ids": {
                "type": "object",
                "additionalProperties": {"type": "string", "format": "uuid"},
            },
            "authority": {"$ref": "#/components/schemas/ProductV1Authority"},
            "payload": {"type": "object", "additionalProperties": True},
        },
        "required": [
            "api_version",
            "phase",
            "product_kind",
            "exact_ids",
            "authority",
            "payload",
        ],
    }
    schemas["ProductV1SystemError"] = {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "outcome": {"type": "string", "const": "SYSTEM_ERROR"},
            "error": {"type": "object", "additionalProperties": True},
        },
        "required": ["outcome", "error"],
    }

    paths: dict[str, object] = {}
    for route in routes:
        parameters = [
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
            }
            for name in route["exact_id_params"]
        ]
        paths[route["path"]] = {
            "get": {
                "operationId": route["operation_id"],
                "tags": ["Product API v1", route["phase"]],
                "summary": route["product_kind"],
                "parameters": parameters,
                "responses": {
                    "200": {
                        "description": "Exact immutable product projection",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProductV1Envelope"
                                }
                            }
                        },
                    },
                    "403": {
                        "description": "Principal not authorized",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProductV1SystemError"
                                }
                            }
                        },
                    },
                    "404": {
                        "description": "Exact product ID not found",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProductV1SystemError"
                                }
                            }
                        },
                    },
                    "409": {
                        "description": "Exact identity/scope conflict",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProductV1SystemError"
                                }
                            }
                        },
                    },
                    "422": {
                        "description": "Invalid exact identifier or projection request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProductV1SystemError"
                                }
                            }
                        },
                    },
                },
                "x-tpaa-phase": route["phase"],
                "x-tpaa-product-kind": route["product_kind"],
                "x-tpaa-exact-id-params": route["exact_id_params"],
                "x-tpaa-delegates-to": route["delegates_to"],
            }
        }

    output["paths"] = paths
    output["x-tpaa-authority"] = authority
    output["x-tpaa-product-api"] = {
        "schema": contract["schema"],
        "api_version": contract["api_version"],
        "base_path": contract["base_path"],
        "invariants": contract["invariants"],
        "route_count": len(routes),
    }
    return output


def build_client_contract() -> dict[str, object]:
    contract = _load_contract()
    routes = _validate_contract(contract)
    canonical = build_snapshot()
    authority = _authority_exact(contract, canonical)
    return {
        "schema": "TPAA_PRODUCT_V1_CLIENT_CONTRACT_V1",
        "api_version": "v1",
        "authority": authority,
        "operations": [
            {
                "operation_id": route["operation_id"],
                "method": route["method"],
                "path": route["path"],
                "phase": route["phase"],
                "product_kind": route["product_kind"],
                "exact_id_params": route["exact_id_params"],
                "response_schema": "ProductV1Envelope",
            }
            for route in routes
        ],
        "invariants": contract["invariants"],
    }


def _serialized(value: dict[str, object]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _check(path: Path, expected: str) -> bool:
    try:
        actual = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"PRODUCT_V1_CONTRACT_FAIL missing={path}", file=sys.stderr)
        return False
    if actual != expected:
        print(f"PRODUCT_V1_CONTRACT_FAIL drift={path}", file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openapi-output", type=Path, default=DEFAULT_OPENAPI)
    parser.add_argument("--client-output", type=Path, default=DEFAULT_CLIENT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    openapi = _serialized(build_product_openapi())
    client = _serialized(build_client_contract())
    if args.check:
        ok = _check(args.openapi_output, openapi)
        ok = _check(args.client_output, client) and ok
        if ok:
            print(
                "PRODUCT_V1_CONTRACT_PASS "
                f"openapi={args.openapi_output} client={args.client_output}"
            )
        return 0 if ok else 2

    for path, content in (
        (args.openapi_output, openapi),
        (args.client_output, client),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"PRODUCT_V1_CONTRACT_WRITE path={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
