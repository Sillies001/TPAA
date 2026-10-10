"""Application boundary for immutable ED-2 B3 upper products."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from .ed2_upper_products import (
    ED2UpperProduct,
    build_ed2_upper_product,
    normalize_ed2_upper_kind,
)


class ED2UpperProductRepositoryPort(Protocol):
    def register(self, product: ED2UpperProduct) -> str: ...

    def exact(self, snapshot_id: str) -> ED2UpperProduct: ...

    def list_kind(self, kind: str) -> tuple[tuple[str, ED2UpperProduct], ...]: ...


class ED2UpperProductService:
    """Create/read frozen upper products without mutable aliases."""

    def __init__(self, repository: ED2UpperProductRepositoryPort) -> None:
        self._repository = repository

    @staticmethod
    def _projection(snapshot_id: str, product: ED2UpperProduct) -> dict[str, object]:
        return {
            "schema": "TPAA_ED2_UPPER_PRODUCT_PROJECTION_V1",
            "snapshot_id": snapshot_id,
            "kind": product.kind,
            "source_release_ids": list(product.source_release_ids),
            "as_of_utc": product.as_of_utc,
            "logical_content_hash": product.logical_content_hash,
            "payload": product.payload,
            "frozen": True,
            "mutable_alias_resolution": False,
        }

    def create(
        self,
        *,
        kind: str,
        source_release_ids: Sequence[str],
        as_of_utc: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        product = build_ed2_upper_product(
            kind=kind,
            source_release_ids=source_release_ids,
            as_of_utc=as_of_utc,
            payload=payload,
        )
        snapshot_id = self._repository.register(product)
        return self._projection(snapshot_id, product)

    def exact(
        self,
        *,
        snapshot_id: str,
        expected_kind: str | None = None,
    ) -> dict[str, object]:
        product = self._repository.exact(snapshot_id)
        if expected_kind is not None:
            normalized = normalize_ed2_upper_kind(expected_kind)
            if product.kind != normalized:
                raise LookupError(
                    f"ED2_UPPER_KIND_MISMATCH:{snapshot_id}:{normalized}"
                )
        return self._projection(snapshot_id, product)

    def list_kind(self, kind: str) -> dict[str, object]:
        normalized = normalize_ed2_upper_kind(kind)
        items = [
            {
                "snapshot_id": snapshot_id,
                "kind": product.kind,
                "source_release_ids": list(product.source_release_ids),
                "as_of_utc": product.as_of_utc,
                "logical_content_hash": product.logical_content_hash,
            }
            for snapshot_id, product in self._repository.list_kind(normalized)
        ]
        return {
            "schema": "TPAA_ED2_UPPER_PRODUCT_INDEX_V1",
            "kind": normalized,
            "items": items,
            "current_latest_fallback_used": False,
        }
