from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ed2_b3_upper_products_are_durable_exact_and_production_wired() -> None:
    contract = _source("src/tpaa_application/ed2_upper_products.py")
    service = _source("src/tpaa_application/ed2_upper_service.py")
    repository = _source("src/tpaa_runtime/ed2_upper_repository.py")
    production = _source("src/tpaa_runtime/production.py")
    api = _source("src/tpaa_api/ed2_upper.py")

    for token in (
        "EVENT_RELATION_ROOT_CAUSE",
        "LONGITUDINAL_HUMAN_TEAM",
        "COURSE_UNIT_ANALYTICS",
        "TRAINING_PLUGIN_COMPOSITION",
        "JOINT_LVC_GATEWAY",
        "MEDIA_DEBRIEF",
    ):
        assert token in contract

    assert '"registry.dataset_snapshot"' in repository
    assert "DurableED2UpperProductRepository" in production
    assert "ED2UpperProductService" in production
    assert "ed2_upper=ed2_upper" in production
    assert '"/api/v1/upper/{kind}/{snapshot_id}"' in api
    assert "snapshot_id: UUID" in api
    assert "current_latest_fallback_used" in service

    for source in (contract, service, repository, production):
        assert "tests/fixtures" not in source
        assert "InMemory" not in source
        assert "mutable latest" not in source.lower()


def test_ed2_b3_training_plugin_and_joint_lvc_are_governed_boundaries() -> None:
    contract = _source("src/tpaa_application/ed2_upper_products.py")
    plugin = _source("src/tpaa_runtime/training_plugin.py")
    gateway = _source("src/tpaa_ingest/ed2_gateway.py")

    expected = (
        "ContextApplicabilityProfile",
        "WorldReconstructionPolicySet",
        "StageObjectiveProjector",
        "TPAAMChainBuilder",
        "EventRelationComplianceDetectors",
        "MetricSet",
        "AssessmentProfile",
    )
    for item in expected:
        assert item in contract
    assert "importlib" not in plugin
    assert "untrusted_dynamic_loading" in plugin
    assert 'session_type="LVC"' in gateway
    assert 'source_or_projection_class="FACT_SOURCE"' in gateway
    assert '"external_protocol_boundary": True' in gateway
    assert '"operational_optimization": False' in gateway


def test_ed2_b3_gui_extends_existing_p05_without_navigation_churn() -> None:
    shell = _source("src/tpaa_gui/product_shell.py")
    linked = _source("src/tpaa_gui/ed2_upper.py")

    assert "tpaaB5TrajectoryRefresh" in shell
    assert "tpaaED2LinkedDebriefSnapshotId" in shell
    assert "tpaaED2LinkedDebriefRefresh" in shell
    assert "tpaaED2LinkedDebriefRender" in shell
    assert "/api/v1/upper/MEDIA_DEBRIEF" in shell
    assert "build_linked_debrief_projection" in shell
    assert "P14" not in shell
    assert "mutable_alias_resolution" in linked
    assert "business_recompute" in linked
    assert '{"W", "P", "A", "J", "M"}' in linked
