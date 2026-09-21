from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tpaa_canonical import CanonicalArtifactLoader

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> object:
    path = REPO_ROOT / "src" / "tpaa_generated" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_tpaa_generated_{name}_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_stage_registry_exact_identity_and_profile_parity() -> None:
    artifact = CanonicalArtifactLoader().load("STAGE_REGISTRY")
    profiles = artifact.payload["profiles"]
    assert isinstance(profiles, dict)
    canonical_stages = {
        stage
        for profile in profiles.values()
        if isinstance(profile, dict)
        for stage in profile["ordered_stages"]
    }
    module = _load("stage_registry")
    assert {item.value for item in module.StageCode} == canonical_stages
    assert {item.value for item in module.StageProfileId} == set(profiles)
    generated_profiles = {item["profile_id"]: item for item in module.STAGE_PROFILES}
    assert set(generated_profiles) == set(profiles)
    for profile_id, canonical in profiles.items():
        assert generated_profiles[profile_id]["ordered_stages"] == tuple(canonical["ordered_stages"])
        assert dict(generated_profiles[profile_id]["semantics"]) == canonical["semantics"]


def test_metric_registry_exact_metric_identity_parity() -> None:
    metrics = CanonicalArtifactLoader().load("P1_METRIC_CATALOG").payload["metrics"]
    assert isinstance(metrics, list)
    canonical_codes = {item["metric_code"] for item in metrics}
    module = _load("metric_registry")
    assert {item.value for item in module.P1MetricCode} == canonical_codes
    assert {item["metric_code"] for item in module.P1_METRICS} == canonical_codes
    assert len(module.P1_METRICS) == 116


def test_dto_types_cover_exact_canonical_contract_names_and_fields() -> None:
    contracts = CanonicalArtifactLoader().load("CROSS_LAYER_DTO_CONTRACTS").payload["contracts"]
    assert isinstance(contracts, dict)
    module = _load("dto")
    for dto_name, contract in contracts.items():
        dto = getattr(module, dto_name)
        fields = contract.get("fields", contract.get("projection_fields"))
        assert isinstance(fields, list)
        assert set(dto.__annotations__) == {field["field"] for field in fields}
