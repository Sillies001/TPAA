from __future__ import annotations

from pathlib import Path
from typing import cast

from tpaa_application import build_ed2_upper_product
from tpaa_runtime.durable_repositories import RuntimeUnitOfWorkFactory
from tpaa_runtime.ed2_upper_repository import DurableED2UpperProductRepository
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

_RELEASE = "11111111-1111-4111-8111-111111111111"
_SESSION = "22222222-2222-4222-8222-222222222222"
_JOB = "33333333-3333-4333-8333-333333333333"
_HASH = "a" * 64


def _seed_release(database: Path) -> None:
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        uow.canonical_rows.insert(
            "registry.training_session",
            {
                "session_id": _SESSION,
                "session_code": "ED2-B3-UNIT",
                "session_type": "SIM",
                "start_session_time_us": 0,
                "end_session_time_us": 1,
                "training_type_set": ["BASIC"],
                "data_status": "AVAILABLE",
                "source_count": 1,
                "schema_version": "1.9.0",
            },
            field_kinds={"training_type_set": "text_array"},
        )
        uow.canonical_rows.insert(
            "registry.compute_job",
            {
                "job_id": _JOB,
                "job_type": "ED2_B3_UNIT",
                "session_id": _SESSION,
                "episode_id": None,
                "job_key": "ed2-b3-unit",
                "status": "SUCCEEDED",
                "component_version": "1.0.1",
                "input_hash": _HASH,
                "progress": 1,
                "reason_codes": [],
                "error_detail": None,
            },
            field_kinds={"reason_codes": "text_array"},
        )
        uow.canonical_rows.insert(
            "registry.analysis_release",
            {
                "release_id": _RELEASE,
                "scope_type": "SESSION",
                "scope_key": _SESSION,
                "session_id": _SESSION,
                "longitudinal_scope_id": None,
                "release_no": 1,
                "compute_job_id": _JOB,
                "catalog_version": "CB-1.4.0",
                "catalog_hash": _HASH,
                "context_binding_hash": _HASH,
                "status": "PUBLISHED",
                "parent_release_id": None,
                "manifest_hash": _HASH,
                "created_at": "2030-01-01T04:59:00Z",
                "published_at": "2030-01-01T05:00:00Z",
            },
        )
        uow.commit()


def _product():
    return build_ed2_upper_product(
        kind="MEDIA_DEBRIEF",
        source_release_ids=(_RELEASE,),
        as_of_utc="2030-01-01T05:00:00Z",
        payload={
            "release_id": _RELEASE,
            "mutable_alias_resolution": False,
            "business_recompute": False,
            "cesium_linked": True,
            "view_2d": True,
            "view_3d": True,
            "semantic_layers": ["W", "P", "A", "J", "M"],
            "timeline": [
                {"session_time_us": 1, "layer": "W", "ref": "world:1"},
            ],
            "media": [],
            "bookmarks": [],
            "playlists": [],
        },
    )


def test_ed2_b3_upper_snapshot_is_restart_exact_and_immutable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    _seed_release(database)

    read_factory = cast(
        RuntimeUnitOfWorkFactory,
        lambda: SQLiteDesktopUnitOfWork(database),
    )
    write_factory = cast(
        RuntimeUnitOfWorkFactory,
        lambda: SQLiteDesktopUnitOfWork(database, write=True),
    )

    first = DurableED2UpperProductRepository(read_factory, write_factory)
    product = _product()
    snapshot_id = first.register(product)
    assert first.exact(snapshot_id) == product

    restarted = DurableED2UpperProductRepository(read_factory, write_factory)
    assert restarted.exact(snapshot_id) == product
    assert restarted.list_kind("MEDIA_DEBRIEF") == ((snapshot_id, product),)

    # Idempotent exact registration must reuse the deterministic frozen snapshot.
    assert restarted.register(product) == snapshot_id

    with SQLiteDesktopUnitOfWork(database) as uow:
        row = uow.canonical_rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": snapshot_id},
            columns=(
                "snapshot_type",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        uow.commit()
    assert row is not None
    assert row["snapshot_type"] == "ED2_UPPER_MEDIA_DEBRIEF"
    assert str(row["data_hash"]) == product.logical_content_hash
    assert row["schema_version"] == "TPAA_ED2_UPPER_PRODUCT_V1"
    assert row["frozen"] in (True, 1)
