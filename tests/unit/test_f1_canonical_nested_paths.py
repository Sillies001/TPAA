from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_canonical.byte_stability import governed_text_sha256, governed_text_size, write_utf8_lf
from tpaa_canonical.loader import CanonicalArtifactError, CanonicalArtifactLoader


def _candidate_loader(root: Path, filename: str) -> CanonicalArtifactLoader:
    canonical = root / "canonical"
    artifact_path = canonical / filename
    payload = {
        "authority_id": "TASK_METRIC_TEST",
        "authority_version": "1.0.0",
        "core_baseline": "CB-TEST",
    }
    artifact_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    write_utf8_lf(artifact_path, artifact_text)
    artifact_bytes = artifact_path.read_bytes()
    lock = {
        "baseline": {"core": "CB-TEST", "db_schema": "1.0.0"},
        "artifacts": [
            {
                "file": filename,
                "sha256": governed_text_sha256(artifact_bytes),
                "bytes": governed_text_size(artifact_bytes),
            }
        ],
    }
    lock_path = root / "BASELINE_LOCK.json"
    write_utf8_lf(lock_path, json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
    return CanonicalArtifactLoader(
        root,
        expected_core_baseline="CB-TEST",
        trusted_lock_sha256=governed_text_sha256(lock_path.read_bytes()),
        expected_controlled_artifact_count=1,
    )


def test_loader_accepts_controlled_nested_canonical_artifact(tmp_path: Path) -> None:
    loader = _candidate_loader(tmp_path / "CB-TEST", "task-metrics/TASK_METRIC_TEST.json")

    artifact = loader.load("TASK_METRIC_TEST")

    assert artifact.filename == "task-metrics/TASK_METRIC_TEST.json"
    assert artifact.payload["authority_id"] == "TASK_METRIC_TEST"


@pytest.mark.parametrize(
    "filename",
    [
        "../TASK_METRIC_TEST.json",
        "/TASK_METRIC_TEST.json",
        "task-metrics\\\\TASK_METRIC_TEST.json",
        "task-metrics//TASK_METRIC_TEST.json",
        "C:/TASK_METRIC_TEST.json",
    ],
)
def test_loader_rejects_unsafe_nested_lock_paths(tmp_path: Path, filename: str) -> None:
    root = tmp_path / "CB-TEST"
    canonical = root / "canonical"
    canonical.mkdir(parents=True)
    lock = {
        "baseline": {"core": "CB-TEST", "db_schema": "1.0.0"},
        "artifacts": [{"file": filename, "sha256": "0" * 64, "bytes": 0}],
    }
    lock_path = root / "BASELINE_LOCK.json"
    write_utf8_lf(lock_path, json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
    loader = CanonicalArtifactLoader(
        root,
        expected_core_baseline="CB-TEST",
        trusted_lock_sha256=governed_text_sha256(lock_path.read_bytes()),
        expected_controlled_artifact_count=1,
    )

    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load_all()

    assert captured.value.reason == "BASELINE_LOCK_SCHEMA_MISMATCH"


def test_loader_rejects_unlisted_nested_canonical_json(tmp_path: Path) -> None:
    loader = _candidate_loader(tmp_path / "CB-TEST", "task-metrics/TASK_METRIC_TEST.json")
    write_utf8_lf(
        tmp_path / "CB-TEST" / "canonical" / "task-metrics" / "UNLISTED.json",
        "{}\n",
    )

    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load_all()

    assert captured.value.reason == "UNCONTROLLED_CANONICAL_ARTIFACT"
