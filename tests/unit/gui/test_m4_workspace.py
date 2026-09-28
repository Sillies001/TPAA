from __future__ import annotations

import ast
from pathlib import Path

from tpaa_gui import (
    build_annotation_command_payload,
    build_m4_debrief_workspace_model,
    build_m4_trend_workspace_model,
)

ROOT = Path(__file__).resolve().parents[3]


def _trend_payload() -> dict[str, object]:
    release_id = "70000000-0000-4000-8000-000000000001"
    trend_id = "70000000-0000-4000-8000-000000000002"
    return {
        "query": {"release_id": release_id},
        "release": {
            "release_id": release_id,
            "manifest_hash": "a" * 64,
        },
        "scope": {
            "longitudinal_scope_id": (
                "70000000-0000-4000-8000-000000000003"
            ),
            "longitudinal_scope_key": "b" * 64,
        },
        "series": {
            "release_id": release_id,
            "trend_id": trend_id,
            "longitudinal_scope_id": (
                "70000000-0000-4000-8000-000000000003"
            ),
            "subject_type": "AIRCRAFT",
            "subject_id": "70000000-0000-4000-8000-000000000004",
            "metric_code": "P1-AIR-001",
            "metric_semantic_id": "P1-AIR-001",
            "metric_semantic_version": 1,
            "comparison_key_hash": "c" * 64,
            "sample_count_total": 1,
            "current_value": 987.654321,
            "ewma_value": 876.54321,
            "slope": -12.3456,
            "slope_unit": "metric_unit/session_order",
            "stability_mad": 7.89,
            "trend_status": "DECREASING",
            "status": "VALID",
            "reason_codes": [],
            "trend_profile_id": "M4_P1_OBSERVED_TREND_V1",
            "trend_profile_version": "1.0.0",
            "trend_profile_hash": "d" * 64,
            "input_hash": "e" * 64,
        },
        "points": [
            {
                "trend_id": trend_id,
                "point_order": 1,
                "sample_id": "70000000-0000-4000-8000-000000000005",
                "release_id": "70000000-0000-4000-8000-000000000006",
                "session_id": "70000000-0000-4000-8000-000000000007",
                "session_order": 42,
                "value": 987.654321,
                "sample_status": "VALID",
                "configuration_key": "AIRCRAFT_CONFIG_SHA256:" + "f" * 64,
            }
        ],
    }


def test_m4_gui_trend_model_preserves_api_semantics_without_recompute() -> None:
    payload = _trend_payload()
    release_id = str(payload["query"]["release_id"])
    model = build_m4_trend_workspace_model(
        payload,
        expected_release_id=release_id,
    )
    assert model.current_value == 987.654321
    assert model.ewma_value == 876.54321
    assert model.slope == -12.3456
    assert model.stability_mad == 7.89
    assert model.trend_status == "DECREASING"
    assert model.points[0].value == 987.654321
    assert model.points[0].session_order == "42"


def test_m4_gui_debrief_preserves_exact_release_and_revision_identity() -> None:
    release_id = "71000000-0000-4000-8000-000000000001"
    retrospective_id = "71000000-0000-4000-8000-000000000002"
    payload = {
        "query": {
            "base_release_id": release_id,
            "view_mode": "RETROSPECTIVE",
            "retrospective_release_id": retrospective_id,
        },
        "base_release": {
            "release_id": release_id,
            "manifest_hash": "a" * 64,
        },
        "timeline": [
            {
                "base_release_id": release_id,
                "item_id": "evidence:1",
                "item_type": "EVIDENCE",
                "session_id": "71000000-0000-4000-8000-000000000003",
                "evidence_set_id": (
                    "71000000-0000-4000-8000-000000000004"
                ),
                "source_release_id": retrospective_id,
                "knowledge_time_mode": "RETROSPECTIVE",
                "start_session_time_us": "100",
                "end_session_time_us": "200",
            }
        ],
        "annotations": [
            {
                "annotation_id": (
                    "71000000-0000-4000-8000-000000000005"
                ),
                "base_release_id": release_id,
                "author_id": "71000000-0000-4000-8000-000000000006",
                "annotation_type": "EVIDENCE_NOTE",
                "body_text": "note",
                "visibility": "PROJECT",
                "status": "ACTIVE",
                "revision_no": 2,
                "supersedes_annotation_id": (
                    "71000000-0000-4000-8000-000000000007"
                ),
                "evidence_set_id": (
                    "71000000-0000-4000-8000-000000000004"
                ),
                "reason": "correction",
                "audit_id": "2",
                "request_id": "request-2",
                "created_at": "2026-09-28T02:00:00Z",
            }
        ],
    }
    model = build_m4_debrief_workspace_model(
        payload,
        expected_base_release_id=release_id,
    )
    assert model.view_mode == "RETROSPECTIVE"
    assert model.retrospective_release_id == retrospective_id
    assert model.timeline[0].source_release_id == retrospective_id
    assert model.annotations[0].revision_no == 2
    assert model.annotations[0].reason == "correction"


def test_m4_gui_annotation_payload_is_transport_only() -> None:
    payload = build_annotation_command_payload(
        request_id="request-3",
        operation="SUPERSEDE",
        base_release_id="72000000-0000-4000-8000-000000000001",
        target_annotation_id=(
            "72000000-0000-4000-8000-000000000002"
        ),
        session_id="72000000-0000-4000-8000-000000000003",
        author_id="72000000-0000-4000-8000-000000000004",
        annotation_type="COMMENT",
        body_text="revision",
        visibility="PROJECT",
        reason="clarification",
        evidence_set_id=None,
    )
    assert payload["operation"] == "SUPERSEDE"
    assert payload["reason"] == "clarification"
    assert "score" not in payload
    assert "rubric" not in payload


def test_m4_gui_source_has_no_persistence_or_business_engine_imports() -> None:
    source = (
        ROOT / "src" / "tpaa_gui" / "m4_workspace.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    assert not any(
        module.startswith(
            (
                "tpaa_storage",
                "tpaa_application",
                "tpaa_longitudinal",
                "tpaa_metric",
                "tpaa_world",
            )
        )
        for module in modules
    )
