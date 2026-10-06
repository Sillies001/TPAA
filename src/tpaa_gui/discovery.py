"""Shared PRCB C4 exact-product discovery helpers for Desktop workspaces."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast


class ProductDiscoveryTransport(Protocol):
    def product_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Mapping[str, object]]: ...


class ProductDiscoveryError(RuntimeError):
    """Fail-closed GUI discovery projection error."""


def product_items(
    transport: ProductDiscoveryTransport,
    kind: str,
) -> list[dict[str, object]]:
    status, payload = transport.product_request_json(
        "GET",
        f"/api/v1/discovery/products/{kind}",
    )
    if status != 200:
        raise ProductDiscoveryError(f"DISCOVERY_HTTP_ERROR:{status}")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ProductDiscoveryError("DISCOVERY_ITEMS_INVALID")
    result: list[dict[str, object]] = []
    for raw in items:
        if not isinstance(raw, Mapping):
            raise ProductDiscoveryError("DISCOVERY_ITEM_INVALID")
        exact_id = raw.get("exact_id")
        metadata = raw.get("metadata")
        if not isinstance(exact_id, str) or not exact_id:
            raise ProductDiscoveryError("DISCOVERY_EXACT_ID_INVALID")
        if not isinstance(metadata, Mapping):
            raise ProductDiscoveryError("DISCOVERY_METADATA_INVALID")
        result.append(
            {
                "exact_id": exact_id,
                "metadata": dict(cast(Mapping[str, Any], metadata)),
            }
        )
    return result


def exact_ids(
    transport: ProductDiscoveryTransport,
    kind: str,
) -> list[str]:
    return [str(item["exact_id"]) for item in product_items(transport, kind)]


def session_items(
    transport: ProductDiscoveryTransport,
) -> list[dict[str, object]]:
    status, payload = transport.product_request_json(
        "GET",
        "/api/v1/discovery/sessions",
    )
    if status != 200:
        raise ProductDiscoveryError(f"DISCOVERY_HTTP_ERROR:{status}")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ProductDiscoveryError("DISCOVERY_ITEMS_INVALID")
    return [
        dict(cast(Mapping[str, object], item))
        for item in items
        if isinstance(item, Mapping)
    ]


def release_ids(
    transport: ProductDiscoveryTransport,
    *,
    kind: str = "P1_RELEASE",
) -> list[str]:
    return exact_ids(transport, kind)


def session_release_items(
    transport: ProductDiscoveryTransport,
    session_id: str,
) -> list[dict[str, object]]:
    if not session_id:
        return []
    status, payload = transport.product_request_json(
        "GET",
        f"/api/v1/discovery/sessions/{session_id}/releases",
    )
    if status != 200:
        raise ProductDiscoveryError(f"DISCOVERY_HTTP_ERROR:{status}")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ProductDiscoveryError("DISCOVERY_ITEMS_INVALID")
    return [
        dict(cast(Mapping[str, object], item))
        for item in items
        if isinstance(item, Mapping)
    ]
