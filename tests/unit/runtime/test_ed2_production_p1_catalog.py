from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_runtime.production_p1_catalog import (
    PRODUCTION_P1_CATALOG_METRIC_COUNT,
    PRODUCTION_P1_SUBJECT_COUNTS,
    ProductionP1CatalogError,
    build_production_p1_catalog_contract,
    validate_production_p1_input_membership,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_production_p1_contract_binds_exact_116_catalog() -> None:
    contract = build_production_p1_catalog_contract(AUTHORITY)

    assert len(contract.metric_codes) == PRODUCTION_P1_CATALOG_METRIC_COUNT == 116
    assert len(set(contract.metric_codes)) == 116
    assert dict(contract.subject_counts) == PRODUCTION_P1_SUBJECT_COUNTS
    assert dict(contract.lane_counts) == {
        "AIRCRAFT_CAP_L1_OBSERVATION": 39,
        "QUALITY_EVIDENCE_ONLY": 5,
        "SYSTEM_PERFORMANCE_OBSERVATION": 72,
    }
    assert dict(contract.route_counts) == {
        "CAPABILITY_OBSERVATION": 39,
        "METRIC_INSTANCE_EVIDENCE_ONLY": 5,
        "SYSTEM_PERFORMANCE_OBSERVATION": 72,
    }
    assert len(contract.plugin_identity_manifest) == 116


def test_representative_five_can_never_satisfy_production_p1_membership() -> None:
    contract = build_production_p1_catalog_contract(AUTHORITY)
    representative = {
        code: {}
        for code in (
            "P1-AIR-001",
            "P1-AIR-002",
            "P1-AIR-003",
            "P1-AIR-004",
            "P1-AIR-007",
        )
    }

    with pytest.raises(
        ProductionP1CatalogError,
        match="ED2_P1_INPUT_MEMBERSHIP_INCOMPLETE",
    ):
        validate_production_p1_input_membership(contract, representative)


def test_exact_metric_code_membership_is_accepted_before_business_dispatch() -> None:
    contract = build_production_p1_catalog_contract(AUTHORITY)
    inputs = {code: {} for code in contract.metric_codes}

    validate_production_p1_input_membership(contract, inputs)
