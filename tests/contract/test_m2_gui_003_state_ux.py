from __future__ import annotations

import pytest

from tpaa_gui.m2_workspace import (
    M2FoundationNavigationError,
    build_m2_metric_presentation_state,
)


def test_m2_gui_003_keeps_wrong_sensor_na_insufficient_invalid_and_error_distinct() -> None:
    wrong_sensor = build_m2_metric_presentation_state(
        {
            "metric_code": "P1-SNS-001",
            "applicable": False,
            "system_type": "IRST",
            "applicability_reason_codes": ["WRONG_SENSOR_TYPE"],
            "instances": [],
        }
    )
    na_state = build_m2_metric_presentation_state(
        {
            "metric_code": "P1-SNS-002",
            "applicable": True,
            "instances": [
                {
                    "status": "N_A",
                    "reason_codes": ["NO_ELIGIBLE_OPPORTUNITIES"],
                }
            ],
        }
    )
    insufficient = build_m2_metric_presentation_state(
        {
            "metric_code": "P1-SNS-003",
            "applicable": True,
            "instances": [
                {
                    "status": "INSUFFICIENT_DATA",
                    "reason_codes": ["INSUFFICIENT_REFERENCE_COVERAGE"],
                }
            ],
        }
    )
    invalid = build_m2_metric_presentation_state(
        {
            "metric_code": "P1-SNS-004",
            "applicable": True,
            "instances": [{"status": "INVALID", "reason_codes": []}],
        }
    )
    system_error = build_m2_metric_presentation_state(
        {
            "metric_code": "P1-SNS-005",
            "system_error_code": "M2_METRIC_PLUGIN_FAILED",
        }
    )
    assert {
        wrong_sensor.kind,
        na_state.kind,
        insufficient.kind,
        invalid.kind,
        system_error.kind,
    } == {
        "WRONG_SENSOR_NOT_APPLICABLE",
        "N_A",
        "INSUFFICIENT_DATA",
        "INVALID",
        "SYSTEM_ERROR",
    }
    assert len(
        {
            wrong_sensor.style_sheet,
            na_state.style_sheet,
            insufficient.style_sheet,
            invalid.style_sheet,
            system_error.style_sheet,
        }
    ) == 5


def test_m2_gui_003_na_and_insufficient_require_reason_codes() -> None:
    for status in ("N_A", "INSUFFICIENT_DATA"):
        with pytest.raises(M2FoundationNavigationError) as error:
            build_m2_metric_presentation_state(
                {
                    "metric_code": "P1-SNS-001",
                    "applicable": True,
                    "instances": [{"status": status, "reason_codes": []}],
                }
            )
        assert "M2_GUI_STATE_REASON_CODES_REQUIRED" in str(error.value)


def test_m2_gui_003_not_applicable_cannot_carry_metric_instances() -> None:
    with pytest.raises(M2FoundationNavigationError) as error:
        build_m2_metric_presentation_state(
            {
                "metric_code": "P1-SNS-001",
                "applicable": False,
                "system_type": "IRST",
                "applicability_reason_codes": ["WRONG_SENSOR_TYPE"],
                "instances": [{"status": "N_A", "reason_codes": ["WRONG_SENSOR"]}],
            }
        )
    assert str(error.value).startswith(
        "M2_GUI_STATE_NOT_APPLICABLE_INSTANCES_PRESENT:"
    )


def test_m2_gui_003_system_error_cannot_be_ambiguous_with_metric_state() -> None:
    with pytest.raises(M2FoundationNavigationError) as error:
        build_m2_metric_presentation_state(
            {
                "metric_code": "P1-SNS-005",
                "system_error_code": "M2_METRIC_PLUGIN_FAILED",
                "applicable": True,
                "instances": [{"status": "INVALID", "reason_codes": []}],
            }
        )
    assert str(error.value).startswith("M2_GUI_STATE_SYSTEM_ERROR_AMBIGUOUS:")


def test_m2_gui_003_mixed_instance_states_are_explicit() -> None:
    state = build_m2_metric_presentation_state(
        {
            "metric_code": "P1-SNS-003",
            "applicable": True,
            "instances": [
                {"status": "VALID", "reason_codes": []},
                {"status": "N_A", "reason_codes": ["NO_CONFIRMED_DETECTION"]},
            ],
        }
    )
    assert state.kind == "MIXED_RESULT_STATES"
    assert state.result_statuses == ("N_A", "VALID")
    assert state.reason_codes == ("NO_CONFIRMED_DETECTION",)
