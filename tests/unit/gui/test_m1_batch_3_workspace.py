from __future__ import annotations

from tpaa_gui.m1_workspace import _active_stage_index, _cursor_time


def test_master_cursor_maps_display_position_without_redefining_stage_boundaries() -> None:
    assert _cursor_time(1_000_000, 9_000_000, 0) == 1_000_000
    assert _cursor_time(1_000_000, 9_000_000, 500) == 5_000_000
    assert _cursor_time(1_000_000, 9_000_000, 1000) == 9_000_000


def test_active_stage_uses_release_bound_half_open_intervals() -> None:
    stages = [
        {"start_session_time_us": "1000000", "end_session_time_us": "3000000"},
        {"start_session_time_us": "3000000", "end_session_time_us": "5000000"},
        {"start_session_time_us": "5000000", "end_session_time_us": "7000000"},
        {"start_session_time_us": "7000000", "end_session_time_us": "9000000"},
    ]
    assert _active_stage_index(stages, 1_000_000) == 0
    assert _active_stage_index(stages, 3_000_000) == 1
    assert _active_stage_index(stages, 5_000_000) == 2
    assert _active_stage_index(stages, 9_000_000) == 3
    assert _active_stage_index(stages, 999_999) is None
