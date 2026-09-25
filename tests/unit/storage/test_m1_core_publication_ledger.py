from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.testing.m1_batch_2_support import (
    build_batch_2_fixture_products,
    seed_sqlite_core_prerequisites,
)
from tpaa_storage.bootstrap import bootstrap_sqlite
from tpaa_storage.sqlite_repository import SQLiteDesktopUnitOfWork

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_sqlite_core_publication_maps_only_authoritative_tables(tmp_path: Path) -> None:
    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
    )
    database = tmp_path / "m1-batch-2.sqlite3"
    bootstrap_sqlite(database)

    connection = sqlite3.connect(database)
    try:
        seed_sqlite_core_prerequisites(connection, products)
    finally:
        connection.close()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        receipt = uow.publication.publish(
            products.release,
            idempotency_key="sqlite-batch-2",
            expected_version_token=0,
        )
        membership_before = uow.publication.logical_membership(products.release.release_id)
        uow.commit()

    assert receipt.reused is False
    assert receipt.version_token == 1
    assert membership_before["release"]["release_id"] == products.release.release_id
    assert membership_before["release"]["status"] == "PUBLISHED"
    assert len(membership_before["metric_instances"]) == 5
    assert len(membership_before["evidence_sets"]) == 5
    assert len(membership_before["observations"]) == 5

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        retry = uow.publication.publish(
            products.release,
            idempotency_key="sqlite-batch-2",
            expected_version_token=0,
        )
        membership_after = uow.publication.logical_membership(products.release.release_id)
        uow.commit()

    assert retry.reused is True
    assert retry.version_token == 1
    assert membership_after == membership_before
