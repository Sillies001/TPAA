from __future__ import annotations

from dataclasses import replace

import pytest

from tpaa_canonical import (
    RuntimeBaselineIdentity,
    RuntimeBaselineMismatch,
    RuntimeReadiness,
    evaluate_runtime_baseline_handshake,
    load_trusted_runtime_baseline_identity,
)


def _identity() -> RuntimeBaselineIdentity:
    return RuntimeBaselineIdentity(
        product_build_version="0.0.0+test",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="lock",
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="core-hash",
        p1_metric_catalog_version="1.14.0",
        p1_metric_catalog_sha256="catalog-hash",
        dto_authority_sha256="dto-hash",
    )


def test_exact_runtime_identity_is_ready() -> None:
    identity = _identity()

    result = evaluate_runtime_baseline_handshake(expected=identity, observed=identity)

    assert result.readiness is RuntimeReadiness.READY
    assert result.ready is True
    assert result.mismatches == ()


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"product_build_version": "different"}, RuntimeBaselineMismatch.PRODUCT_BUILD_VERSION),
        ({"core_baseline": "CB-X"}, RuntimeBaselineMismatch.CORE_BASELINE),
        ({"baseline_lock_sha256": "other"}, RuntimeBaselineMismatch.BASELINE_LOCK_SHA256),
        ({"db_schema_version": "9.9.9"}, RuntimeBaselineMismatch.DB_SCHEMA_VERSION),
        ({"core_authority_sha256": "other"}, RuntimeBaselineMismatch.CORE_AUTHORITY),
        (
            {"p1_metric_catalog_version": "9.9.9"},
            RuntimeBaselineMismatch.P1_METRIC_CATALOG_VERSION,
        ),
        (
            {"p1_metric_catalog_sha256": "other"},
            RuntimeBaselineMismatch.P1_METRIC_CATALOG_SHA256,
        ),
        ({"dto_authority_sha256": "other"}, RuntimeBaselineMismatch.DTO_AUTHORITY_SHA256),
    ],
)
def test_core_catalog_schema_build_mismatch_never_enters_ready(
    changes: dict[str, str], reason: RuntimeBaselineMismatch
) -> None:
    expected = _identity()
    observed = replace(expected, **changes)

    result = evaluate_runtime_baseline_handshake(expected=expected, observed=observed)

    assert result.readiness is RuntimeReadiness.NOT_READY
    assert result.ready is False
    assert result.mismatches == (reason,)


def test_multiple_mismatches_are_deterministic_and_fail_closed() -> None:
    expected = _identity()
    observed = replace(
        expected,
        product_build_version="different",
        core_baseline="CB-X",
        db_schema_version="2.0.0",
        core_authority_artifact_id="WRONG",
        core_authority_sha256="wrong",
    )

    result = evaluate_runtime_baseline_handshake(expected=expected, observed=observed)

    assert result.readiness is RuntimeReadiness.NOT_READY
    assert result.mismatches == (
        RuntimeBaselineMismatch.PRODUCT_BUILD_VERSION,
        RuntimeBaselineMismatch.CORE_BASELINE,
        RuntimeBaselineMismatch.DB_SCHEMA_VERSION,
        RuntimeBaselineMismatch.CORE_AUTHORITY,
    )


def test_trusted_identity_is_derived_from_verified_canonical_baseline() -> None:
    identity = load_trusted_runtime_baseline_identity(product_build_version="0.0.0+test")

    assert identity.product_build_version == "0.0.0+test"
    assert identity.core_baseline == "CB-1.4.0"
    assert identity.db_schema_version == "1.6.0"
    assert identity.core_authority_artifact_id == "CORE_LOGICAL_MODEL"
    assert identity.core_authority_sha256 == (
        "cfde6638e6899167267375c899bff2f04a490ce12f32e0005be4e15dda956245"
    )
    assert identity.p1_metric_catalog_version == "1.14.0"
    assert identity.p1_metric_catalog_sha256 == (
        "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d"
    )
    assert identity.dto_authority_sha256 == (
        "be9e83d18427c0a71d80df6ba2a56f7f611a059c749e1e163d9b5c0140b90e1c"
    )



def test_identity_rejects_missing_dimensions_instead_of_allowing_false_ready() -> None:
    with pytest.raises(ValueError, match="core_baseline"):
        replace(_identity(), core_baseline="")

def test_product_build_version_is_explicit_and_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="product_build_version"):
        load_trusted_runtime_baseline_identity(product_build_version="")
