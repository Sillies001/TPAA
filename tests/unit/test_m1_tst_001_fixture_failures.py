from __future__ import annotations

import json
import shutil

import pytest

from tools.testing.m1_fixture_harness import (
    FIXTURE_ROOT,
    M1FixtureError,
    load_spec,
    validate_bundle,
)


def _copy_bundle(tmp_path, fixture_id: str = "BF_M1_FAILURE_V1"):
    source = FIXTURE_ROOT / fixture_id
    target = tmp_path / fixture_id
    shutil.copytree(source, target)
    return target


def _write_json(path, payload) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_corrupt_manifest_fails_closed(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    (bundle / "manifest.json").write_text("{not-json\n", encoding="utf-8")

    with pytest.raises(M1FixtureError) as caught:
        load_spec(bundle)

    assert caught.value.code == "M1_FIXTURE_MANIFEST_CORRUPT"


def test_version_mismatch_fails_closed(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["fixture_version"] = "2.0.0"
    _write_json(path, manifest)

    with pytest.raises(M1FixtureError) as caught:
        load_spec(bundle)

    assert caught.value.code == "M1_FIXTURE_VERSION_UNSUPPORTED"


def test_missing_source_artifact_fails_closed(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    spec = load_spec(bundle)
    spec.source_path.unlink()

    with pytest.raises(M1FixtureError) as caught:
        validate_bundle(bundle)

    assert caught.value.code == "M1_FIXTURE_FILE_MISSING"


def test_changed_source_bytes_fail_hash_validation(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    spec = load_spec(bundle)
    payload = json.loads(spec.source_path.read_text(encoding="utf-8"))
    payload["rows"][0]["p"] = 123.0
    _write_json(spec.source_path, payload)

    with pytest.raises(M1FixtureError) as caught:
        validate_bundle(bundle)

    assert caught.value.code == "M1_FIXTURE_SOURCE_HASH_MISMATCH"


def test_operational_classification_is_rejected(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["data_classification"] = "OPERATIONAL"
    _write_json(path, manifest)

    with pytest.raises(M1FixtureError) as caught:
        load_spec(bundle)

    assert caught.value.code == "M1_FIXTURE_DATA_CLASSIFICATION_FORBIDDEN"


def test_unreviewed_fixture_is_not_accepted_for_m1_tst_001(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["review_state"] = "DRAFT"
    _write_json(path, manifest)

    with pytest.raises(M1FixtureError) as caught:
        load_spec(bundle)

    assert caught.value.code == "M1_FIXTURE_NOT_REVIEWABLE"

def test_input_hash_basis_mismatch_fails_closed(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["input_hash_basis"] = ["source/flight.json"]
    _write_json(path, manifest)

    with pytest.raises(M1FixtureError) as caught:
        load_spec(bundle)

    assert caught.value.code == "M1_FIXTURE_INPUT_HASH_BASIS_MISMATCH"


def test_golden_reviewer_must_match_assigned_role(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["expected_generation"]["reviewer"] = "@not-the-assigned-reviewer"
    _write_json(path, manifest)

    with pytest.raises(M1FixtureError) as caught:
        load_spec(bundle)

    assert caught.value.code == "M1_FIXTURE_GOLDEN_REVIEWER_MISMATCH"

