from __future__ import annotations

from tools.testing.fixture_harness import DEFAULT_BUNDLE, golden_check, load_spec


def test_m0_golden_framework_smoke_uses_frozen_fixture() -> None:
    spec = load_spec(DEFAULT_BUNDLE)
    product = golden_check(DEFAULT_BUNDLE)

    assert spec.fixture_id == "M0_BASIC_TRANSPORT_V1"
    assert spec.fixture_version == "1.0.0"
    assert spec.lifecycle in {"REVIEWED", "APPROVED_GOLDEN"}
    assert product["schema"] == "TPAA_M0_BASIC_LOGICAL_PRODUCT_V1"
    assert product["session_time"] == "9007199254740993.125"

    values = product["values"]
    assert isinstance(values, list)
    assert values == [
        {"kind": "NUMERIC", "value": "12.5"},
        {"kind": "TEXT", "value": "READY"},
        {"kind": "BOOLEAN", "value": True},
        {"kind": "STRUCTURED", "value": {"alpha": 1, "beta": ["x", False, None]}},
    ]
