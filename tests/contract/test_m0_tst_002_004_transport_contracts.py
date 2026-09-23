from __future__ import annotations

import json
from decimal import Decimal

from tools.testing.fixture_harness import DEFAULT_BUNDLE, golden_check, load_spec
from tpaa_canonical.loader import ArtifactExpectation, CanonicalArtifactLoader


def test_m0_tst_002_canonical_contracts_cover_core_dto_metric_stage_and_registries() -> None:
    loader = CanonicalArtifactLoader()
    artifacts = {
        artifact_id: loader.load(artifact_id)
        for artifact_id in (
            "CORE_LOGICAL_MODEL",
            "CROSS_LAYER_DTO_CONTRACTS",
            "P1_METRIC_CATALOG",
            "STAGE_REGISTRY",
            "CAPABILITY_PHASE_REGISTRY",
            "ENGINEERING_WORKSTREAM_REGISTRY",
        )
    }

    assert all(len(artifact.sha256) == 64 for artifact in artifacts.values())
    assert artifacts["P1_METRIC_CATALOG"].declared_version == "1.14.0"
    assert artifacts["STAGE_REGISTRY"].declared_version == "1.1.0"

    loader.load(
        "CROSS_LAYER_DTO_CONTRACTS",
        expectation=ArtifactExpectation(required_top_level_keys=("contracts",)),
    )
    loader.load(
        "P1_METRIC_CATALOG",
        expectation=ArtifactExpectation(required_top_level_keys=("metrics",)),
    )
    loader.load(
        "STAGE_REGISTRY",
        expectation=ArtifactExpectation(required_top_level_keys=("profiles",)),
    )


def test_m0_tst_003_typed_value_round_trip_preserves_transport_kinds() -> None:
    product = golden_check(DEFAULT_BUNDLE)
    encoded = json.dumps(product, sort_keys=True)
    decoded = json.loads(encoded)
    values = decoded["values"]

    assert values[0] == {"kind": "NUMERIC", "value": "12.5"}
    assert isinstance(values[0]["value"], str)
    assert values[1] == {"kind": "TEXT", "value": "READY"}
    assert isinstance(values[1]["value"], str)
    assert values[2] == {"kind": "BOOLEAN", "value": True}
    assert isinstance(values[2]["value"], bool)
    assert values[3]["kind"] == "STRUCTURED"
    assert isinstance(values[3]["value"], dict)


def test_m0_tst_004_session_time_remains_decimal_string_beyond_js_safe_integer() -> None:
    spec = load_spec(DEFAULT_BUNDLE)
    payload = json.loads(spec.input_path.read_text(encoding="utf-8"))
    product = golden_check(DEFAULT_BUNDLE)

    source_time = payload["session_time"]
    projected_time = product["session_time"]
    assert isinstance(source_time, str)
    assert isinstance(projected_time, str)
    assert Decimal(source_time) == Decimal("9007199254740993.125")
    assert projected_time == source_time
    assert int(Decimal(source_time)) > 2**53 - 1
