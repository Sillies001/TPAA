"""DB 1.9 frozen dataset-snapshot adapter for ED-2 B3 upper products."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast
from uuid import UUID, uuid5

from tpaa_application.ed2_upper_products import (
    ED2UpperProduct,
    ED2_UPPER_PRODUCT_SCHEMA,
    build_ed2_upper_product,
    normalize_ed2_upper_kind,
)
from tpaa_application.ed2_upper_service import ED2UpperProductRepositoryPort

from .durable_repositories import RuntimeUnitOfWorkFactory
from tpaa_storage.canonical_rows import CanonicalRowRepository

_NAMESPACE = UUID("ed2b3000-2d87-53e4-9832-4f927c0847be")
_PREFIX = "ED2_UPPER_"


class DurableED2UpperProductRepository(ED2UpperProductRepositoryPort):
    """Immutable B3 product carrier using the adopted generic snapshot relation."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        write_uow_factory: RuntimeUnitOfWorkFactory,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._write_uow_factory = write_uow_factory

    @staticmethod
    def _snapshot_type(kind: str) -> str:
        return _PREFIX + normalize_ed2_upper_kind(kind)

    @staticmethod
    def _snapshot_id(product: ED2UpperProduct) -> str:
        return str(
            uuid5(
                _NAMESPACE,
                f"{product.kind}:{product.logical_content_hash}",
            )
        )

    @staticmethod
    def _decoded_manifest(value: object) -> dict[str, object]:
        decoded: object = value
        if isinstance(value, str):
            decoded = json.loads(value)
        if not isinstance(decoded, Mapping) or not all(
            isinstance(key, str) for key in decoded
        ):
            raise RuntimeError("ED2_UPPER_SNAPSHOT_MANIFEST_INVALID")
        return dict(cast(Mapping[str, object], decoded))

    @staticmethod
    def _decoded_refs(value: object) -> tuple[str, ...]:
        decoded: object = value
        if isinstance(value, str):
            decoded = json.loads(value)
        if not isinstance(decoded, (list, tuple)):
            raise RuntimeError("ED2_UPPER_SNAPSHOT_REFS_INVALID")
        return tuple(str(item) for item in decoded)

    @staticmethod
    def _assert_source_releases(
        rows: CanonicalRowRepository,
        release_ids: tuple[str, ...],
    ) -> None:
        for release_id in release_ids:
            row = rows.one(
                "registry.analysis_release",
                where={"release_id": release_id},
                columns=("status", "published_at"),
            )
            if (
                row is None
                or str(row["status"]) != "PUBLISHED"
                or row["published_at"] is None
            ):
                raise RuntimeError(
                    f"ED2_UPPER_SOURCE_RELEASE_NOT_PUBLISHED:{release_id}"
                )

    @classmethod
    def _from_row(
        cls,
        snapshot_id: str,
        row: Mapping[str, object],
    ) -> ED2UpperProduct:
        snapshot_type = str(row["snapshot_type"])
        if not snapshot_type.startswith(_PREFIX):
            raise LookupError(f"ED2_UPPER_SNAPSHOT_NOT_FOUND:{snapshot_id}")
        kind = normalize_ed2_upper_kind(snapshot_type.removeprefix(_PREFIX))
        manifest = cls._decoded_manifest(row["query_or_manifest"])
        if manifest.get("schema") != ED2_UPPER_PRODUCT_SCHEMA:
            raise RuntimeError(f"ED2_UPPER_SNAPSHOT_SCHEMA_INVALID:{snapshot_id}")
        raw_releases = manifest.get("source_release_ids")
        if not isinstance(raw_releases, list) or not all(
            isinstance(item, str) for item in raw_releases
        ):
            raise RuntimeError(f"ED2_UPPER_SNAPSHOT_REFS_INVALID:{snapshot_id}")
        as_of = manifest.get("as_of_utc")
        payload = manifest.get("payload")
        if not isinstance(as_of, str) or not isinstance(payload, Mapping):
            raise RuntimeError(f"ED2_UPPER_SNAPSHOT_MANIFEST_INVALID:{snapshot_id}")
        product = build_ed2_upper_product(
            kind=str(manifest.get("kind")),
            source_release_ids=cast(list[str], raw_releases),
            as_of_utc=as_of,
            payload=cast(Mapping[str, object], payload),
        )
        refs = cls._decoded_refs(row["input_refs"])
        expected_id = cls._snapshot_id(product)
        if (
            kind != product.kind
            or tuple(sorted(refs)) != product.source_release_ids
            or str(row["data_hash"]) != product.logical_content_hash
            or str(row["schema_version"]) != ED2_UPPER_PRODUCT_SCHEMA
            or row["frozen"] not in (True, 1)
            or expected_id != snapshot_id
        ):
            raise RuntimeError(f"ED2_UPPER_SNAPSHOT_INTEGRITY_FAILED:{snapshot_id}")
        return product

    def register(self, product: ED2UpperProduct) -> str:
        snapshot_id = self._snapshot_id(product)
        snapshot_type = self._snapshot_type(product.kind)
        manifest = product.manifest()
        with self._write_uow_factory() as uow:
            self._assert_source_releases(
                uow.canonical_rows,
                product.source_release_ids,
            )
            current = uow.canonical_rows.one(
                "registry.dataset_snapshot",
                where={"dataset_snapshot_id": snapshot_id},
                columns=(
                    "snapshot_type",
                    "query_or_manifest",
                    "input_refs",
                    "data_hash",
                    "schema_version",
                    "frozen",
                ),
            )
            if current is None:
                uow.canonical_rows.insert(
                    "registry.dataset_snapshot",
                    {
                        "dataset_snapshot_id": snapshot_id,
                        "snapshot_type": snapshot_type,
                        "query_or_manifest": manifest,
                        "input_refs": product.source_release_ids,
                        "data_hash": product.logical_content_hash,
                        "schema_version": ED2_UPPER_PRODUCT_SCHEMA,
                        "frozen": True,
                    },
                    field_kinds={
                        "query_or_manifest": "json",
                        "input_refs": "uuid_array",
                    },
                )
            else:
                self._from_row(snapshot_id, current)
            uow.commit()
        return snapshot_id

    def exact(self, snapshot_id: str) -> ED2UpperProduct:
        try:
            parsed = UUID(snapshot_id)
        except ValueError as exc:
            raise LookupError(f"ED2_UPPER_SNAPSHOT_ID_INVALID:{snapshot_id}") from exc
        if parsed.int == 0 or str(parsed) != snapshot_id:
            raise LookupError(f"ED2_UPPER_SNAPSHOT_ID_INVALID:{snapshot_id}")
        with self._read_uow_factory() as uow:
            row = uow.canonical_rows.one(
                "registry.dataset_snapshot",
                where={"dataset_snapshot_id": snapshot_id},
                columns=(
                    "snapshot_type",
                    "query_or_manifest",
                    "input_refs",
                    "data_hash",
                    "schema_version",
                    "frozen",
                ),
            )
            if row is None:
                raise LookupError(
                    f"ED2_UPPER_SNAPSHOT_NOT_FOUND:{snapshot_id}"
                )
            product = self._from_row(snapshot_id, row)
            self._assert_source_releases(
                uow.canonical_rows,
                product.source_release_ids,
            )
            uow.commit()
        return product

    def list_kind(self, kind: str) -> tuple[tuple[str, ED2UpperProduct], ...]:
        snapshot_type = self._snapshot_type(kind)
        with self._read_uow_factory() as uow:
            rows = uow.canonical_rows.many(
                "registry.dataset_snapshot",
                where={"snapshot_type": snapshot_type},
                columns=(
                    "dataset_snapshot_id",
                    "snapshot_type",
                    "query_or_manifest",
                    "input_refs",
                    "data_hash",
                    "schema_version",
                    "frozen",
                ),
                order_by=("dataset_snapshot_id",),
            )
            products: list[tuple[str, ED2UpperProduct]] = []
            for row in rows:
                snapshot_id = str(row["dataset_snapshot_id"])
                product = self._from_row(snapshot_id, row)
                self._assert_source_releases(
                    uow.canonical_rows,
                    product.source_release_ids,
                )
                products.append((snapshot_id, product))
            uow.commit()
        return tuple(products)
