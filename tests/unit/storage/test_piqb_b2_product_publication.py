from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tpaa_storage.object_seal import LocalSealedObjectFlow
from tpaa_storage.object_store import LocalObjectStore
from tpaa_storage.product_publication import (
    ProductPublicationCoordinator,
    ProductPublicationError,
    ProductPublicationReceipt,
    ProductPublicationRegistration,
    ProductPublicationRequest,
    recover_sealed_orphans,
)


class _Ledger:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.values: list[ProductPublicationRegistration] = []

    def register(
        self,
        value: ProductPublicationRegistration,
    ) -> ProductPublicationReceipt:
        if self.fail:
            raise RuntimeError("injected DB failure")
        self.values.append(value)
        return ProductPublicationReceipt(
            product_family=value.product_family,
            product_id=value.product_id,
            scope_key=value.scope_key,
            object_uri=value.object_uri,
            object_sha256=value.object_sha256,
            version_token=value.expected_version_token + 1,
            reused=False,
        )


@dataclass
class _Uow:
    product_publication: _Ledger
    committed: bool = False
    rolled_back: bool = False

    def __enter__(self) -> _Uow:
        return self

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if not self.committed:
            self.rolled_back = True


def _request() -> ProductPublicationRequest:
    return ProductPublicationRequest(
        operation_id="op-1",
        product_family="P6_FORECAST",
        product_id="90000000-0000-4000-8000-000000000001",
        scope_key="subject:90000000-0000-4000-8000-000000000002",
        sealed_uri=(
            "tpaa-object://products/piqb-b2/"
            "90000000-0000-4000-8000-000000000001.json"
        ),
        payload=b'{"schema":"P6_FORECAST_TEST"}',
        idempotency_key="publish-1",
        expected_version_token=0,
    )


def test_product_publication_seals_before_transaction_and_commits(
    tmp_path: Path,
) -> None:
    store = LocalObjectStore(tmp_path)
    flow = LocalSealedObjectFlow(store)
    ledger = _Ledger()
    created: list[_Uow] = []

    def factory() -> _Uow:
        value = _Uow(ledger)
        created.append(value)
        return value

    result = ProductPublicationCoordinator(
        object_flow=flow,
        unit_of_work_factory=factory,
    ).publish(_request())

    assert store.verify(result.sealed_object)
    assert result.receipt.version_token == 1
    assert created[0].committed is True
    assert created[0].rolled_back is False
    assert ledger.values[0].object_uri == result.sealed_object.logical_uri


def test_db_failure_leaves_exact_sealed_orphan_for_recovery(
    tmp_path: Path,
) -> None:
    store = LocalObjectStore(tmp_path)
    flow = LocalSealedObjectFlow(store)
    ledger = _Ledger(fail=True)
    created: list[_Uow] = []

    def factory() -> _Uow:
        value = _Uow(ledger)
        created.append(value)
        return value

    with pytest.raises(ProductPublicationError) as failed:
        ProductPublicationCoordinator(
            object_flow=flow,
            unit_of_work_factory=factory,
        ).publish(_request())

    assert failed.value.code == "DATABASE_PUBLICATION_FAILED"
    orphan = failed.value.sealed_object
    assert orphan is not None
    assert store.verify(orphan)
    assert created[0].rolled_back is True

    dry = recover_sealed_orphans(
        store,
        logical_prefix="tpaa-object://products/piqb-b2",
        referenced_uris=(),
        dry_run=True,
    )
    assert dry.orphaned == (orphan.logical_uri,)
    assert dry.removed == ()
    assert store.verify(orphan)

    removed = recover_sealed_orphans(
        store,
        logical_prefix="tpaa-object://products/piqb-b2",
        referenced_uris=(),
        dry_run=False,
    )
    assert removed.removed == (orphan.logical_uri,)
    assert store.list_objects("tpaa-object://products/piqb-b2") == ()


def test_recovery_never_deletes_registered_object(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    stored = store.put_bytes(
        "tpaa-object://products/piqb-b2/registered.json",
        b"registered",
    )
    report = recover_sealed_orphans(
        store,
        logical_prefix="tpaa-object://products/piqb-b2",
        referenced_uris=(stored.logical_uri,),
        dry_run=False,
    )
    assert report.scanned == 1
    assert report.referenced == 1
    assert report.orphaned == ()
    assert report.removed == ()
    assert store.verify(stored)
