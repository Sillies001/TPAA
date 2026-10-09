"""Exact qualification-only Mission-System rebinding invariants."""

from __future__ import annotations

import pytest

from tools.testing.ed2_p1_full_input_builder import (
    _rebind_system_inputs,
    _remap_system_identity,
)


def test_ed2_b2_system_identity_remaps_nested_refs_only() -> None:
    original = {
        "mission_system_instance_id": "system-a",
        "nested": [
            {"mission_system_instance_id": "system-a"},
            "system-a",
            "prefix-system-a",
        ],
        "system-a": {"reference": "system-a"},
        "other": 3,
    }
    rewritten = _remap_system_identity(original, {"system-a": "system-b"})
    assert rewritten == {
        "mission_system_instance_id": "system-b",
        "nested": [
            {"mission_system_instance_id": "system-b"},
            "system-b",
            "prefix-system-a",
        ],
        "system-b": {"reference": "system-b"},
        "other": 3,
    }
    assert original["mission_system_instance_id"] == "system-a"
    assert _remap_system_identity(original, {}) == original


def test_ed2_b2_system_identity_adds_missing_top_level_binding() -> None:
    inputs: dict[str, dict[str, object]] = {
        "MISSING": {"nested": {"mission_system_instance_id": "system-a"}},
        "PRESENT": {"mission_system_instance_id": "system-a"},
    }
    actual = _rebind_system_inputs(
        inputs,
        {"MISSING": "system-a", "PRESENT": "system-a"},
        {"system-a": "system-b"},
    )
    assert actual["MISSING"]["mission_system_instance_id"] == "system-b"
    assert actual["MISSING"]["nested"] == {
        "mission_system_instance_id": "system-b"
    }
    assert actual["PRESENT"]["mission_system_instance_id"] == "system-b"
    assert "mission_system_instance_id" not in inputs["MISSING"]
    with pytest.raises(ValueError, match="ED2_QUALIFICATION_SYSTEM_INPUT_DRIFT"):
        _rebind_system_inputs(
            {"DRIFT": {"mission_system_instance_id": "unexpected"}},
            {"DRIFT": "system-a"},
            {"system-a": "system-b"},
        )
