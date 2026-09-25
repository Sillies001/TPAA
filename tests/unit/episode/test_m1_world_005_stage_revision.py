from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_episode import StageRevisionError, project_basic_flight_stage_quality, supersede_stage

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "m1" / "BF_M1_NOMINAL_V1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_stage_correction_creates_new_linked_row_without_mutating_history() -> None:
    original = project_basic_flight_stage_quality(
        FIXTURE,
        authority_root=AUTHORITY_ROOT,
    ).stages[1]

    revised = supersede_stage(original, correction_key="review-accepted-boundary-v2")

    assert revised is not original
    assert revised.stage_id != original.stage_id
    assert revised.supersedes_stage_id == original.stage_id
    assert original.supersedes_stage_id is None
    assert revised.episode_id == original.episode_id
    assert revised.start_session_time_us == original.start_session_time_us
    assert revised.end_session_time_us == original.end_session_time_us
    assert supersede_stage(original, correction_key="review-accepted-boundary-v2") == revised


def test_stage_revision_fails_closed_on_invalid_interval() -> None:
    original = project_basic_flight_stage_quality(
        FIXTURE,
        authority_root=AUTHORITY_ROOT,
    ).stages[0]

    with pytest.raises(StageRevisionError) as caught:
        supersede_stage(
            original,
            correction_key="bad",
            start_session_time_us=10,
            end_session_time_us=10,
        )

    assert caught.value.code == "M1_STAGE_REVISION_INTERVAL_INVALID"
