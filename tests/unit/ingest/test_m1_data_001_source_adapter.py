from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tpaa_ingest import (
    SyntheticSourceAdapterError,
    load_synthetic_fixture_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "m1"


def _copy_bundle(
    tmp_path: Path,
    fixture_id: str = "BF_M1_NOMINAL_V1",
) -> Path:
    target = tmp_path / fixture_id
    shutil.copytree(FIXTURES / fixture_id, target)
    return target


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_nominal_bundle_exposes_stable_source_identity_and_mapping() -> None:
    bundle = load_synthetic_fixture_bundle(FIXTURES / "BF_M1_NOMINAL_V1")

    assert bundle.identity.fixture_id == "BF_M1_NOMINAL_V1"
    assert bundle.identity.fixture_version == "1.0.0"
    assert (
        bundle.identity.source_sha256
        == "513ba5592d156ef668cd271af6cb97e2f90a6c814822920736f5ae921fa00b8d"
    )
    assert (
        bundle.identity.context_sha256
        == "a8e7036cf86a3ab63ee8447013d8e01ddf61de682009ee771d3f68017aad8096"
    )
    assert (
        bundle.identity.input_sha256
        == "ca649b252e37639206e420930933c76637bd249f27e3bb8a925747274886c91c"
    )
    assert bundle.identity.stable_source_ref == (
        "M1_FIXTURE:BF_M1_NOMINAL_V1:1.0.0:"
        "513ba5592d156ef668cd271af6cb97e2f90a6c814822920736f5ae921fa00b8d"
    )
    assert bundle.data_classification == "SYNTHETIC"
    assert bundle.mapping_version == "M1_BASIC_FLIGHT_SOURCE_MAP_V1"
    assert bundle.physical_to_canonical_mapping["p"] == "body_p_rad_s"
    assert bundle.physical_to_canonical_mapping["quality"] == "quality_mask"


def test_adapter_preserves_source_clock_for_m1_data_003() -> None:
    bundle = load_synthetic_fixture_bundle(FIXTURES / "BF_M1_NOMINAL_V1")

    assert bundle.session.source_time_basis == "SOURCE_US"
    assert bundle.rows[0].source_time_us == "0"
    assert bundle.rows[-1].source_time_us == "7000000"
    assert bundle.session.end_source_time_us == "8000000"

    # M1-DATA-001 deliberately does not apply the context +1,000,000 us
    # Session-Time transform; that remains the M1-DATA-003 responsibility.
    assert bundle.rows[0].source_time_us != "1000000"


def test_adapter_preserves_partial_missing_values_without_zero_coercion() -> None:
    bundle = load_synthetic_fixture_bundle(
        FIXTURES / "BF_M1_STRUCTURED_PARTIAL_V1"
    )

    assert bundle.rows[0].values["tas"] == 100
    assert bundle.rows[0].values["mach"] is None
    assert bundle.rows[1].values["tas"] is None
    assert bundle.rows[1].values["mach"] == 0.31


def test_adapter_preserves_source_markers_without_projecting_stage_intervals() -> None:
    bundle = load_synthetic_fixture_bundle(FIXTURES / "BF_M1_NOMINAL_V1")

    assert [(item.source_time_us, item.marker_value) for item in bundle.source_markers] == [
        ("0", "SETUP_ENTRY"),
        ("2000000", "EXECUTION"),
        ("4000000", "STABILIZATION_RECOVERY"),
        ("6000000", "COMPLETION"),
        ("8000000", "END"),
    ]


def test_uncontrolled_classification_fails_closed(tmp_path: Path) -> None:
    bundle = _copy_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["data_classification"] = "OPERATIONAL"
    _write_json(manifest_path, manifest)

    with pytest.raises(SyntheticSourceAdapterError) as caught:
        load_synthetic_fixture_bundle(bundle)

    assert caught.value.code == "M1_SOURCE_ADAPTER_CLASSIFICATION_FORBIDDEN"


def test_changed_source_bytes_fail_before_source_is_exposed(tmp_path: Path) -> None:
    bundle = _copy_bundle(tmp_path)
    source_path = bundle / "source" / "flight.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["rows"][0]["p"] = 999.0
    _write_json(source_path, source)

    with pytest.raises(SyntheticSourceAdapterError) as caught:
        load_synthetic_fixture_bundle(bundle)

    assert caught.value.code == "M1_SOURCE_ADAPTER_SOURCE_HASH_MISMATCH"


def test_unknown_fixture_identity_fails_closed(tmp_path: Path) -> None:
    bundle = _copy_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fixture_id"] = "BF_M1_UNCONTROLLED_V1"
    _write_json(manifest_path, manifest)

    with pytest.raises(SyntheticSourceAdapterError) as caught:
        load_synthetic_fixture_bundle(bundle)

    assert caught.value.code == "M1_SOURCE_ADAPTER_FIXTURE_NOT_GOVERNED"


def test_mapping_metadata_drift_fails_closed(tmp_path: Path) -> None:
    bundle = _copy_bundle(tmp_path)
    source_path = bundle / "source" / "flight.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["mapping"]["p"] = "roll_rate_guess"
    _write_json(source_path, source)

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    import hashlib

    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    manifest["files"]["source"]["sha256"] = source_sha
    context_sha = manifest["files"]["context"]["sha256"]
    basis = (
        f"source/flight.json={source_sha}\n"
        f"context/evaluation-context.json={context_sha}\n"
    ).encode("ascii")
    manifest["input_sha256"] = hashlib.sha256(basis).hexdigest()
    _write_json(manifest_path, manifest)

    with pytest.raises(SyntheticSourceAdapterError) as caught:
        load_synthetic_fixture_bundle(bundle)

    assert caught.value.code == "M1_SOURCE_ADAPTER_MAPPING_MISMATCH"


def test_context_classification_fails_closed_even_when_hashes_are_refreshed(
    tmp_path: Path,
) -> None:
    import hashlib

    bundle = _copy_bundle(tmp_path)
    context_path = bundle / "context" / "evaluation-context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["classification"] = "OPERATIONAL"
    _write_json(context_path, context)

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    context_sha = hashlib.sha256(context_path.read_bytes()).hexdigest()
    manifest["files"]["context"]["sha256"] = context_sha
    source_sha = manifest["files"]["source"]["sha256"]
    basis = (
        f"source/flight.json={source_sha}\n"
        f"context/evaluation-context.json={context_sha}\n"
    ).encode("ascii")
    manifest["input_sha256"] = hashlib.sha256(basis).hexdigest()
    _write_json(manifest_path, manifest)

    with pytest.raises(SyntheticSourceAdapterError) as caught:
        load_synthetic_fixture_bundle(bundle)

    assert caught.value.code == "M1_SOURCE_ADAPTER_CLASSIFICATION_FORBIDDEN"


def test_authority_hash_drift_fails_before_source_is_exposed(tmp_path: Path) -> None:
    bundle = _copy_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["authority_refs"]["stage_registry_sha256"] = "0" * 64
    _write_json(manifest_path, manifest)

    with pytest.raises(SyntheticSourceAdapterError) as caught:
        load_synthetic_fixture_bundle(bundle)

    assert caught.value.code == "M1_SOURCE_ADAPTER_AUTHORITY_MISMATCH"
