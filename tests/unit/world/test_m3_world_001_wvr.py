from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_world.m3_wvr_training import (
    EXPECTED_STAGE_ORDER,
    EXPECTED_WORLD_CODES,
    M3WVRWorldError,
    project_m3_wvr_world,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE = ROOT / "tests" / "fixtures" / "m3" / "WVR_M3_WORLD_001_NOMINAL_V1.json"


def test_wvr_projection_is_exact_and_replay_stable() -> None:
    first = project_m3_wvr_world(FIXTURE, authority_root=AUTHORITY)
    second = project_m3_wvr_world(FIXTURE, authority_root=AUTHORITY)
    assert first == second
    assert first.stage_profile_id == "WVR_ENGAGEMENT_V1"
    assert first.episode.episode_type == "WVR_ENGAGEMENT"
    assert first.episode.world_capability_code == "WVR_CORE"
    assert first.interval_semantics == "half-open"
    assert tuple(stage.stage_type for stage in first.stages) == EXPECTED_STAGE_ORDER
    assert tuple(stage.stage_order for stage in first.stages) == tuple(
        range(len(EXPECTED_STAGE_ORDER))
    )
    assert all(stage.start_session_time_us < stage.end_session_time_us for stage in first.stages)
    assert all(
        left.end_session_time_us == right.start_session_time_us
        for left, right in zip(first.stages, first.stages[1:], strict=False)
    )
    assert tuple(event.stage_type for event in first.events) == EXPECTED_STAGE_ORDER
    assert all(
        event.stage_id == stage.stage_id
        and event.session_time_us == stage.start_session_time_us
        for event, stage in zip(first.events, first.stages, strict=True)
    )
    assert tuple(code for code, _ in first.worlds) == EXPECTED_WORLD_CODES
    assert tuple(manifest.world_kind for _, manifest in first.worlds) == (
        "ACTION",
        "CONTEXT",
        "MACHINE",
        "TRUTH",
    )
    assert all(manifest.episode_id == first.episode.episode_id for _, manifest in first.worlds)
    assert all(manifest.stage_id is None for _, manifest in first.worlds)
    assert all(manifest.status == "READY" for _, manifest in first.worlds)
    assert not first.shadow_stage_schema_created
    assert not first.event_persistence_schema_created
    assert not first.canonical_authority_mutated
    assert not first.persistence_executed
    assert not first.metric_logic_executed
    assert not first.observation_projection_executed
    assert not first.release_publication_executed


def _write_mutated(tmp_path: Path, mutation: str) -> Path:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if mutation == "stage-order":
        payload["official_stage_markers"][0]["stage"] = "MANEUVER"
    elif mutation == "world-missing":
        payload["world_sources"] = payload["world_sources"][:-1]
    else:
        raise AssertionError(mutation)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_wvr_projection_fails_closed_on_stage_order_drift(tmp_path: Path) -> None:
    with pytest.raises(M3WVRWorldError) as captured:
        project_m3_wvr_world(
            _write_mutated(tmp_path, "stage-order"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_WVR_STAGE_MARKER_ORDER_INVALID"


def test_wvr_projection_fails_closed_when_required_world_is_missing(tmp_path: Path) -> None:
    with pytest.raises(M3WVRWorldError) as captured:
        project_m3_wvr_world(
            _write_mutated(tmp_path, "world-missing"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_WVR_REQUIRED_WORLD_MISSING"
