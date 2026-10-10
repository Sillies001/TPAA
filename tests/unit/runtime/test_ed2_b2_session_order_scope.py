"""DB 1.9 session-order scope types are enforced before P3 persistence."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from tpaa_runtime.production_downstream import (
    ProductionDownstreamError,
    _ensure_session_order_authority,
)

_AIRCRAFT_ID = "8dbfd35f-6310-4e9b-8be6-54a0c9a1d8b8"
_SESSION_ID = "cb1ea1f7-1c12-494b-9501-5b32b92fd662"


def _specification(scope_type: str) -> dict[str, object]:
    return {
        "scope_code": "ED2_B2_CONTINUOUS_P3",
        "scope_type": scope_type,
        "subject_kind": "AIRCRAFT",
        "selector_json": {
            "aircraft_id": _AIRCRAFT_ID,
            "qualification_scope": "ED2_B2_CONTINUOUS",
        },
        "selector_language_version": "1.0.0",
        "scope_revision": 1,
        "description": "qualification",
    }


def test_ed2_b2_aircraft_program_scope_persists_db19_value() -> None:
    rows = Mock()
    rows.one.return_value = None

    scope_id, assignments = _ensure_session_order_authority(
        rows,
        aircraft_id=_AIRCRAFT_ID,
        session_ids=(_SESSION_ID,),
        session_order_by_session={_SESSION_ID: 1},
        specification=_specification("AIRCRAFT_PROGRAM"),
    )

    assert scope_id
    assert assignments[_SESSION_ID][1] == 1
    first_insert = rows.insert.call_args_list[0]
    assert first_insert.args[0] == "registry.session_order_scope"
    assert first_insert.args[1]["scope_type"] == "AIRCRAFT_PROGRAM"


def test_ed2_b2_invalid_scope_type_fails_before_database_write() -> None:
    rows = Mock()

    with pytest.raises(
        ProductionDownstreamError,
        match="ED2_B2_SESSION_ORDER_SCOPE_TYPE_INVALID:AIRCRAFT",
    ):
        _ensure_session_order_authority(
            rows,
            aircraft_id=_AIRCRAFT_ID,
            session_ids=(_SESSION_ID,),
            session_order_by_session={_SESSION_ID: 1},
            specification=_specification("AIRCRAFT"),
        )

    rows.one.assert_not_called()
    rows.insert.assert_not_called()
