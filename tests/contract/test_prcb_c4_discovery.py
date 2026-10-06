from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c4_discovery_is_durable_exact_id_navigation_only() -> None:
    discovery = (
        ROOT / "src" / "tpaa_runtime" / "durable_discovery.py"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "src" / "tpaa_api" / "product_discovery.py"
    ).read_text(encoding="utf-8")
    production = (
        ROOT / "src" / "tpaa_runtime" / "production.py"
    ).read_text(encoding="utf-8")
    local = (
        ROOT / "src" / "tpaa_gui" / "local_backend.py"
    ).read_text(encoding="utf-8")

    assert "registry.training_session" in discovery
    assert "registry.analysis_release" in discovery
    assert "M4_RELEASE" in discovery
    assert "P2_ESTIMATE" in discovery
    assert "P3_TWIN" in discovery
    assert "P4_ASSESSMENT" in discovery
    assert "P5_ASSESSMENT" in discovery
    assert "P6_FORECAST" in discovery
    assert "P6_COUNTERFACTUAL" in discovery
    assert "P6_RECOMMENDATION" in discovery
    assert '"current_latest_fallback_used": False' in discovery
    assert 'row.get("scope_key") != row.get("session_id")' in discovery
    assert "current_release_id" not in api
    assert "/api/v1/discovery/sessions" in api
    assert "/api/v1/discovery/products/{kind}" in api
    assert "DurableProductDiscovery(read_uow_factory)" in production
    assert '"/api/v1/"' in local
    assert "InMemory" not in discovery
    assert "tests/fixtures" not in discovery
