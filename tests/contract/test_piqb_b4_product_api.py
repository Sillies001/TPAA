from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request

from tpaa_api import register_product_v1_routes
from tpaa_application import ApplicationService, M8ViewerContext, M9ViewerContext

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
TOOL = ROOT / "tools" / "api" / "product_v1_contract.py"
OPENAPI = ROOT / "api" / "openapi-product-v1.json"
CLIENT = ROOT / "api" / "product-v1-client-contract.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contract() -> dict[str, object]:
    return _load(BASE / "B4_PRODUCT_API_V1_CONTRACT.json")


def _m8(_request: Request) -> M8ViewerContext:
    return M8ViewerContext(
        viewer_role="INSTRUCTOR_EVALUATOR",
        viewer_actor_id=None,
        scope_match=True,
    )


def _m9(_request: Request) -> M9ViewerContext:
    return M9ViewerContext(
        role="MODEL_REVIEWER",
        actor_id=None,
        scope_match=True,
    )


def test_product_v1_generated_openapi_and_client_contract_are_exact() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "PRODUCT_V1_CONTRACT_PASS" in result.stdout


def test_product_v1_runtime_routes_match_frozen_contract_exactly() -> None:
    contract = _contract()
    routes = contract["routes"]
    assert isinstance(routes, list)

    app = FastAPI()
    register_product_v1_routes(
        app,
        cast(ApplicationService, object()),
        m8_principal_resolver=_m8,
        m9_principal_resolver=_m9,
    )
    actual = {
        (next(iter(route.methods)), route.path, route.operation_id)
        for route in app.routes
        if hasattr(route, "methods")
        and hasattr(route, "path")
        and route.path.startswith("/api/v1/products/")
    }
    expected = {
        (
            str(item["method"]),
            str(item["path"]),
            str(item["operation_id"]),
        )
        for item in routes
        if isinstance(item, dict)
    }
    assert actual == expected
    assert len(actual) == 10


def test_product_v1_contract_forbids_alias_latest_and_hidden_recompute() -> None:
    contract = _contract()
    invariants = contract["invariants"]
    routes = contract["routes"]
    assert isinstance(invariants, dict)
    assert isinstance(routes, list)

    assert invariants["exact_ids_only"] is True
    assert invariants["mutable_latest_routes_forbidden"] is True
    assert invariants["aliases_forbidden"] is True
    assert invariants["hidden_recomputation_forbidden"] is True

    for item in routes:
        assert isinstance(item, dict)
        path = str(item["path"]).lower()
        delegate = str(item["delegates_to"])
        assert "latest" not in path
        assert "alias" not in path
        assert item["method"] == "GET"
        assert delegate.startswith("ApplicationService.")
        assert "compute" not in delegate.lower()
        assert "run_" not in delegate.lower()


def test_product_v1_openapi_extends_existing_canonical_dto_authority() -> None:
    canonical = _load(ROOT / "api" / "openapi-m0.json")
    product = _load(OPENAPI)
    contract = _contract()

    assert product["x-tpaa-authority"] == canonical["x-tpaa-authority"]
    assert product["x-tpaa-authority"] == contract["canonical_dto_authority"]
    meta = product["x-tpaa-product-api"]
    assert isinstance(meta, dict)
    assert meta["route_count"] == 10
    assert meta["api_version"] == "v1"

    canonical_schemas = canonical["components"]
    product_components = product["components"]
    assert isinstance(canonical_schemas, dict)
    assert isinstance(product_components, dict)
    canonical_schema_map = canonical_schemas["schemas"]
    product_schema_map = product_components["schemas"]
    assert isinstance(canonical_schema_map, dict)
    assert isinstance(product_schema_map, dict)
    assert set(canonical_schema_map) < set(product_schema_map)
    assert "ProductV1Envelope" in product_schema_map
    assert "CapabilityObservationDTO" in product_schema_map


def test_product_v1_client_operations_match_openapi_operation_ids() -> None:
    product = _load(OPENAPI)
    client = _load(CLIENT)
    paths = product["paths"]
    operations = client["operations"]
    assert isinstance(paths, dict)
    assert isinstance(operations, list)

    openapi_ids = {
        str(method["operationId"])
        for path in paths.values()
        if isinstance(path, dict)
        for method in path.values()
        if isinstance(method, dict)
    }
    client_ids = {
        str(item["operation_id"])
        for item in operations
        if isinstance(item, dict)
    }
    assert openapi_ids == client_ids
    assert len(client_ids) == 10


def test_product_v1_desktop_allowlist_contains_versioned_surface() -> None:
    source = (ROOT / "src" / "tpaa_api" / "desktop.py").read_text(
        encoding="utf-8"
    )
    unified = (ROOT / "src" / "tpaa_api" / "unified.py").read_text(
        encoding="utf-8"
    )
    assert '"/api/v1/"' in source
    assert "register_product_v1_routes" in unified


def test_product_v1_runtime_openapi_matches_frozen_operation_contract() -> None:
    contract = _contract()
    routes = contract["routes"]
    assert isinstance(routes, list)

    app = FastAPI()
    register_product_v1_routes(
        app,
        cast(ApplicationService, object()),
        m8_principal_resolver=_m8,
        m9_principal_resolver=_m9,
    )
    runtime = app.openapi()
    runtime_paths = runtime["paths"]
    assert isinstance(runtime_paths, dict)

    actual = {
        str(operation["operationId"])
        for path, path_item in runtime_paths.items()
        if str(path).startswith("/api/v1/products/")
        and isinstance(path_item, dict)
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    expected = {
        str(item["operation_id"])
        for item in routes
        if isinstance(item, dict)
    }
    assert actual == expected
    schemas = runtime["components"]["schemas"]
    assert "ProductV1Envelope" in schemas
    assert "ProductV1Authority" in schemas
