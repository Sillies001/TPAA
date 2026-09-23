from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tpaa_canonical import (
    EXPECTED_CONTROLLED_ARTIFACT_COUNT,
    EXPECTED_CORE_BASELINE,
    UNVERSIONED_BY_AUTHORITY,
    ArtifactExpectation,
    CanonicalArtifactError,
    CanonicalArtifactLoader,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_ROOT = REPO_ROOT / "baseline" / EXPECTED_CORE_BASELINE


def test_load_all_exact_controlled_artifacts() -> None:
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    artifacts = loader.load_all()
    assert len(artifacts) == EXPECTED_CONTROLLED_ARTIFACT_COUNT
    assert {artifact.artifact_id for artifact in artifacts} == set(loader.artifact_ids)
    assert all(len(artifact.sha256) == 64 for artifact in artifacts)


def test_loader_exposes_authority_version_without_inventing_missing_version() -> None:
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    stage = loader.load("STAGE_REGISTRY")
    logical_model = loader.load("CORE_LOGICAL_MODEL")
    assert stage.declared_version == "1.1.0"
    assert stage.version_label == "1.1.0"
    assert logical_model.declared_version is None
    assert logical_model.version_label == UNVERSIONED_BY_AUTHORITY
    assert logical_model.schema_version == "1.6.0"


def test_consumer_version_mismatch_fails_closed_with_context() -> None:
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load(
            "STAGE_REGISTRY",
            expectation=ArtifactExpectation(version="0.0.0"),
        )
    error = captured.value
    assert error.reason == "VERSION_MISMATCH"
    assert error.artifact_id == "STAGE_REGISTRY"
    assert error.actual_version == "1.1.0"
    assert "artifact_id=STAGE_REGISTRY" in str(error)
    assert "version_expected=0.0.0" in str(error)
    assert "version_actual=1.1.0" in str(error)


def test_consumer_schema_version_mismatch_fails_closed() -> None:
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load(
            "CORE_LOGICAL_MODEL",
            expectation=ArtifactExpectation(schema_version="9.9.9"),
        )
    assert captured.value.reason == "SCHEMA_VERSION_MISMATCH"
    assert captured.value.actual_schema_version == "1.6.0"


def test_required_top_level_schema_shape_mismatch_fails_closed() -> None:
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load(
            "STAGE_REGISTRY",
            expectation=ArtifactExpectation(required_top_level_keys=("missing_key",)),
        )
    assert captured.value.reason == "SCHEMA_MISMATCH"


def test_unversioned_authority_rejects_consumer_version_requirement() -> None:
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load(
            "CORE_LOGICAL_MODEL",
            expectation=ArtifactExpectation(version="1.0.0"),
        )
    assert captured.value.reason == "VERSION_UNDECLARED"
    assert "UNVERSIONED_BY_AUTHORITY" in str(captured.value)


def test_baseline_lock_drift_fails_before_lock_contents_are_trusted(tmp_path: Path) -> None:
    copied = tmp_path / EXPECTED_CORE_BASELINE
    shutil.copytree(BASELINE_ROOT, copied)
    lock_path = copied / "BASELINE_LOCK.json"
    lock_path.write_bytes(lock_path.read_bytes() + b"\n")

    with pytest.raises(CanonicalArtifactError) as captured:
        CanonicalArtifactLoader(copied)
    error = captured.value
    assert error.reason == "BASELINE_LOCK_HASH_MISMATCH"
    assert error.artifact_id == "BASELINE_LOCK"
    assert "version_actual=UNTRUSTED_NOT_PARSED" in str(error)


def test_byte_or_hash_drift_fails_before_json_is_trusted(tmp_path: Path) -> None:
    copied = tmp_path / EXPECTED_CORE_BASELINE
    shutil.copytree(BASELINE_ROOT, copied)
    stage_path = copied / "canonical" / "STAGE_REGISTRY.json"
    stage_path.write_bytes(stage_path.read_bytes() + b"\n")

    loader = CanonicalArtifactLoader(copied)
    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load("STAGE_REGISTRY")
    error = captured.value
    assert error.reason == "CONTROLLED_ARTIFACT_DRIFT"
    assert error.actual_version == "UNTRUSTED_NOT_PARSED"
    assert "artifact_id=STAGE_REGISTRY" in str(error)
    assert "version_actual=UNTRUSTED_NOT_PARSED" in str(error)


def test_missing_controlled_artifact_fails_closed(tmp_path: Path) -> None:
    copied = tmp_path / EXPECTED_CORE_BASELINE
    shutil.copytree(BASELINE_ROOT, copied)
    (copied / "canonical" / "STAGE_REGISTRY.json").unlink()

    loader = CanonicalArtifactLoader(copied)
    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load("STAGE_REGISTRY")
    assert captured.value.reason == "MISSING_CONTROLLED_ARTIFACT"


def test_unknown_or_unsafe_artifact_id_fails_closed() -> None:
    loader = CanonicalArtifactLoader(BASELINE_ROOT)
    with pytest.raises(CanonicalArtifactError) as unknown:
        loader.load("NOT_CONTROLLED")
    assert unknown.value.reason == "UNKNOWN_ARTIFACT"

    with pytest.raises(CanonicalArtifactError) as unsafe:
        loader.load("../STAGE_REGISTRY")
    assert unsafe.value.reason == "INVALID_ARTIFACT_ID"
