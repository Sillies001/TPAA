from __future__ import annotations

from pathlib import Path

from tpaa_runtime.persistence import (
    DesktopPersistenceConfig,
    build_desktop_persistence,
)
from tpaa_storage import (
    ProductPublicationRequest,
    ProductReleaseIdentity,
    bootstrap_sqlite,
)


def _request() -> ProductPublicationRequest:
    return ProductPublicationRequest(
        operation_id="runtime-persistence-op",
        product_family="P1_SESSION_RELEASE",
        product_id="93000000-0000-4000-8000-000000000001",
        release=ProductReleaseIdentity(
            release_id="93000000-0000-4000-8000-000000000002",
            scope_type="SESSION",
            scope_key="93000000-0000-4000-8000-000000000003",
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

    assert runtime.fit_gate.record("P1_SESSION_RELEASE").production_allowed
    published = runtime.publication.publish(_request())
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
