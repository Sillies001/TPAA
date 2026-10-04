"""Shared deterministic identities for PIQB B2 product publication adapters."""

from __future__ import annotations

from uuid import UUID, uuid5

PRODUCT_OBJECT_NAMESPACE = UUID("3f78c2bf-e754-55c0-8ff3-c758c679c71c")
PRODUCT_BINDING_NAMESPACE = UUID("8ef13a2d-58f6-5637-8d83-7ff7354758b4")
PRODUCT_JOB_NAMESPACE = UUID("5ef42f8c-806a-5f55-8bf4-015069783216")
PRODUCT_PUBLICATION_COMPONENT_VERSION = "PIQB-B2-PRODUCT-PUBLICATION-1.0.0"


def product_object_ref_id(object_uri: str, object_sha256: str) -> str:
    return str(
        uuid5(
            PRODUCT_OBJECT_NAMESPACE,
            f"{object_uri}|{object_sha256}",
        )
    )


def product_binding_id(
    product_family: str,
    product_id: str,
    release_id: str,
    object_ref_id: str,
) -> str:
    return str(
        uuid5(
            PRODUCT_BINDING_NAMESPACE,
            (
                f"{product_family}|{product_id}|"
                f"{release_id}|{object_ref_id}"
            ),
        )
    )


def product_job_id(idempotency_key: str, manifest_hash: str) -> str:
    return str(
        uuid5(
            PRODUCT_JOB_NAMESPACE,
            f"{idempotency_key}|{manifest_hash}",
        )
    )
