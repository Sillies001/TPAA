from __future__ import annotations

import os
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tpaa_gui.product_shell import create_product_workspace
from tpaa_gui.w6_projection import (
    W6ProjectionError,
    attribution_display_rows,
    build_individual_assessment,
    build_team_assessment,
    trend_segments,
    validate_model_profile,
    validate_subject_lane,
)

P4 = "94000000-0000-4000-8000-000000000004"
P5 = "95000000-0000-4000-8000-000000000005"


def _p4() -> dict[str, object]:
    return {
        "layer": "P4_INDIVIDUAL_HUMAN_MACHINE",
        "actor_assessment_id": P4,
        "subject_key": "subject:pilot-1",
        "episode_id": "episode-1",
        "approval_state": "IN_REVIEW",
        "p3_validity_status": "IN_DOMAIN",
        "p3_claim_level": "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
        "p3_as_of_utc": "2026-10-25T00:00:00Z",
        "world_refs": ["world-1"],
        "machine_evidence_ids": ["machine-1"],
        "evidence_set_id": "evidence-1",
        "supersedes_id": None,
        "score": None,
        "grade": None,
    }


def _p5() -> dict[str, object]:
    return {
        "layer": "P5_TEAM_MISSION",
        "mission_assessment_id": P5,
        "composition_id": "composition-1",
        "mission_episode_id": "episode-1",
        "approval_state": "APPROVED",
        "validity_status": "VALID",
        "claim_level": "TEAM_MISSION_EVIDENCE",
        "as_of_utc": "2026-10-25T00:00:00Z",
        "participant_subject_keys": ["subject:pilot-1", "subject:pilot-2"],
        "world_snapshot_refs": ["world-1"],
        "objective_result_refs": ["objective-1"],
        "team_performance_evidence_id": "team-evidence-1",
        "supersedes_id": None,
        "overall_score": None,
        "grade": None,
    }


def test_w6_assessment_lanes_are_exact_and_team_is_not_individual() -> None:
    individual = build_individual_assessment(_p4(), expected_id=P4)
    team = build_team_assessment(_p5(), expected_id=P5)
    assert individual.subject_key == "subject:pilot-1"
    assert individual.participant_subject_keys == ()
    assert team.subject_key == "composition-1"
    assert team.participant_subject_keys == ("subject:pilot-1", "subject:pilot-2")

    leaked = {**_p4(), "overall_score": 0.9}
    with pytest.raises(W6ProjectionError, match="TEAM_TO_INDIVIDUAL"):
        build_individual_assessment(leaked, expected_id=P4)
    with pytest.raises(W6ProjectionError, match="MUTABLE_ALIAS"):
        build_individual_assessment(_p4(), expected_id="latest")


def test_w6_not_identifiable_never_renders_deterministic_effect() -> None:
    rows = attribution_display_rows(
        status="NOT_IDENTIFIABLE",
        factor_effects=(),
        reason_codes=("INSUFFICIENT_COHORT",),
    )
    assert rows == (
        {
            "factor": "Not identifiable",
            "association_effect": None,
            "reason": "INSUFFICIENT_COHORT",
        },
    )
    with pytest.raises(W6ProjectionError, match="EFFECT_FORBIDDEN"):
        attribution_display_rows(
            status="NOT_IDENTIFIABLE",
            factor_effects=(("human", 0.4),),
            reason_codes=("INSUFFICIENT_COHORT",),
        )


def test_w6_server_profile_and_configuration_break_contracts() -> None:
    profile = {
        "profile_id": "profile-1",
        "aircraft_model_id": "model-1",
        "configuration_key": "block-1/config-a",
        "profile_version": "1",
        "as_of_utc": "2026-10-25T00:00:00Z",
        "aircraft_count": 5,
        "independent_episode_count": 12,
        "frontend_aggregate": False,
    }
    validate_model_profile(profile, expected_id="profile-1")
    with pytest.raises(W6ProjectionError, match="FRONTEND_PROFILE"):
        validate_model_profile({**profile, "frontend_aggregate": True}, expected_id="profile-1")

    segments = trend_segments(
        (
            {"session_order": "1", "configuration_key": "config-a"},
            {"session_order": "2", "configuration_key": "config-a"},
            {"session_order": "3", "configuration_key": "config-b"},
        )
    )
    assert [(item.configuration_key, item.reason) for item in segments] == [
        ("config-a", "CONFIG_CHANGE"),
        ("config-b", "SERIES_END"),
    ]
    assert validate_subject_lane("MISSION_SYSTEM_INSTANCE") == "MISSION_SYSTEM_INSTANCE"


def test_w6_shell_maps_p04_p10_to_seven_independent_product_pages() -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["w6-test"])

    def diagnostics() -> Any:
        from tpaa_gui.diagnostics import DiagnosticsSnapshot

        return DiagnosticsSnapshot(
            readiness="READY",
            backend_state="READY",
            mismatches=(),
            failure_code=None,
            expected=None,
            observed=None,
        )

    root = create_product_workspace(
        QtCore,
        QtWidgets,
        None,
        transport=cast(Any, object()),
        diagnostics_provider=diagnostics,
    )
    for slot in range(4, 11):
        page = root._tpaa_pages[slot - 1]
        content = page._tpaa_content
        assert content.objectName() == f"tpaaP{slot:02d}Content"
        assert content.property("tpaaOriginalObjectName") == f"tpaaP{slot:02d}Workflow"
    assert root._tpaa_pages[3]._tpaa_content is not root._tpaa_pages[4]._tpaa_content
    assert root.findChild(QtWidgets.QLabel, "tpaaP08CausalityGuard") is not None
    assert root.findChild(QtWidgets.QLabel, "tpaaP10IsolationGuard") is not None
    root.close()
    app.processEvents()

