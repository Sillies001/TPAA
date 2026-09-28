from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_gui.m3_workspace import (
    M3_GUI_TRAINING_KEYS,
    M3WorkspaceNavigationError,
    build_m3_workspace_navigation_model,
)

ROOT = Path(__file__).resolve().parents[2]

TRAINING = {
    "BASIC": ("BASIC_FLIGHT", "BASIC_FLIGHT_V1", "EXECUTION"),
    "WVR": ("WVR_ENGAGEMENT", "WVR_ENGAGEMENT_V1", "MANEUVER"),
    "BVR": ("BVR_KILL_CHAIN", "BVR_KILL_CHAIN_V1", "TRACK"),
    "STRIKE": ("STRIKE_MISSION", "STRIKE_MISSION_V1", "ROUTE_TASK_EXECUTION"),
}


def _workspace(training_key: str) -> dict[str, object]:
    episode_type, profile_id, stage_code = TRAINING[training_key]
    release_id = f"release-{training_key.lower()}"
    metrics = [
        {
            "release_id": release_id,
            "metric_code": f"P1-TEST-{index:03d}",
        }
        for index in range(1, 117)
    ]
    return {
        "release_id": release_id,
        "manifest_hash": "a" * 64,
        "training": {
            "training_key": training_key,
            "episode_type": episode_type,
            "stage_profile_id": profile_id,
            "episode_id": f"episode-{training_key.lower()}",
            "stage_id": f"stage-{training_key.lower()}",
            "stage_code": stage_code,
        },
        "families": [
            {
                "family_code": "P1-TEST-*",
                "metric_count": 116,
                "applicable_count": 100,
                "not_applicable_count": 16,
            }
        ],
        "metrics": metrics,
        "release_provenance": {
            "provenance_hash": "b" * 64,
        },
    }


def test_m3_gui_001_navigation_model_specializes_all_four_training_types() -> None:
    for training_key in M3_GUI_TRAINING_KEYS:
        payload = _workspace(training_key)
        model = build_m3_workspace_navigation_model(
            payload,
            expected_training_key=training_key,
            expected_release_id=f"release-{training_key.lower()}",
        )
        assert model.training.training_key == training_key
        assert model.training.episode_type == TRAINING[training_key][0]
        assert model.training.stage_profile_id == TRAINING[training_key][1]
        assert model.training.stage_code == TRAINING[training_key][2]
        assert len(model.metric_codes) == 116
        assert sum(family.metric_count for family in model.families) == 116
        assert model.release_id == f"release-{training_key.lower()}"


def test_m3_gui_001_rejects_release_or_training_identity_drift() -> None:
    with pytest.raises(M3WorkspaceNavigationError, match="M3_GUI_RELEASE_ID_MISMATCH"):
        build_m3_workspace_navigation_model(
            _workspace("BASIC"),
            expected_training_key="BASIC",
            expected_release_id="another-release",
        )

    with pytest.raises(
        M3WorkspaceNavigationError,
        match="M3_GUI_TRAINING_KEY_MISMATCH",
    ):
        build_m3_workspace_navigation_model(
            _workspace("WVR"),
            expected_training_key="BASIC",
            expected_release_id="release-wvr",
        )


def test_m3_gui_001_rejects_incomplete_metric_membership() -> None:
    payload = _workspace("STRIKE")
    metrics = payload["metrics"]
    assert isinstance(metrics, list)
    payload["metrics"] = metrics[:-1]
    with pytest.raises(
        M3WorkspaceNavigationError,
        match="M3_GUI_METRIC_MEMBERSHIP_INVALID",
    ):
        build_m3_workspace_navigation_model(
            payload,
            expected_training_key="STRIKE",
            expected_release_id="release-strike",
        )


def test_m3_gui_001_module_is_projection_only() -> None:
    source = (ROOT / "src" / "tpaa_gui" / "m3_workspace.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "tpaa_application",
        "tpaa_api",
        "tpaa_metric",
        "tpaa_observation",
        "tpaa_storage",
        "tpaa_world",
        "CatalogMetricEngine",
        "build_m3_metric_execution_plan",
        "sqlite3",
        "psycopg",
    ):
        assert forbidden not in source
