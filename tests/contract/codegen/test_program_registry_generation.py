from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tpaa_canonical import CanonicalArtifactLoader
from tpaa_codegen import GenerationCoordinator
from tpaa_codegen.generators import BaselineMetadataGenerator, ProgramRegistryGenerator

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATED_MODULE = REPO_ROOT / "src" / "tpaa_generated" / "program_registry.py"


def _canonical_codes() -> tuple[set[str], set[str], set[str]]:
    loader = CanonicalArtifactLoader()
    p = loader.load("CAPABILITY_PHASE_REGISTRY").payload["capability_phases"]
    m = loader.load("DEVELOPMENT_MILESTONE_REGISTRY").payload["milestones"]
    ws = loader.load("ENGINEERING_WORKSTREAM_REGISTRY").payload["workstreams"]
    assert isinstance(p, list) and isinstance(m, list) and isinstance(ws, list)
    return (
        {str(item["p_code"]) for item in p},
        {str(item["code"]) for item in m},
        {str(item["code"]) for item in ws},
    )


def _load_generated_module() -> object:
    spec = importlib.util.spec_from_file_location("_tpaa_generated_program_registry_test", GENERATED_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_program_registry_generation_is_deterministic() -> None:
    loader = CanonicalArtifactLoader()
    coordinator = GenerationCoordinator(loader, [BaselineMetadataGenerator(), ProgramRegistryGenerator()])
    first = {f.relative_path.as_posix(): f.content for f in coordinator.build().files}
    second = {f.relative_path.as_posix(): f.content for f in coordinator.build().files}
    assert first == second


def test_generated_program_registry_has_exact_canonical_identity_parity() -> None:
    canonical_p, canonical_m, canonical_ws = _canonical_codes()
    module = _load_generated_module()
    assert {item.value for item in module.CapabilityPhase} == canonical_p
    assert {item.value for item in module.DevelopmentMilestone} == canonical_m
    assert {item.value for item in module.EngineeringWorkstream} == canonical_ws
    assert {item["p_code"] for item in module.CAPABILITY_PHASES} == canonical_p
    assert {item["code"] for item in module.DEVELOPMENT_MILESTONES} == canonical_m
    assert {item["code"] for item in module.ENGINEERING_WORKSTREAMS} == canonical_ws


def test_program_registry_manifest_has_three_authoritative_sources() -> None:
    loader = CanonicalArtifactLoader()
    summary = GenerationCoordinator(loader, [ProgramRegistryGenerator()]).build()
    result = summary.results[0]
    assert {source.artifact_id for source in result.sources} == {
        "CAPABILITY_PHASE_REGISTRY",
        "DEVELOPMENT_MILESTONE_REGISTRY",
        "ENGINEERING_WORKSTREAM_REGISTRY",
    }
    assert all(len(source.sha256) == 64 for source in result.sources)
