"""Exact qualification-only Mission-System rebinding invariants."""

from __future__ import annotations

from tools.testing.ed2_p1_full_input_builder import _remap_system_identity


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
