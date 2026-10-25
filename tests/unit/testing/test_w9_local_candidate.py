from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.qualification.w9_local_candidate import (
    PROFILES,
    W9CandidateError,
    build_local_candidate_manifest,
)
from tpaa_qualification import W9_EVIDENCE_CATEGORIES

REVISION = "a" * 40


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, Path]]:
    dist = tmp_path / "dist"
    for index, profile in enumerate(PROFILES):
        extension = ".zip" if profile.startswith("WINDOWS") else ".tar.gz"
        package_name = f"tpaa-1.0.0-{profile}{extension}"
        package = dist / package_name
        content = f"package-{index}".encode()
        _write(package, content)
        summary = {
            "schema": "TPAA_M0_PACKAGE_ARTIFACT_SUMMARY_V1",
            "qualification": "DEVELOPMENT_NOT_M5_QUALIFIED",
            "source_revision": REVISION,
            "platform_profile": profile,
            "package": package_name,
            "package_sha256": hashlib.sha256(content).hexdigest(),
            "package_bytes": len(content),
        }
        _write(
            dist / f"{package_name}.summary.json",
            json.dumps(summary).encode(),
        )
    baseline_lock = tmp_path / "BASELINE.lock.json"
    dependency_lock = tmp_path / "uv.lock"
    _write(baseline_lock, b"baseline")
    _write(dependency_lock, b"dependencies")
    evidence = {}
    for index, category in enumerate(W9_EVIDENCE_CATEGORIES):
        path = tmp_path / "evidence" / f"{index}.json"
        _write(path, category.encode())
        evidence[category] = path
    return dist, baseline_lock, dependency_lock, evidence


def test_w9_local_manifest_binds_four_packages_and_all_categories(tmp_path: Path) -> None:
    dist, baseline_lock, dependency_lock, evidence = _inputs(tmp_path)
    result = build_local_candidate_manifest(
        dist=dist,
        expected_revision=REVISION,
        baseline_lock=baseline_lock,
        dependency_lock=dependency_lock,
        evidence_by_category=evidence,
    )

    assert result["decision"] == "NO_GO"
    assert result["all_local_evidence_bound_to_one_candidate"] is True
    assert len(result["packages"]) == 4
    candidate = result["candidate_identity_sha256"]
    assert len(str(candidate)) == 64
    assert all(
        item["candidate_identity_sha256"] == candidate
        for item in result["evidence_bindings"]
    )


def test_w9_local_manifest_fails_on_package_hash_or_revision_drift(
    tmp_path: Path,
) -> None:
    dist, baseline_lock, dependency_lock, evidence = _inputs(tmp_path)
    windows = dist / "tpaa-1.0.0-WINDOWS_DESKTOP_X64.zip"
    windows.write_bytes(b"tampered")

    with pytest.raises(W9CandidateError, match="W9_PACKAGE_HASH_MISMATCH"):
        build_local_candidate_manifest(
            dist=dist,
            expected_revision=REVISION,
            baseline_lock=baseline_lock,
            dependency_lock=dependency_lock,
            evidence_by_category=evidence,
        )


def test_w9_local_manifest_requires_exact_ordered_category_set(tmp_path: Path) -> None:
    dist, baseline_lock, dependency_lock, evidence = _inputs(tmp_path)
    reordered = dict(reversed(tuple(evidence.items())))

    with pytest.raises(W9CandidateError, match="CATEGORY_SET_OR_ORDER_INVALID"):
        build_local_candidate_manifest(
            dist=dist,
            expected_revision=REVISION,
            baseline_lock=baseline_lock,
            dependency_lock=dependency_lock,
            evidence_by_category=reordered,
        )
