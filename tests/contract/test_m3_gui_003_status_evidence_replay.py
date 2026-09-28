from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from tpaa_gui.m3_status import (
    M3_GUI_RESULT_STATUSES,
    M3_GUI_STATUS_STYLES,
    M3StatusPresentationError,
    build_m3_evidence_drilldown,
    build_m3_metric_status_presentations,
)

ROOT = Path(__file__).resolve().parents[2]

FAMILY_COUNTS = {
    "P1-AIR-*": 39,
    "P1-QA-*": 5,
    "P1-SNS-*": 24,
    "P1-TRK-*": 7,
    "P1-ID-*": 12,
    "P1-PSV-*": 7,
    "P1-ESM-*": 6,
    "P1-DL-*": 8,
    "P1-FUS-*": 8,
}
STATUS_SEQUENCE = (
    ("N_A", ["SYNTHETIC_N_A"]),
    ("INSUFFICIENT_DATA", ["SYNTHETIC_DATA_GAP"]),
    ("INVALID", ["SYNTHETIC_INVALID"]),
    ("REVIEW_REQUIRED", ["SYNTHETIC_REVIEW"]),
    ("VALID", []),
)


def _workspace() -> dict[str, object]:
    release_id = "release-gui-003"
    metrics: list[dict[str, object]] = []
    global_index = 0
    for family_code, count in FAMILY_COUNTS.items():
        applicable = family_code != "P1-PSV-*"
        for index in range(1, count + 1):
            if applicable:
                status, reasons = STATUS_SEQUENCE[min(global_index, 4)]
                instances = [{"status": status, "reason_codes": reasons}]
                applicability_reasons: list[str] = []
            else:
                instances = []
                applicability_reasons = ["NOT_APPLICABLE_SYSTEM_TYPE"]
            metrics.append(
                {
                    "release_id": release_id,
                    "metric_code": f"{family_code[:-1]}{index:03d}",
                    "family_code": family_code,
                    "applicability": {
                        "applicable": applicable,
                        "reason_codes": applicability_reasons,
                        "system_type": "RADAR",
                    },
                    "instances": instances,
                }
            )
            global_index += 1
    assert len(metrics) == 116
    return {"release_id": release_id, "metrics": metrics}


def _evidence() -> dict[str, object]:
    return {
        "release_id": "release-gui-003",
        "metric_code": "P1-AIR-001",
        "definition_hash": "a" * 64,
        "execution_record_hash": "b" * 64,
        "evidence_hash": "c" * 64,
        "payload": {
            "applicable": True,
            "instances": [
                {"status": "N_A", "reason_codes": ["SYNTHETIC_N_A"]}
            ],
        },
        "release_provenance": {
            "manifest_hash": "d" * 64,
            "provenance_hash": "e" * 64,
        },
    }


def test_m3_gui_003_result_states_are_distinct_and_release_bound() -> None:
    presentations = build_m3_metric_status_presentations(
        _workspace(),
        expected_release_id="release-gui-003",
    )
    assert len(presentations) == 116
    assert M3_GUI_RESULT_STATUSES == {
        "VALID",
        "N_A",
        "INSUFFICIENT_DATA",
        "INVALID",
        "REVIEW_REQUIRED",
    }
    kinds = {item.kind for item in presentations}
    assert M3_GUI_RESULT_STATUSES <= kinds
    assert "NOT_APPLICABLE" in kinds
    assert all(item.release_id == "release-gui-003" for item in presentations)

    by_code = {item.metric_code: item for item in presentations}
    assert by_code["P1-AIR-001"].kind == "N_A"
    assert by_code["P1-AIR-001"].reason_codes == ("SYNTHETIC_N_A",)
    assert by_code["P1-AIR-002"].kind == "INSUFFICIENT_DATA"
    assert by_code["P1-AIR-003"].kind == "INVALID"
    assert by_code["P1-AIR-004"].kind == "REVIEW_REQUIRED"
    assert by_code["P1-AIR-005"].kind == "VALID"
    assert by_code["P1-PSV-001"].kind == "NOT_APPLICABLE"
    assert by_code["P1-PSV-001"].result_statuses == ()


def test_m3_gui_003_status_styles_keep_system_error_distinct() -> None:
    required = (
        "VALID",
        "N_A",
        "INSUFFICIENT_DATA",
        "INVALID",
        "REVIEW_REQUIRED",
        "NOT_APPLICABLE",
        "SYSTEM_ERROR",
    )
    assert all(key in M3_GUI_STATUS_STYLES for key in required)
    assert len({M3_GUI_STATUS_STYLES[key] for key in required}) == len(required)


def test_m3_gui_003_evidence_drilldown_requires_exact_historical_identity() -> None:
    model = build_m3_evidence_drilldown(
        _evidence(),
        expected_release_id="release-gui-003",
        expected_metric_code="P1-AIR-001",
    )
    assert model.release_id == "release-gui-003"
    assert model.metric_code == "P1-AIR-001"
    assert model.evidence_hash == "c" * 64
    assert model.manifest_hash == "d" * 64
    assert model.provenance_hash == "e" * 64

    drift = deepcopy(_evidence())
    drift["release_id"] = "different-release"
    with pytest.raises(
        M3StatusPresentationError,
        match="M3_GUI_EVIDENCE_RELEASE_MISMATCH",
    ):
        build_m3_evidence_drilldown(
            drift,
            expected_release_id="release-gui-003",
            expected_metric_code="P1-AIR-001",
        )


def test_m3_gui_003_non_applicable_and_invalid_status_fail_closed() -> None:
    fake_observation = deepcopy(_workspace())
    metrics = fake_observation["metrics"]
    assert isinstance(metrics, list)
    passive = next(
        item
        for item in metrics
        if isinstance(item, dict) and item.get("family_code") == "P1-PSV-*"
    )
    assert isinstance(passive, dict)
    passive["instances"] = [{"status": "VALID", "reason_codes": []}]
    with pytest.raises(
        M3StatusPresentationError,
        match="M3_GUI_STATUS_NOT_APPLICABLE_INSTANCES_PRESENT",
    ):
        build_m3_metric_status_presentations(
            fake_observation,
            expected_release_id="release-gui-003",
        )

    invalid_status = deepcopy(_workspace())
    invalid_metrics = invalid_status["metrics"]
    assert isinstance(invalid_metrics, list)
    first = invalid_metrics[0]
    assert isinstance(first, dict)
    first["instances"] = [{"status": "UNKNOWN", "reason_codes": ["UNKNOWN"]}]
    with pytest.raises(
        M3StatusPresentationError,
        match="M3_GUI_STATUS_RESULT_INVALID",
    ):
        build_m3_metric_status_presentations(
            invalid_status,
            expected_release_id="release-gui-003",
        )


def test_m3_gui_003_presentation_source_has_no_recompute_or_latest_fallback() -> None:
    status_source = (ROOT / "src" / "tpaa_gui" / "m3_status.py").read_text(
        encoding="utf-8"
    )
    workspace_source = (ROOT / "src" / "tpaa_gui" / "m3_workspace.py").read_text(
        encoding="utf-8"
    )
    combined = status_source + "\n" + workspace_source
    for forbidden in (
        "tpaa_application",
        "tpaa_metric",
        "tpaa_observation",
        "tpaa_storage",
        "CatalogMetricEngine",
        "build_m3_metric_execution_plan",
        "sqlite3",
        "psycopg",
        '"/latest"',
        '"/current"',
    ):
        assert forbidden not in combined
