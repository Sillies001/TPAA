from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c4_presentation_and_governance_remain_fail_closed() -> None:
    discovery = (
        ROOT / "src" / "tpaa_runtime" / "durable_discovery.py"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "src" / "tpaa_api" / "product_discovery.py"
    ).read_text(encoding="utf-8")
    state = json.loads(
        (
            ROOT
            / "docs"
            / "baseline"
            / "PRCB-1.0"
            / "PRCB_IMPLEMENTATION_STATE.json"
        ).read_text(encoding="utf-8")
    )

    assert "TPAA_RELEASE_PRESENTATION_BINDING_V1" in discovery
    assert "GEODETIC_SERIES_NOT_PRESENT" in discovery
    assert '"business_recompute_performed": False' in discovery
    assert '"current_latest_fallback_used": False' in discovery
    assert "source_forecast_result_ids" in discovery
    assert "source_counterfactual_run_ids" in discovery
    assert "/api/v1/discovery/releases/{release_id}/presentation" in api

    assert state["active_batch"] == "C5"
    assert state["task_state"]["C3"]["state"] == "COMPLETE"
    assert state["task_state"]["C4"]["state"] == "COMPLETE"
    assert state["task_state"]["C5"]["state"] == "ACTIVE"
    assert state["qualification"]["status"] == "NOT_YET_QUALIFIED"
    assert state["qualification"]["formal_release_claimed"] is False
