from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from tpaa_gui.m3_workspace import (
    M3_GUI_FAMILY_PRESENTATION,
    M3_GUI_PRODUCT_FAMILY_CODES,
    M3WorkspaceNavigationError,
    build_m3_workspace_navigation_model,
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


def _workspace() -> dict[str, object]:
    release_id = "release-gui-002"
    metrics: list[dict[str, object]] = []
    families: list[dict[str, object]] = []
    for family_code, count in FAMILY_COUNTS.items():
        applicable = family_code != "P1-PSV-*"
        for index in range(1, count + 1):
            metrics.append(
                {
                    "release_id": release_id,
                    "metric_code": f"{family_code[:-1]}{index:03d}",
                    "family_code": family_code,
                    "applicability": {
                        "applicable": applicable,
                        "reason_codes": (
                            [] if applicable else ["NOT_APPLICABLE_SYSTEM_TYPE"]
                        ),
                        "system_type": "RADAR",
                    },
                    "instances": (
                        [{"status": "VALID", "reason_codes": []}]
                        if applicable
                        else []
                    ),
                }
            )
        families.append(
            {
                "family_code": family_code,
                "metric_count": count,
                "applicable_count": count if applicable else 0,
                "not_applicable_count": 0 if applicable else count,
            }
        )
    assert len(metrics) == 116
    return {
        "release_id": release_id,
        "manifest_hash": "a" * 64,
        "training": {
            "training_key": "BASIC",
            "episode_type": "BASIC_FLIGHT",
            "stage_profile_id": "BASIC_FLIGHT_V1",
            "episode_id": "episode-basic",
            "stage_id": "stage-basic",
            "stage_code": "EXECUTION",
        },
        "families": families,
        "metrics": metrics,
        "release_provenance": {"provenance_hash": "b" * 64},
    }


def test_m3_gui_002_product_family_meanings_are_explicit_and_distinct() -> None:
    assert M3_GUI_PRODUCT_FAMILY_CODES == (
        "P1-AIR-*",
        "P1-TRK-*",
        "P1-ID-*",
        "P1-PSV-*",
        "P1-ESM-*",
        "P1-DL-*",
        "P1-FUS-*",
    )
    assert M3_GUI_FAMILY_PRESENTATION == {
        "P1-AIR-*": (
            "Aircraft performance",
            "aircraft observed flight/energy/control/handling/persistence performance",
        ),
        "P1-TRK-*": (
            "Local track product",
            "local track-processing product layer; applicability is by product capability, "
            "not by one physical sensor type",
        ),
        "P1-ID-*": (
            "Association / identification",
            "association/identity processing layer; applicability is by product capability",
        ),
        "P1-PSV-*": (
            "Passive sensor",
            "passive electro-optical/infrared sensing layer",
        ),
        "P1-ESM-*": (
            "RWR / ESM",
            "emitter sensing / warning / ESM layer",
        ),
        "P1-DL-*": (
            "Datalink",
            "datalink transport and remote-track delivery layer",
        ),
        "P1-FUS-*": (
            "Sensor fusion",
            "multi-source fused-track product layer",
        ),
    }
    assert len({value[0] for value in M3_GUI_FAMILY_PRESENTATION.values()}) == 7
    assert len({value[1] for value in M3_GUI_FAMILY_PRESENTATION.values()}) == 7


def test_m3_gui_002_model_preserves_projected_applicability_without_recompute() -> None:
    model = build_m3_workspace_navigation_model(
        _workspace(),
        expected_training_key="BASIC",
        expected_release_id="release-gui-002",
    )
    target = [
        metric
        for metric in model.metric_applicability
        if metric.family_code in M3_GUI_PRODUCT_FAMILY_CODES
    ]
    assert len(target) == 87

    passive = [metric for metric in target if metric.family_code == "P1-PSV-*"]
    assert len(passive) == 7
    assert all(metric.applicable is False for metric in passive)
    assert all(
        metric.reason_codes == ("NOT_APPLICABLE_SYSTEM_TYPE",)
        for metric in passive
    )
    assert all(metric.instance_count == 0 for metric in passive)

    aircraft = [metric for metric in target if metric.family_code == "P1-AIR-*"]
    assert len(aircraft) == 39
    assert all(metric.applicable is True for metric in aircraft)
    assert all(metric.reason_codes == () for metric in aircraft)
    assert all(metric.instance_count == 1 for metric in aircraft)


def test_m3_gui_002_non_applicable_fake_observation_fails_closed() -> None:
    payload = deepcopy(_workspace())
    metrics = payload["metrics"]
    assert isinstance(metrics, list)
    passive = next(
        item
        for item in metrics
        if isinstance(item, dict) and item.get("family_code") == "P1-PSV-*"
    )
    assert isinstance(passive, dict)
    passive["instances"] = [{"status": "VALID", "reason_codes": []}]
    with pytest.raises(
        M3WorkspaceNavigationError,
        match="M3_GUI_NOT_APPLICABLE_INSTANCE_FORBIDDEN",
    ):
        build_m3_workspace_navigation_model(
            payload,
            expected_training_key="BASIC",
            expected_release_id="release-gui-002",
        )


def test_m3_gui_002_source_has_no_applicability_authority_or_metric_engine() -> None:
    source = (ROOT / "src" / "tpaa_gui" / "m3_workspace.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "tpaa_application",
        "tpaa_metric",
        "tpaa_observation",
        "tpaa_storage",
        "CatalogMetricEngine",
        "applicability_mode",
        "allowed_system_types",
        "required_product_semantics",
        "SYSTEM_TYPE_EXACT",
        "SYSTEM_TYPE_SET",
        "PRODUCT_CAPABILITY",
        "sqlite3",
        "psycopg",
    ):
        assert forbidden not in source
