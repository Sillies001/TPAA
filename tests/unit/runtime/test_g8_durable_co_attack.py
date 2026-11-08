"""G8 durable co-attack adapter data-integrity failure semantics."""

from __future__ import annotations

import pytest

from tpaa_application.co_attack import CoAttackError
from tpaa_runtime.durable_co_attack import _props


def test_valid_relation_properties_are_preserved() -> None:
    assert _props('{"batch_id":"b-1"}') == {"batch_id": "b-1"}


@pytest.mark.parametrize("value", ["{broken", [], 17, None])
def test_malformed_relation_properties_are_degraded_not_silent_empty(value: object) -> None:
    with pytest.raises(CoAttackError) as excinfo:
        _props(value)
    assert excinfo.value.code == "CANONICAL_RELATION_PROPERTIES_INVALID"
    assert excinfo.value.http_status == 503
