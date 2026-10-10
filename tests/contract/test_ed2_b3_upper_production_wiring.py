from __future__ import annotations

import json
from pathlib import Path

from tpaa_application import (
    ED2_ROOT_CAUSE_CATEGORIES,
    ED2_TRAINING_PLUGIN_CONTRACTS,
)

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

def test_ed2_b3_frozen_authorities_cover_upper_product_semantics() -> None:
    taxonomy = json.loads(
        (
            ROOT
            / "baseline"
            / "CB-1.4.0"
            / "canonical"
            / "TRAINING_EVALUATION_TAXONOMY.json"
        ).read_text(encoding="utf-8")
    )
    assert frozenset(taxonomy["root_cause_candidate_categories"]) == (
        ED2_ROOT_CAUSE_CATEGORIES
    )
    assert tuple(taxonomy["training_plugin_contract"]) == (
        ED2_TRAINING_PLUGIN_CONTRACTS
    )

    traceability = json.loads(
        (
            ROOT
            / "baseline"
            / "CB-1.4.0"
            / "canonical"
            / "TRACEABILITY_MATRIX.json"
        ).read_text(encoding="utf-8")
    )
    rendered_verification = "\n".join(
        str(item["verification"]) for item in traceability["items"]
    )
    qualification = _source("src/tpaa_qualification/ed2_b3_upper.py")
    for verification_id in (
        "V-SAFE-002",
        "V-COHORT-001",
        "V-PLUGIN-001",
        "V-KNOW-001",
        "V-VIS-001",
    ):
        assert verification_id in rendered_verification
        assert f'"{verification_id}"' in qualification


def test_ed2_conformance_matrix_has_no_silent_production_gap() -> None:
    matrix = json.loads(
        (
            ROOT
            / "docs"
            / "baseline"
            / "ED2-CONFORMANCE"
            / "ED2_DESIGN_CONFORMANCE_MATRIX.json"
        ).read_text(encoding="utf-8")
    )
    requirements = matrix["requirements"]
    by_id = {item["id"]: item for item in requirements}

    for requirement_id in (
        "ED2-P1-001",
        "ED2-P1-002",
        "ED2-SRC-001",
        "ED2-WORLD-001",
        "ED2-P2P6-001",
        "ED2-ASSESS-001",
    ):
        assert by_id[requirement_id]["status"] == "QUALIFIED"
    assert by_id["ED2-UPPER-001"]["status"] == "IMPLEMENTED_CANDIDATE"
    assert all(item["gap"] is None for item in requirements)
    assert (
        "src/tpaa_qualification/ed2_b3_upper.py"
        in by_id["ED2-UPPER-001"]["current_evidence"]
    )
    qualification = matrix["qualification"]
    assert qualification["design_conformance_claimed"] is False
    assert qualification["status"] == "ED2_CONFORMANCE_CANDIDATE"
    assert qualification["failed_acceptance"] == []

