from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_world.m3_profile_training import (
    M3ProfileWorldError,
    project_m3_training_profile,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE = (
    ROOT / "tests" / "fixtures" / "m3" / "STRIKE_M3_WORLD_003_NOMINAL_V1.json"
)
STAGES = (
    "MISSION_SETUP",
    "ROUTE_TASK_EXECUTION",
    "TARGET_INFORMATION_AVAILABLE",
    "TARGET_ASSOCIATION",
    "DESIGNATION_TRACK",
    "TRAINING_ATTACK_EVENT",
    "RANGE_SIM_ADJUDICATION",
    "POST_EVENT_TASK_TRANSITION",
    "RECOVERY",
)
WORLDS = ("A", "C", "M", "W")


def test_strike_projection_is_exact_and_replay_stable() -> None:
    first = project_m3_training_profile(FIXTURE, authority_root=AUTHORITY)
    second = project_m3_training_profile(FIXTURE, authority_root=AUTHORITY)
    assert first == second
    assert first.training_type == "STRIKE"
    assert first.episode_type == "STRIKE_MISSION"
    assert first.stage_profile_id == "STRIKE_MISSION_V1"
    assert first.world_capability_code == "STRIKE_CORE"
    assert first.required_world_codes == WORLDS
    assert tuple(stage.stage_type for stage in first.stages) == STAGES
    assert tuple(event.stage_type for event in first.events) == STAGES
    assert tuple(code for code, _ in first.worlds) == WORLDS
    assert all(manifest.world_kind != "ADJUDICATION" for _, manifest in first.worlds)
    range_event = next(
        event for event in first.events if event.stage_type == "RANGE_SIM_ADJUDICATION"
    )
    assert range_event.event_type == "STAGE_ENTRY_MARKER"
    assert range_event.authority_source == "CONTEXT_OFFICIAL_MARKER"
    assert not first.event_persistence_schema_created
    assert not first.shadow_stage_schema_created


def _mutated(tmp_path: Path, mutation: str) -> Path:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if mutation == "stage":
        payload["official_stage_markers"][6]["stage"] = "RECOVERY"
    elif mutation == "world":
        payload["world_sources"] = payload["world_sources"][:-1]
    else:
        raise AssertionError(mutation)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_strike_fails_closed_on_stage_order_drift(tmp_path: Path) -> None:
    with pytest.raises(M3ProfileWorldError) as captured:
        project_m3_training_profile(
            _mutated(tmp_path, "stage"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_PROFILE_STAGE_MARKER_ORDER_INVALID"


def test_strike_fails_closed_on_required_world_gap(tmp_path: Path) -> None:
    with pytest.raises(M3ProfileWorldError) as captured:
        project_m3_training_profile(
            _mutated(tmp_path, "world"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_PROFILE_REQUIRED_WORLD_MISMATCH"
