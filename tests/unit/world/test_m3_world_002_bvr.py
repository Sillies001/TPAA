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
FIXTURE = ROOT / "tests" / "fixtures" / "m3" / "BVR_M3_WORLD_002_NOMINAL_V1.json"
STAGES = (
    "DETECTION",
    "TRACK",
    "IDENTIFICATION",
    "DECISION",
    "WEAPON_EMPLOYMENT",
    "ASSESSMENT",
)
WORLDS = ("A", "C", "M", "P", "W")


def test_bvr_projection_is_exact_and_replay_stable() -> None:
    first = project_m3_training_profile(FIXTURE, authority_root=AUTHORITY)
    second = project_m3_training_profile(FIXTURE, authority_root=AUTHORITY)
    assert first == second
    assert first.training_type == "BVR"
    assert first.episode_type == "BVR_KILL_CHAIN"
    assert first.stage_profile_id == "BVR_KILL_CHAIN_V1"
    assert first.world_capability_code == "BVR_PROCESS"
    assert first.required_world_codes == WORLDS
    assert tuple(stage.stage_type for stage in first.stages) == STAGES
    assert tuple(event.stage_type for event in first.events) == STAGES
    assert all(
        left.end_session_time_us == right.start_session_time_us
        for left, right in zip(first.stages, first.stages[1:], strict=False)
    )
    assert tuple(code for code, _ in first.worlds) == WORLDS
    assert not first.shadow_stage_schema_created
    assert not first.event_persistence_schema_created
    assert not first.canonical_authority_mutated


def _mutated(tmp_path: Path, mutation: str) -> Path:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if mutation == "stage":
        payload["official_stage_markers"][1]["stage"] = "DECISION"
    elif mutation == "world":
        payload["world_sources"] = payload["world_sources"][:-1]
    else:
        raise AssertionError(mutation)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_bvr_fails_closed_on_stage_order_drift(tmp_path: Path) -> None:
    with pytest.raises(M3ProfileWorldError) as captured:
        project_m3_training_profile(
            _mutated(tmp_path, "stage"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_PROFILE_STAGE_MARKER_ORDER_INVALID"


def test_bvr_fails_closed_on_required_world_gap(tmp_path: Path) -> None:
    with pytest.raises(M3ProfileWorldError) as captured:
        project_m3_training_profile(
            _mutated(tmp_path, "world"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_PROFILE_REQUIRED_WORLD_MISMATCH"
