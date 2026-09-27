from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tpaa_gui.m2_workspace import (
    M2FoundationNavigationError,
    build_m2_foundation_navigation_model,
)
from tpaa_metric import (
    CatalogMetricEngine,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
)
from tpaa_observation import (
    build_m2_publication_routing_plan,
    build_m2_release_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _projection() -> dict[str, object]:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    routing = build_m2_publication_routing_plan(AUTHORITY)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {"metric_code": request.definition.metric_code}

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m2-gui-001-test:{definition.metric_code}:v1",
            plugin=probe,
        )
    batch = CatalogMetricEngine(plan, registry).execute(
        {
            definition.metric_code: {"token": definition.metric_code}
            for definition in plan.definitions
        },
        validate_runtime_contract=False,
    )
    snapshot = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=_hash({"task": "M2-GUI-001"}),
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        context_snapshot={"context": "v1"},
        world_snapshot={"world": "v1"},
        identity_snapshot={"identity": "v1"},
        provenance_snapshot={"provenance": "v1"},
    )
    return snapshot.logical_membership()


def test_m2_gui_001_navigation_model_is_exact_foundation_32() -> None:
    model = build_m2_foundation_navigation_model(_projection())
    assert len(model.items) == 32
    assert len(set(model.metric_codes)) == 32
    assert len(model.by_namespace("QA")) == 8
    assert len(model.by_namespace("AIR")) == 3
    assert len(model.by_namespace("SNS")) == 21
    assert model.item("P1-AIR-001").namespace == "AIR"
    assert model.item("P1-SNS-021").namespace == "SNS"


def test_m2_gui_001_rejects_non_foundation_membership() -> None:
    projection = _projection()
    definitions = projection["definitions"]
    assert isinstance(definitions, list)
    projection["definitions"] = definitions[:-1]
    with pytest.raises(M2FoundationNavigationError) as error:
        build_m2_foundation_navigation_model(projection)
    assert str(error.value) == "M2_GUI_FOUNDATION_MEMBERSHIP_INVALID"


def test_m2_gui_001_module_is_projection_only() -> None:
    source = (ROOT / "src" / "tpaa_gui" / "m2_workspace.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "tpaa_storage",
        "tpaa_metric",
        "tpaa_world",
        "compute_representative_metrics",
        "build_m2_metric_execution_plan",
        "psycopg",
        "sqlite",
    ):
        assert forbidden not in source
