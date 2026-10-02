from __future__ import annotations

import inspect

from tpaa_storage.postgres_product_repository import (
    PostgreSQLProductPublicationLedger,
)
from tpaa_storage.product_identity import (
    PRODUCT_PUBLICATION_COMPONENT_VERSION,
    product_binding_id,
    product_job_id,
    product_object_ref_id,
)
from tpaa_storage.sqlite_product_repository import (
    SQLiteProductPublicationLedger,
)


def test_product_publication_identity_derivation_is_driver_neutral() -> None:
    uri = "tpaa-object://products/piqb-b2/object.json"
    sha = "a" * 64
    product_id = "92000000-0000-4000-8000-000000000001"
    release_id = "92000000-0000-4000-8000-000000000002"
    object_ref_id = product_object_ref_id(uri, sha)

    assert object_ref_id == product_object_ref_id(uri, sha)
    assert product_binding_id(
        "P6_FORECAST",
        product_id,
        release_id,
        object_ref_id,
    ) == product_binding_id(
        "P6_FORECAST",
        product_id,
        release_id,
        object_ref_id,
    )
    assert product_job_id("request-key", "b" * 64) == product_job_id(
        "request-key",
        "b" * 64,
    )
    assert PRODUCT_PUBLICATION_COMPONENT_VERSION == (
        "PIQB-B2-PRODUCT-PUBLICATION-1.0.0"
    )


def test_sqlite_and_postgres_product_ledgers_expose_same_port_members() -> None:
    required = {
        "register",
        "exact_product",
        "referenced_object_uris",
    }
    for adapter in (
        SQLiteProductPublicationLedger,
        PostgreSQLProductPublicationLedger,
    ):
        assert required.issubset(set(adapter.__dict__))


def test_postgres_product_adapter_uses_transaction_lock_and_frozen_tables() -> None:
    source = inspect.getsource(PostgreSQLProductPublicationLedger)
    assert "pg_advisory_xact_lock" in source
    for table in (
        '"registry"."object_reference"',
        '"registry"."object_binding"',
        '"registry"."compute_job"',
        '"registry"."analysis_release"',
        '"registry"."release_scope_pointer"',
    ):
        assert table in source
    assert "CREATE TABLE" not in source
    assert "ALTER TABLE" not in source
