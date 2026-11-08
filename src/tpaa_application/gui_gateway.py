"""G3 Application-owned GUI catalog, bootstrap and selector read models."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass

from .generated_g9_gateway import (
    CORE_BASELINE,
    GATEWAY_ACTIVATION_STATUS,
    GATEWAY_AUTHORITY_ID,
    GATEWAY_AUTHORITY_VERSION,
    GUI_GATEWAY_POLICY,
    GUI_GATEWAY_ROUTES,
    GUI_MODULES,
    GUI_SELECTORS,
    GUI_VIEWS,
)


class GuiGatewayError(ValueError):
    """Stable fail-closed error from the G3 GUI Application boundary."""

    def __init__(
        self,
        code: str,
        *,
        http_status: int = 400,
        retryable: bool = False,
        reason_code: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.retryable = retryable
        self.reason_code = reason_code or code


@dataclass(frozen=True, slots=True)
class GuiGatewayPrincipal:
    """Authenticated principal projection used only inside Application."""

    subject: str
    roles: tuple[str, ...]
    gui_permissions: tuple[str, ...]
    resource_scopes: tuple[str, ...]

    @property
    def cache_partition_key(self) -> str:
        material = json.dumps(
            {
                "subject": self.subject,
                "roles": sorted(self.roles),
                "resource_scopes": sorted(self.resource_scopes),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"principal:{hashlib.sha256(material).hexdigest()}"


def _provenance(core_baseline: str) -> dict[str, object]:
    return {
        "authority_id": GATEWAY_AUTHORITY_ID,
        "authority_version": GATEWAY_AUTHORITY_VERSION,
        "core_baseline": core_baseline,
        "activation_status": GATEWAY_ACTIVATION_STATUS,
    }


def _query_context_id(
    principal: GuiGatewayPrincipal,
    selector_id: str,
    release_id: str | None,
) -> str:
    value = json.dumps(
        {
            "partition": principal.cache_partition_key,
            "selector": selector_id,
            "release_id": release_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"query:{hashlib.sha256(value).hexdigest()[:32]}"


def _encode_cursor(selector_id: str, query_context_id: str, offset: int) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "selector": selector_id,
            "query_context_id": query_context_id,
            "offset": offset,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    checksum = hashlib.sha256(payload + GATEWAY_AUTHORITY_VERSION.encode("ascii")).hexdigest()[:16]
    wrapped = json.dumps(
        {"payload": base64.urlsafe_b64encode(payload).decode("ascii"), "checksum": checksum},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(wrapped).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str, selector_id: str, query_context_id: str) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        wrapped = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        encoded = wrapped["payload"]
        payload = base64.urlsafe_b64decode(encoded)
        checksum = hashlib.sha256(payload + GATEWAY_AUTHORITY_VERSION.encode("ascii")).hexdigest()[
            :16
        ]
        if wrapped["checksum"] != checksum:
            raise ValueError("checksum")
        value = json.loads(payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GuiGatewayError("CURSOR_INVALID") from exc
    if (
        value.get("v") != 1
        or value.get("selector") != selector_id
        or value.get("query_context_id") != query_context_id
        or not isinstance(value.get("offset"), int)
        or value["offset"] < 0
    ):
        raise GuiGatewayError("CURSOR_INVALID")
    return int(value["offset"])


class GuiGatewayService:
    """Compose safe GUI read models without reading Canonical data from transport/UI."""

    def __init__(self, *, core_baseline: str = CORE_BASELINE) -> None:
        if not core_baseline.startswith("CB-"):
            raise ValueError("GUI_GATEWAY_CORE_BASELINE_INVALID")
        self._core_baseline = core_baseline

    def _authorized_views(self, principal: GuiGatewayPrincipal) -> list[dict[str, object]]:
        grants = set(principal.gui_permissions)
        result = []
        for source in GUI_VIEWS:
            required = source.get("required_permissions")
            if not isinstance(required, list) or not required:
                continue
            if set(str(value) for value in required).issubset(grants):
                result.append(dict(source))
        return result

    def catalog(
        self,
        principal: GuiGatewayPrincipal,
        *,
        request_id: str,
    ) -> dict[str, object]:
        views = self._authorized_views(principal)
        view_modules = {str(item["module"]) for item in views}
        modules = [dict(item) for item in GUI_MODULES if str(item.get("id")) in view_modules]
        return {
            "schema": "TPAA_GUI_CATALOG_V1",
            "request_id": request_id,
            "provenance": _provenance(self._core_baseline),
            "catalog_version": f"{self._core_baseline}:{GATEWAY_AUTHORITY_VERSION}",
            "views": views,
            "modules": modules,
            "features": [
                {"feature_id": "ASYNC_GATEWAY", "status": "READY"},
                {"feature_id": "CATALOG_BOOTSTRAP_SELECTORS", "status": "READY"},
                {
                    "feature_id": "G4_PLUS_BUSINESS_READ_MODELS",
                    "status": "N_A",
                    "reason_code": "PROJECTION_UNAVAILABLE",
                },
            ],
            "selectors": [dict(item) for item in GUI_SELECTORS],
            "routes": {str(item["route_id"]): dict(item) for item in GUI_GATEWAY_ROUTES},
        }

    def bootstrap(
        self,
        principal: GuiGatewayPrincipal,
        *,
        request_id: str,
    ) -> dict[str, object]:
        return {
            "schema": "TPAA_GUI_BOOTSTRAP_V1",
            "request_id": request_id,
            "provenance": _provenance(self._core_baseline),
            "catalog": self.catalog(principal, request_id=request_id),
            "principal": {
                "roles": list(principal.roles),
                "gui_permissions": list(principal.gui_permissions),
                "resource_scope_count": len(principal.resource_scopes),
            },
            "cache_partition_key": principal.cache_partition_key,
            "selectors": [dict(item) for item in GUI_SELECTORS],
        }

    def selector(
        self,
        principal: GuiGatewayPrincipal,
        selector_id: str,
        *,
        request_id: str,
        release_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        pagination = GUI_GATEWAY_POLICY["pagination_policy"]
        if not isinstance(pagination, dict):
            raise GuiGatewayError("SYSTEM_ERROR", http_status=500)
        maximum = pagination.get("maximum_limit")
        if not isinstance(maximum, int) or limit < 1 or limit > maximum:
            raise GuiGatewayError("CURSOR_INVALID")
        known = {str(item.get("selector_id")) for item in GUI_SELECTORS}
        if selector_id not in known:
            raise GuiGatewayError("NOT_FOUND", http_status=404)
        query_context_id = _query_context_id(principal, selector_id, release_id)
        offset = 0 if cursor is None else _decode_cursor(cursor, selector_id, query_context_id)
        if selector_id == "modules":
            catalog_modules = self.catalog(principal, request_id=request_id).get("modules")
            if not isinstance(catalog_modules, list):
                raise GuiGatewayError("SYSTEM_ERROR", http_status=500)
            source_items = [
                {"id": item.get("id"), "label": item.get("label"), "landing": item.get("landing")}
                for item in catalog_modules
                if isinstance(item, dict)
            ]
            reason_code = None
        elif selector_id == "views":
            source_items = [
                {
                    "id": item.get("view_id"),
                    "title": item.get("title"),
                    "module": item.get("module"),
                    "entry_type": item.get("entry_type"),
                }
                for item in self._authorized_views(principal)
            ]
            reason_code = None
        else:
            source_items = []
            reason_code = "CONTEXT_REQUIRED"
        page = source_items[offset : offset + limit]
        next_offset = offset + len(page)
        next_cursor = (
            _encode_cursor(selector_id, query_context_id, next_offset)
            if next_offset < len(source_items)
            else None
        )
        result: dict[str, object] = {
            "schema": "TPAA_GUI_SELECTOR_V1",
            "request_id": request_id,
            "provenance": _provenance(self._core_baseline),
            "selector_id": selector_id,
            "query_context_id": query_context_id,
            "items": page,
            "next_cursor": next_cursor,
            "total_count": len(source_items),
        }
        if reason_code is not None:
            result["reason_code"] = reason_code
        return result


__all__ = ["GuiGatewayError", "GuiGatewayPrincipal", "GuiGatewayService"]
