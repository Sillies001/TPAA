from __future__ import annotations

import json

import pytest

from tpaa_ingest import (
    PRODUCTION_FLIGHT_ACTION_PROFILE_ID,
    PRODUCTION_FLIGHT_ACTION_SCHEMA,
    ProductionSourceAdapterError,
    validate_production_flight_document,
)

SESSION_ID = "c2000000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "c2000000-0000-4000-8000-000000000002"
ACTION_ID = "c2000000-0000-4000-8000-000000000011"


def _document() -> dict[str, object]:
    return {
        "schema": "TPAA_PRODUCTION_FLIGHT_SOURCE_V1",
        "schema_version": "1.0.0",
        "session_id": SESSION_ID,
        "aircraft_id": AIRCRAFT_ID,
        "time_transform": {
            "scale": 1.0,
            "offset_us": 0,
        },
        "rows": [
            {
                "source_time_us": 0,
                "p": 0.0,
                "nz": 1.0,
                "heading": 0.0,
                "tas": 100.0,
                "mach": 0.3,
                "quality": 0,
            },
            {
                "source_time_us": 100,
                "p": 0.1,
                "nz": 1.1,
                "heading": 0.1,
                "tas": 101.0,
                "mach": 0.31,
                "quality": 0,
            },
        ],
    }


def _encoded(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_production_flight_action_projection_is_explicit_and_versioned() -> None:
    document = _document()
    document["action_projection"] = {
        "schema": PRODUCTION_FLIGHT_ACTION_SCHEMA,
        "profile_id": PRODUCTION_FLIGHT_ACTION_PROFILE_ID,
        "events": [
            {
                "action_event_id": ACTION_ID,
                "action_type": "FLIGHT_CONTROL_ACTIVITY",
                "start_session_time_us": 0,
                "end_session_time_us": 101,
                "evidence_ref": "test://flight/action",
            }
        ],
    }

    validated = validate_production_flight_document(_encoded(document))
    assert validated["action_projection"] == document["action_projection"]


def test_production_flight_action_projection_is_optional_for_historical_sources() -> None:
    validated = validate_production_flight_document(_encoded(_document()))
    assert "action_projection" not in validated


def test_production_flight_action_projection_fails_closed_on_profile_drift() -> None:
    document = _document()
    document["action_projection"] = {
        "schema": PRODUCTION_FLIGHT_ACTION_SCHEMA,
        "profile_id": "CLIENT_SELECTED_PROFILE",
        "events": [
            {
                "action_event_id": ACTION_ID,
                "action_type": "FLIGHT_CONTROL_ACTIVITY",
                "start_session_time_us": 0,
                "end_session_time_us": 101,
                "evidence_ref": "test://flight/action",
            }
        ],
    }

    with pytest.raises(
        ProductionSourceAdapterError,
        match="ED2_FLIGHT_ACTION_PROJECTION_UNSUPPORTED",
    ):
        validate_production_flight_document(_encoded(document))


def test_production_flight_action_projection_fails_closed_on_overlap() -> None:
    document = _document()
    document["action_projection"] = {
        "schema": PRODUCTION_FLIGHT_ACTION_SCHEMA,
        "profile_id": PRODUCTION_FLIGHT_ACTION_PROFILE_ID,
        "events": [
            {
                "action_event_id": ACTION_ID,
                "action_type": "FLIGHT_CONTROL_ACTIVITY",
                "start_session_time_us": 0,
                "end_session_time_us": 70,
                "evidence_ref": "test://flight/action/1",
            },
            {
                "action_event_id": "c2000000-0000-4000-8000-000000000012",
                "action_type": "FLIGHT_CONTROL_ACTIVITY",
                "start_session_time_us": 60,
                "end_session_time_us": 101,
                "evidence_ref": "test://flight/action/2",
            },
        ],
    }

    with pytest.raises(
        ProductionSourceAdapterError,
        match="ED2_FLIGHT_ACTION_PROJECTION_INVALID",
    ):
        validate_production_flight_document(_encoded(document))
