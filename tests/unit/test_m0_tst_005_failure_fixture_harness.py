from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from tools.testing.fixture_harness import DEFAULT_BUNDLE, FixtureError, golden_check, load_spec


def _copy_bundle(tmp_path):
    target = tmp_path / "bundle"
    shutil.copytree(DEFAULT_BUNDLE, target)
    return target


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_missing_input_has_deterministic_failure_code(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    spec = load_spec(bundle)
    spec.input_path.unlink()

    with pytest.raises(FixtureError) as caught:
        golden_check(bundle)

    assert caught.value.code == "FIXTURE_INPUT_MISSING"


def test_corrupt_input_has_deterministic_failure_code(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    spec = load_spec(bundle)
    spec.input_path.write_text("{\"corrupt\":true}\n", encoding="utf-8")

    with pytest.raises(FixtureError) as caught:
        golden_check(bundle)

    assert caught.value.code == "FIXTURE_INPUT_HASH_MISMATCH"


def test_version_mismatch_has_deterministic_failure_code(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fixture_version"] = "2.0.0"
    _write_json(manifest_path, manifest)

    with pytest.raises(FixtureError) as caught:
        load_spec(bundle)

    assert caught.value.code == "FIXTURE_VERSION_UNSUPPORTED"


def test_insufficient_payload_has_deterministic_failure_code(tmp_path) -> None:
    bundle = _copy_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    input_path = bundle / manifest["input"]["path"]
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload["values"] = []
    _write_json(input_path, payload)
    manifest["input"]["sha256"] = hashlib.sha256(input_path.read_bytes()).hexdigest()
    manifest["replay"]["frozen_input_sha256"] = manifest["input"]["sha256"]
    _write_json(manifest_path, manifest)

    with pytest.raises(FixtureError) as caught:
        golden_check(bundle)

    assert caught.value.code == "BASIC_OBJECT_INSUFFICIENT"
