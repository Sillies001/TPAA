from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_storage.persistence_fit import (
    PersistenceFitError,
    ProductPersistenceFitGate,
)

ROOT = Path(__file__).resolve().parents[2]


def _gate() -> ProductPersistenceFitGate:
    return ProductPersistenceFitGate.from_baseline(
        ROOT
        / "docs"
        / "baseline"
        / "PIQB-1.0"
        / "B2_SCHEMA_PERSISTENCE_FIT.json"
    )


def test_fit_gate_allows_only_reviewed_non_blocked_families() -> None:
    gate = _gate()
    for family in (
        "P1_SESSION_RELEASE",
        "LONGITUDINAL_RELEASE",
        "P3_TWIN_CAPABILITY",
    ):
        assert gate.record(family).production_allowed is True
        gate.assert_production_allowed(family)

    for family in (
        "P2_ATTRIBUTION",
        "P4_P5_ASSESSMENT",
        "P6_MODEL_PROJECTION_ADVISORY",
    ):
        record = gate.record(family)
        assert record.production_allowed is False
        assert record.blockers
        with pytest.raises(PersistenceFitError) as blocked:
            gate.assert_production_allowed(family)
        assert blocked.value.product_family == family
        assert blocked.value.status == "BLOCKED"


def test_unreviewed_product_family_fails_closed() -> None:
    with pytest.raises(PersistenceFitError) as blocked:
        _gate().assert_production_allowed("P7")
    assert blocked.value.status == "UNREVIEWED_PRODUCT_FAMILY"


def test_fit_baseline_forbids_shadow_schema() -> None:
    source = (
        ROOT
        / "docs"
        / "baseline"
        / "PIQB-1.0"
        / "B2_SCHEMA_PERSISTENCE_FIT.json"
    ).read_text(encoding="utf-8")
    assert '"no_shadow_schema": true' in source
    for forbidden in (
        "arbitrary object JSON",
        "audit.audit_log.old_value/new_value",
        "undocumented shadow schema",
        "add tables/columns/migrations",
    ):
        assert forbidden in source
