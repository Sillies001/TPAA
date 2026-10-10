"""Governed decimal-string semantics for B2 durable job requests."""

from __future__ import annotations

import pytest

from tpaa_runtime.production_downstream import (
    ProductionDownstreamError,
    _number,
)
from tpaa_storage.hashing import HashInputError, canonical_request_hash


def test_ed2_b2_numeric_requests_preserve_hash_safe_decimal_text() -> None:
    request = {
        "production_input": {
            "factor_values_by_observation": {
                "observation": {"SESSION_CONTEXT_FACTOR": "0.5"}
            },
            "reference_factor_values": {"SESSION_CONTEXT_FACTOR": "0.5"},
        }
    }
    assert len(canonical_request_hash(request)) == 64
    assert _number("0.5", "factor") == 0.5
    assert _number("1.0", "factor") == 1.0
    assert _number(0.5, "factor") == 0.5
    with pytest.raises(HashInputError, match="float is forbidden"):
        canonical_request_hash({"factor": 0.5})


@pytest.mark.parametrize(
    "raw",
    ["", " 0.5", "0.5 ", "NaN", "Infinity", "not-a-number", True, None],
)
def test_ed2_b2_numeric_input_fails_closed_for_invalid_values(raw: object) -> None:
    with pytest.raises(ProductionDownstreamError, match="ED2_B2_INPUT_INVALID"):
        _number(raw, "factor")
