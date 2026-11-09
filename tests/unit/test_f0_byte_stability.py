from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tpaa_canonical import (
    G12_LOCAL_BASELINE_LOCK_SHA256,
    G12_LOCAL_CONTROLLED_ARTIFACT_COUNT,
    G12_LOCAL_CORE_BASELINE,
    CanonicalArtifactError,
    trusted_loader_for_baseline,
)
from tpaa_canonical.byte_stability import (
    GovernedTextLineEndingError,
    canonicalize_governed_text_bytes,
    governed_text_line_ending,
    governed_text_sha256,
    governed_text_size,
    write_utf8_lf,
)

ROOT = Path(__file__).resolve().parents[2]
G12_BASELINE = ROOT / "baseline" / G12_LOCAL_CORE_BASELINE


def _mixed_line_endings(data: bytes) -> bytes:
    position = data.find(b"\n")
    assert position >= 0
    return data[:position] + b"\r\n" + data[position + 1 :]


def test_lf_and_crlf_have_one_historical_canonical_representation() -> None:
    lf = b'{"alpha": 1}\n{"beta": 2}\n'
    crlf = lf.replace(b"\n", b"\r\n")

    assert canonicalize_governed_text_bytes(lf) == crlf
    assert canonicalize_governed_text_bytes(crlf) == crlf
    assert governed_text_sha256(lf) == governed_text_sha256(crlf)
    assert governed_text_size(lf) == governed_text_size(crlf)
    assert governed_text_line_ending(lf) == "LF"
    assert governed_text_line_ending(crlf) == "CRLF"


def test_mixed_or_bare_line_endings_are_rejected() -> None:
    with pytest.raises(GovernedTextLineEndingError):
        canonicalize_governed_text_bytes(b"first\nsecond\r\n")
    with pytest.raises(GovernedTextLineEndingError):
        canonicalize_governed_text_bytes(b"first\rsecond")


def test_g12_loader_accepts_equivalent_lf_and_crlf_checkouts(tmp_path: Path) -> None:
    lf_loader = trusted_loader_for_baseline(G12_BASELINE)
    lf_artifacts = lf_loader.load_all()
    assert len(lf_artifacts) == G12_LOCAL_CONTROLLED_ARTIFACT_COUNT

    crlf_root = tmp_path / G12_LOCAL_CORE_BASELINE
    shutil.copytree(G12_BASELINE, crlf_root)
    controlled_paths = [
        crlf_root / "BASELINE_LOCK.json",
        *sorted((crlf_root / "canonical").glob("*.json")),
    ]
    for path in controlled_paths:
        path.write_bytes(canonicalize_governed_text_bytes(path.read_bytes()))

    crlf_loader = trusted_loader_for_baseline(crlf_root)
    crlf_artifacts = crlf_loader.load_all()

    assert len(crlf_artifacts) == G12_LOCAL_CONTROLLED_ARTIFACT_COUNT
    assert [
        (artifact.artifact_id, artifact.sha256, artifact.byte_size) for artifact in lf_artifacts
    ] == [
        (artifact.artifact_id, artifact.sha256, artifact.byte_size) for artifact in crlf_artifacts
    ]
    assert crlf_loader.baseline_metadata["core"] == G12_LOCAL_CORE_BASELINE
    assert crlf_loader.trusted_lock_sha256 == G12_LOCAL_BASELINE_LOCK_SHA256


def test_g12_loader_rejects_mixed_line_endings_in_lock(tmp_path: Path) -> None:
    copied = tmp_path / G12_LOCAL_CORE_BASELINE
    shutil.copytree(G12_BASELINE, copied)
    lock_path = copied / "BASELINE_LOCK.json"
    lock_path.write_bytes(_mixed_line_endings(lock_path.read_bytes()))

    with pytest.raises(CanonicalArtifactError) as captured:
        trusted_loader_for_baseline(copied)

    assert captured.value.reason == "BASELINE_LOCK_LINE_ENDINGS_INVALID"


def test_g12_loader_rejects_mixed_line_endings_in_controlled_artifact(tmp_path: Path) -> None:
    copied = tmp_path / G12_LOCAL_CORE_BASELINE
    shutil.copytree(G12_BASELINE, copied)
    artifact_path = copied / "canonical" / "STAGE_REGISTRY.json"
    artifact_path.write_bytes(_mixed_line_endings(artifact_path.read_bytes()))
    loader = trusted_loader_for_baseline(copied)

    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load("STAGE_REGISTRY")

    assert captured.value.reason == "CONTROLLED_ARTIFACT_LINE_ENDINGS_INVALID"


def test_g12_loader_still_rejects_content_drift(tmp_path: Path) -> None:
    copied = tmp_path / G12_LOCAL_CORE_BASELINE
    shutil.copytree(G12_BASELINE, copied)
    artifact_path = copied / "canonical" / "STAGE_REGISTRY.json"
    artifact_path.write_bytes(artifact_path.read_bytes() + b" ")

    loader = trusted_loader_for_baseline(copied)
    with pytest.raises(CanonicalArtifactError) as captured:
        loader.load("STAGE_REGISTRY")

    assert captured.value.reason == "CONTROLLED_ARTIFACT_DRIFT"


def test_g12_artifact_digest_and_size_are_platform_independent() -> None:
    loader = trusted_loader_for_baseline(G12_BASELINE)
    lock = json.loads((G12_BASELINE / "BASELINE_LOCK.json").read_text(encoding="utf-8"))
    entries = {entry["file"]: entry for entry in lock["artifacts"]}

    for artifact in loader.load_all():
        entry = entries[artifact.filename]
        assert artifact.sha256 == entry["sha256"]
        assert artifact.byte_size == entry["bytes"]


def test_lf_writer_is_independent_of_host_newline_translation(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "artifact.json"
    write_utf8_lf(target, "first\r\nsecond\n")

    assert target.read_bytes() == b"first\nsecond\n"
