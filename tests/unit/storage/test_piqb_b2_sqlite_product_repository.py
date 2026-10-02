from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_storage import (
    LocalObjectStore,
    LocalSealedObjectFlow,
    ProductPublicationCoordinator,
    ProductPublicationError,
    ProductPublicationRequest,
    ProductReleaseIdentity,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
    recover_sealed_orphans,
)


def _request(*, token: int = 0) -> ProductPublicationRequest:
    return ProductPublicationRequest(
        operation_id=f"sqlite-op-{token}",
        product_family="P6_FORECAST",
        product_id="91000000-0000-4000-8000-000000000001",
        release=ProductReleaseIdentity(
            release_id="91000000-0000-4000-8000-000000000003",
            scope_type="LONGITUDINAL",
            scope_key="P6:subject:91000000-0000-4000-8000-000000000002",
            session_id=None,
            longitudinal_scope_id=None,
            catalog_version="P1-METRIC-CATALOG-1.0",
            catalog_hash="1" * 64,
            context_binding_hash="2" * 64,
            manifest_hash="3" * 64,
        ),
        sealed_uri=(
            "tpaa-object://products/piqb-b2/"
            "91000000-0000-4000-8000-000000000001.json"
        ),
        payload=b'{"schema":"P6_FORECAST_SQLITE"}',
        media_type="application/json",
        storage_backend="LOCAL_OBJECT_STORE",
        idempotency_key="sqlite-product-publication-1",
        expected_version_token=token,
    )


def test_sqlite_product_publication_survives_repository_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    store = LocalObjectStore(tmp_path / "objects")

    coordinator = ProductPublicationCoordinator(
        object_flow=LocalSealedObjectFlow(store),
        unit_of_work_factory=lambda: SQLiteDesktopUnitOfWork(
            database,
            write=True,
        ),
    )
    result = coordinator.publish(_request())
    assert result.receipt.version_token == 1
    assert result.receipt.reused is False

    with SQLiteDesktopUnitOfWork(database) as uow:
        replay = uow.product_publication.exact_product(
            "P6_FORECAST",
            "91000000-0000-4000-8000-000000000001",
        )
        referenced = uow.product_publication.referenced_object_uris(
            "tpaa-object://products/piqb-b2"
        )
        uow.commit()

    assert replay.release_id == "91000000-0000-4000-8000-000000000003"
    assert replay.object_sha256 == result.sealed_object.artifact_sha256
    assert referenced == (result.sealed_object.logical_uri,)

    report = recover_sealed_orphans(
        store,
        logical_prefix="tpaa-object://products/piqb-b2",
        referenced_uris=referenced,
        dry_run=False,
    )
    assert report.orphaned == ()
    assert report.removed == ()
    assert store.verify(result.sealed_object)


def test_sqlite_product_publication_is_idempotent_and_cas_guarded(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    store = LocalObjectStore(tmp_path / "objects")
    coordinator = ProductPublicationCoordinator(
        object_flow=LocalSealedObjectFlow(store),
        unit_of_work_factory=lambda: SQLiteDesktopUnitOfWork(
            database,
            write=True,
        ),
    )
    first = coordinator.publish(_request())
    reused = coordinator.publish(_request())
    assert first.receipt.version_token == 1
    assert reused.receipt.version_token == 1
    assert reused.receipt.reused is True

    conflicting = ProductPublicationRequest(
        **{
            **_request().__dict__,
            "idempotency_key": "sqlite-product-publication-2",
            "expected_version_token": 0,
        }
    )
    with pytest.raises(ProductPublicationError) as failed:
        coordinator.publish(conflicting)
    assert failed.value.code == "DATABASE_PUBLICATION_FAILED"
    assert failed.value.__cause__ is not None
    assert isinstance(failed.value.__cause__, ProductPublicationError)
    assert failed.value.__cause__.code == "PUBLISH_CAS_CONFLICT"
