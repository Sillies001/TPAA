from __future__ import annotations

import json
from pathlib import Path

from tpaa_canonical import CanonicalArtifactLoader
from tpaa_codegen import GenerationCoordinator
from tpaa_codegen.generators import BaselineMetadataGenerator

REPO_ROOT = Path(__file__).resolve().parents[3]


def _summary_bytes() -> dict[str, bytes]:
    loader = CanonicalArtifactLoader()
    summary = GenerationCoordinator(loader, [BaselineMetadataGenerator()]).build()
    return {file.relative_path.as_posix(): file.content for file in summary.files}


def test_slice1_generation_is_byte_identical_between_runs() -> None:
    assert _summary_bytes() == _summary_bytes()


def test_baseline_projection_matches_loader_authority() -> None:
    loader = CanonicalArtifactLoader()
    files = _summary_bytes()
    source = files["src/tpaa_generated/baseline.py"].decode()
    assert repr(loader.baseline_metadata["core"]) in source
    assert repr(loader.baseline_metadata["db_schema"]) in source
    assert repr(loader.trusted_lock_sha256) in source


def test_manifest_is_deterministic_and_contains_no_environment_data() -> None:
    files = _summary_bytes()
    manifest_bytes = files["src/tpaa_generated/_generation_manifest.json"]
    manifest = json.loads(manifest_bytes)
    assert manifest["manifest_type"] == "TPAA_CODEGEN_MANIFEST"
    assert manifest["generator_version"] == "0.2.0"
    forbidden = [str(REPO_ROOT), "generated_at", "timestamp", "hostname", "username"]
    text = manifest_bytes.decode()
    for value in forbidden:
        assert value not in text
