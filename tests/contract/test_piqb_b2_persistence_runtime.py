from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_runtime.persistence import (
    DesktopPersistenceConfig,
    build_desktop_persistence,
)
from tpaa_storage import (
    PersistenceFitError,
    ProductPublicationRequest,
    ProductReleaseIdentity,
    bootstrap_sqlite,
)


def _request() -> ProductPublicationRequest:
    return ProductPublicationRequest(
        operation_id="runtime-persistence-op",
        product_family="LONGITUDINAL_RELEASE",
        product_id="93000000-0000-4000-8000-000000000001",
        release=ProductReleaseIdentity(
            release_id="93000000-0000-4000-8000-000000000002",
            scope_type="LONGITUDINAL",
            scope_key="PIQB-B2-RUNTIME-PERSISTENCE-TEST",
            session_id=None,
            longitudinal_scope_id=None,
            catalog_version="P1-METRIC-CATALOG-1.0",
            catalog_hash="1" * 64,
            context_binding_hash="2" * 64,
            manifest_hash="3" * 64,
        ),
        sealed_uri=(
            "tpaa-object://products/piqb-b2/"
            "93000000-0000-4000-8000-000000000001.json"
        ),
        payload=b'{"schema":"PIQB_B2_RUNTIME_PERSISTENCE"}',
        media_type="application/json",
        storage_backend="LOCAL_OBJECT_STORE",
        idempotency_key="runtime-persistence-1",
        expected_version_token=0,
    )


def test_desktop_persistence_composes_publication_restart_and_recovery(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    runtime = build_desktop_persistence(
        DesktopPersistenceConfig(
            database_path=database,
            object_root=tmp_path / "objects",
        )
    )

    assert runtime.fit_gate.record("LONGITUDINAL_RELEASE").production_allowed
    published = runtime.publish(_request())
    assert runtime.object_store.verify(published.sealed_object)

    recovery = runtime.recover_registered_objects(
        logical_prefix="tpaa-object://products/piqb-b2",
        dry_run=False,
    )
    assert recovery.orphaned == ()
    assert recovery.removed == ()
    assert runtime.object_store.verify(published.sealed_object)


def test_desktop_persistence_staging_recovery_is_explicit(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    runtime = build_desktop_persistence(
        DesktopPersistenceConfig(
            database_path=database,
            object_root=tmp_path / "objects",
        )
    )
    active = runtime.object_store.put_bytes(
        "tpaa-object://staging/active-op/active.bin",
        b"active",
    )
    orphan = runtime.object_store.put_bytes(
        "tpaa-object://staging/dead-op/orphan.bin",
        b"orphan",
    )

    report = runtime.recover_staging(
        scheme="tpaa-object",
        active_operation_ids=("active-op",),
        dry_run=False,
    )
    assert report.removed == (orphan.logical_uri,)
    assert runtime.object_store.verify(active)


def test_desktop_persistence_blocks_unqualified_family_before_object_stage(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    runtime = build_desktop_persistence(
        DesktopPersistenceConfig(
            database_path=database,
            object_root=tmp_path / "objects",
        )
    )
    blocked = ProductPublicationRequest(
        operation_id="blocked-p6-op",
        product_family="P6_MODEL_PROJECTION_ADVISORY",
        product_id="93000000-0000-4000-8000-000000000011",
        release=ProductReleaseIdentity(
            release_id="93000000-0000-4000-8000-000000000012",
            scope_type="LONGITUDINAL",
            scope_key="PIQB-B2-BLOCKED-P6",
            session_id=None,
            longitudinal_scope_id=None,
            catalog_version="P1-METRIC-CATALOG-1.0",
            catalog_hash="1" * 64,
            context_binding_hash="2" * 64,
            manifest_hash="3" * 64,
        ),
        sealed_uri=(
            "tpaa-object://products/piqb-b2/"
            "93000000-0000-4000-8000-000000000011.json"
        ),
        payload=b'{"schema":"MUST_NOT_BE_STAGED"}',
        media_type="application/json",
        storage_backend="LOCAL_OBJECT_STORE",
        idempotency_key="blocked-p6-1",
        expected_version_token=0,
    )

    with pytest.raises(PersistenceFitError) as failed:
        runtime.publish(blocked)
    assert failed.value.product_family == "P6_MODEL_PROJECTION_ADVISORY"
    assert failed.value.status == "BLOCKED"
    assert runtime.object_store.list_objects(
        "tpaa-object://products/piqb-b2"
    ) == ()
