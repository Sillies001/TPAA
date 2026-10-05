from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools.testing.m1_batch_2_support import (
    build_batch_2_fixture_products,
    seed_sqlite_core_prerequisites,
)
from tpaa_application import M1ApplicationError
from tpaa_application.m1_publication import to_core_publication_bundle
from tpaa_runtime import (
    ProductionRuntime,
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _runtime(database: Path, object_root: Path) -> ProductionRuntime:
    return build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=AUTHORITY,
            object_root=object_root,
            desktop_database_path=database,
        )
    )


def test_prcb_c1_p1_exact_release_reads_survive_runtime_restart(
    tmp_path: Path,
) -> None:
    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
    )
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)

    connection = sqlite3.connect(database)
    try:
        seed_sqlite_core_prerequisites(connection, products)
    finally:
        connection.close()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        receipt = uow.publication.publish(
            to_core_publication_bundle(products.release),
            idempotency_key="prcb-c1-p1-durable",
            expected_version_token=0,
        )
        uow.commit()

    first = _runtime(database, tmp_path / "objects")
    release_before = first.application.m1_release(receipt.release_id)
    metrics_before = first.application.m1_metrics(receipt.release_id)
    observations_before = first.application.m1_observations(receipt.release_id)
    context_before = first.application.m1_context(receipt.release_id)

    assert release_before["release_id"] == receipt.release_id
    assert release_before["durable_authority"] == "DB_1_9_CORE_PUBLICATION_LEDGER"
    assert release_before["production_compute_configured"] is False
    assert len(metrics_before) == 5
    assert len(observations_before) == 5
    assert context_before["context_id"] == products.release.context_id

    restarted = _runtime(database, tmp_path / "objects")
    assert restarted.application.m1_release(receipt.release_id) == release_before
    assert restarted.application.m1_metrics(receipt.release_id) == metrics_before
    assert restarted.application.m1_observations(receipt.release_id) == observations_before
    assert restarted.application.m1_context(receipt.release_id) == context_before


def test_prcb_c1_p1_compute_commands_remain_fail_closed_until_c2(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    runtime = _runtime(database, tmp_path / "objects")

    with pytest.raises(M1ApplicationError) as caught:
        runtime.application.import_m1_session(
            fixture_id="must-not-be-read",
            idempotency_key="prcb-c1-no-fixture-fallback",
        )
    assert caught.value.code == "P1_PRODUCTION_COMMAND_NOT_CONFIGURED"

    states = {
        item["phase"]: item["state"]
        for item in runtime.application.feature_availability()["items"]
    }
    assert states["P1"] == "NOT_CONFIGURED"
