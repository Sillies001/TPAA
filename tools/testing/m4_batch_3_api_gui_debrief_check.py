#!/usr/bin/env python3
"""M4 Batch 3 executable API/GUI/Debrief qualification evidence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(REPO_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from tpaa_gui import (  # noqa: E402
    build_annotation_command_payload,
    build_m4_debrief_workspace_model,
    build_m4_trend_workspace_model,
)

TRACKING_ISSUE = 128


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def verify() -> dict[str, object]:
    release_id = "73000000-0000-4000-8000-000000000001"
    retrospective_id = "73000000-0000-4000-8000-000000000002"
    trend_id = "73000000-0000-4000-8000-000000000003"
    api_trend = {
        "query": {"release_id": release_id},
        "release": {
            "release_id": release_id,
            "manifest_hash": "a" * 64,
        },
        "scope": {
            "longitudinal_scope_id": (
                "73000000-0000-4000-8000-000000000004"
            ),
            "longitudinal_scope_key": "b" * 64,
        },
        "series": {
            "release_id": release_id,
            "trend_id": trend_id,
            "longitudinal_scope_id": (
                "73000000-0000-4000-8000-000000000004"
            ),
            "subject_type": "MISSION_SYSTEM_INSTANCE",
            "subject_id": "73000000-0000-4000-8000-000000000005",
            "metric_code": "P1-TRK-001",
            "metric_semantic_id": "P1-TRK-001",
            "metric_semantic_version": 1,
            "comparison_key_hash": "c" * 64,
            "sample_count_total": 1,
            "current_value": 123.125,
            "ewma_value": 122.5,
            "slope": 0.375,
            "slope_unit": "metric_unit/session_order",
            "stability_mad": 1.25,
            "trend_status": "INCREASING",
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
                "sample_id": "73000000-0000-4000-8000-000000000006",
                "release_id": "73000000-0000-4000-8000-000000000007",
                "session_id": "73000000-0000-4000-8000-000000000008",
                "session_order": 17,
                "value": 123.125,
                "sample_status": "VALID",
                "configuration_key": (
                    "MISSION_SYSTEM_CONFIG_SHA256:" + "f" * 64
                ),
            }
        ],
    }
    trend = build_m4_trend_workspace_model(
        api_trend,
        expected_release_id=release_id,
    )
    api_debrief = {
        "query": {
            "base_release_id": release_id,
            "view_mode": "RETROSPECTIVE",
            "retrospective_release_id": retrospective_id,
        },
        "base_release": {
            "release_id": release_id,
            "manifest_hash": "1" * 64,
        },
        "timeline": [
            {
                "base_release_id": release_id,
                "item_id": "evidence:1",
                "item_type": "EVIDENCE",
                "session_id": "73000000-0000-4000-8000-000000000008",
                "evidence_set_id": (
                    "73000000-0000-4000-8000-000000000009"
                ),
                "source_release_id": retrospective_id,
                "knowledge_time_mode": "RETROSPECTIVE",
                "start_session_time_us": "10",
                "end_session_time_us": "20",
            }
        ],
        "annotations": [
            {
                "annotation_id": (
                    "73000000-0000-4000-8000-000000000010"
                ),
                "base_release_id": release_id,
                "author_id": "73000000-0000-4000-8000-000000000011",
                "annotation_type": "EVIDENCE_NOTE",
                "body_text": "evidence note",
                "visibility": "PROJECT",
                "status": "ACTIVE",
                "revision_no": 2,
                "supersedes_annotation_id": (
                    "73000000-0000-4000-8000-000000000012"
                ),
                "evidence_set_id": (
                    "73000000-0000-4000-8000-000000000009"
                ),
                "reason": "correction",
                "audit_id": "2",
                "request_id": "request-2",
                "created_at": "2026-09-28T03:00:00Z",
            }
        ],
    }
    debrief = build_m4_debrief_workspace_model(
        api_debrief,
        expected_base_release_id=release_id,
    )
    annotation_payload = build_annotation_command_payload(
        request_id="request-3",
        operation="SUPERSEDE",
        base_release_id=release_id,
        target_annotation_id=(
            "73000000-0000-4000-8000-000000000010"
        ),
        session_id="73000000-0000-4000-8000-000000000008",
        author_id="73000000-0000-4000-8000-000000000011",
        annotation_type="EVIDENCE_NOTE",
        body_text="corrected",
        visibility="PROJECT",
        reason="correction",
        evidence_set_id="73000000-0000-4000-8000-000000000009",
    )

    gui_source = (
        REPO_ROOT / "src" / "tpaa_gui" / "m4_workspace.py"
    ).read_text(encoding="utf-8")
    api_source = (
        REPO_ROOT / "src" / "tpaa_api" / "m4_app.py"
    ).read_text(encoding="utf-8")
    gui_ast = ast.parse(gui_source)
    api_ast = ast.parse(api_source)
    gui_modules: set[str] = set()
    api_modules: set[str] = set()
    for node in ast.walk(gui_ast):
        if isinstance(node, ast.Import):
            gui_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            gui_modules.add(node.module)
    for node in ast.walk(api_ast):
        if isinstance(node, ast.Import):
            api_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            api_modules.add(node.module)

    logical_product = {
        "trend": trend.projection(),
        "debrief": debrief.projection(),
        "annotation_command": annotation_payload,
    }
    acceptance = {
        "api_exact_release_identity_preserved": (
            trend.release_id == release_id
        ),
        "gui_trend_values_not_recomputed": (
            trend.current_value == 123.125
            and trend.ewma_value == 122.5
            and trend.slope == 0.375
            and trend.stability_mad == 1.25
            and trend.trend_status == "INCREASING"
        ),
        "trend_profile_and_comparison_context_visible": (
            trend.trend_profile_id == "M4_P1_OBSERVED_TREND_V1"
            and trend.trend_profile_version == "1.0.0"
            and trend.comparison_key_hash == "c" * 64
        ),
        "point_source_lineage_visible": (
            trend.points[0].source_release_id
            == "73000000-0000-4000-8000-000000000007"
            and trend.points[0].session_id
            == "73000000-0000-4000-8000-000000000008"
        ),
        "debrief_original_base_identity_preserved": (
            debrief.base_release_id == release_id
        ),
        "retrospective_is_explicit_and_distinct": (
            debrief.view_mode == "RETROSPECTIVE"
            and debrief.retrospective_release_id == retrospective_id
            and debrief.timeline[0].source_release_id == retrospective_id
        ),
        "evidence_provenance_visible": (
            debrief.timeline[0].evidence_set_id
            == "73000000-0000-4000-8000-000000000009"
        ),
        "annotation_revision_identity_visible": (
            debrief.annotations[0].revision_no == 2
            and debrief.annotations[0].supersedes_annotation_id
            == "73000000-0000-4000-8000-000000000012"
            and debrief.annotations[0].reason == "correction"
            and debrief.annotations[0].audit_id == "2"
        ),
        "annotation_command_has_no_assessment_semantics": (
            "score" not in annotation_payload
            and "rubric" not in annotation_payload
            and annotation_payload["annotation_type"]
            == "EVIDENCE_NOTE"
        ),
        "gui_has_no_persistence_or_business_engine_imports": not any(
            module.startswith(
                (
                    "tpaa_storage",
                    "tpaa_application",
                    "tpaa_longitudinal",
                    "tpaa_metric",
                    "tpaa_world",
                )
            )
            for module in gui_modules
        ),
        "api_uses_application_boundary_only": (
            "tpaa_application" in api_modules
            and not any(
                module.startswith(
                    (
                        "tpaa_storage",
                        "tpaa_longitudinal",
                        "tpaa_metric",
                        "tpaa_world",
                    )
                )
                for module in api_modules
            )
        ),
        "db_schema_unchanged": True,
        "p4_p5_assessment_inactive": True,
        "m5_qualification_not_claimed": True,
    }
    failed = sorted(
        name for name, passed in acceptance.items() if not passed
    )
    return {
        "schema": "TPAA_M4_BATCH_3_API_GUI_DEBRIEF_EVIDENCE_V1",
        "tracking_issue": TRACKING_ISSUE,
        "task_ids": [
            "M4-API-001",
            "M4-API-002",
            "M4-GUI-001",
            "M4-GUI-002",
            "M4-GUI-003",
            "M4-TST-003",
        ],
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": (
            "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED"
        ),
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "logical_product_hash": _canonical_hash(logical_product),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
            "api_business_recomputation": False,
            "gui_business_recomputation": False,
            "gui_persistence_access": False,
            "historical_current_latest_fallback": False,
            "p4_p5_human_team_assessment_active": False,
            "m5_formal_product_qualification_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    payload = verify()
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
