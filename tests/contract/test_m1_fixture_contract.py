from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tools.testing.m1_fixture_contract import (
    EXPECTED_IDS,
    M1FixtureError,
    validate_all,
    validate_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"


def test_m1_fixture_contract_validates_exact_eight_bundles() -> None:
    evidence = validate_all()
    assert evidence["schema"] == "TPAA_M1_FIXTURE_CONTRACT_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-TST-001"
    assert evidence["status"] == "PASS"
    assert evidence["fixture_count"] == 8
    fixture_ids = {item["fixture_id"] for item in evidence["fixtures"]}
    assert fixture_ids == EXPECTED_IDS
    assert all(item["data_classification"] == "SYNTHETIC" for item in evidence["fixtures"])
    assert all(item["review_state"] in {"REVIEWED", "APPROVED_GOLDEN"} for item in evidence["fixtures"])


def test_nominal_bundle_freezes_expected_generation_independence() -> None:
    expected = json.loads(
        (
            FIXTURE_ROOT
            / "BF_M1_NOMINAL_V1"
            / "expected"
            / "expected.json"
        ).read_text(encoding="utf-8")
    )
    generation = expected["expected_generation"]
    assert generation["method"] in {
        "human_recalculation",
        "independent_reference_script",
        "independent_reference_implementation",
    }
    assert generation["generated_from_implementation_under_test"] is False
    assert generation["independently_reviewable"] is True
    assert generation["reviewer"] == "@Sillies001"
    assert generation["independence_attestation"]


def _copy_bundle(tmp_path: Path, fixture_id: str = "BF_M1_FAILURE_V1") -> Path:
    source = FIXTURE_ROOT / fixture_id
    target = tmp_path / fixture_id
    shutil.copytree(source, target)
    return target


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("schema", "M1_FIXTURE_SCHEMA_MISMATCH"),
        ("version", "M1_FIXTURE_VERSION_UNSUPPORTED"),
        ("missing_source", "M1_FIXTURE_FILE_MISSING"),
        ("source_hash", "M1_FIXTURE_HASH_MISMATCH"),
    ],
)
def test_failure_fixture_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    bundle = _copy_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if mutation == "schema":
        manifest["schema"] = "CORRUPT"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
    elif mutation == "version":
        manifest["fixture_version"] = "999.0.0"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
    elif mutation == "missing_source":
        (bundle / "source" / "flight.json").unlink()
    elif mutation == "source_hash":
        source_path = bundle / "source" / "flight.json"
        source_path.write_text(
            source_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
    else:
        raise AssertionError(mutation)

    with pytest.raises(M1FixtureError) as exc_info:
        validate_bundle(bundle)
    assert exc_info.value.code == expected_code


def test_all_manifests_use_reproducible_input_hash_contract() -> None:
    for fixture_id in sorted(EXPECTED_IDS):
        manifest = json.loads(
            (FIXTURE_ROOT / fixture_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["input_hash_algorithm"] == "SHA256_PATH_SHA256_V1"
        assert manifest["expected_hash_algorithm"] == "SHA256_FILE_BYTES_V1"
        assert manifest["input_hash_basis"] == [
            "source/flight.json",
            "context/evaluation-context.json",
        ]
        assert len(manifest["input_sha256"]) == 64
        assert len(manifest["expected_sha256"]) == 64
