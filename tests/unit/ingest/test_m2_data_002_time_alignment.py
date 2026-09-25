from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tpaa_ingest import M2TimeAlignmentError, load_m2_time_alignment

REPO_ROOT = Path(__file__).resolve().parents[3]
NOMINAL = REPO_ROOT / "tests" / "fixtures" / "m2" / "TA_M2_NOMINAL_V1"
INVALID = REPO_ROOT / "tests" / "fixtures" / "m2" / "TA_M2_INVALID_UNRESOLVED_V1"


def _copy_fixture(source: Path, tmp_path: Path) -> Path:
    target = tmp_path / source.name
    shutil.copytree(source, target)
    return target


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_time_alignment_projection_preserves_all_frozen_input_fields() -> None:
    projection = load_m2_time_alignment(NOMINAL)

    assert projection.fixture_id == "TA_M2_NOMINAL_V1"
    assert projection.session_time_basis == "TPAA_SESSION_US"
    assert projection.profile_id == "M2_QA_FOUNDATION_PROFILE_V1"
    assert projection.max_gap_us == 60_000
    assert [segment.segment_id for segment in projection.clock_segments] == [
        "seg-a",
        "seg-b",
    ]
    assert projection.clock_segments[0].records[0].sensor_timestamp_mapped_to_session_time_us == (
        1_000_000
    )
    assert projection.clock_segments[0].records[0].aligned_session_time_us == 1_002_000
    assert projection.latency_records[0].sensor_measurement_effective_time_us == 1_040_000
    assert projection.latency_records[0].referenced_ownship_state_effective_time_us == (
        1_000_000
    )
    assert projection.interpolation_records[0].measurement_time_us == 1_050_000
    assert projection.interpolation_records[0].left_truth_time_us == 1_000_000
    assert projection.interpolation_records[0].right_truth_time_us == 1_100_000


def test_time_alignment_projection_preserves_uncertainty_provenance() -> None:
    projection = load_m2_time_alignment(NOMINAL)
    refs = {record.reference_name: record for record in projection.uncertainty_records}

    assert refs["ownship_nav_time_uncertainty_ref"].representation == (
        "TWO_SIDED_HARD_BOUND"
    )
    assert refs["ownship_nav_time_uncertainty_ref"].bound_us == 500
    assert refs["ownship_nav_time_uncertainty_ref"].provenance_ref == "ins-clock:own:v1"
    assert refs["target_nav_time_uncertainty_ref"].bound_us == 800
    assert projection.ownship_clock_transform_residual_sigma_us == 100
    assert projection.target_clock_transform_residual_sigma_us == 200


def test_time_alignment_projection_is_replay_stable_and_not_metric_execution() -> None:
    first = load_m2_time_alignment(NOMINAL)
    second = load_m2_time_alignment(NOMINAL)

    assert first == second
    assert first.logical_hash == second.logical_hash
    assert len(first.logical_hash) == 64
    assert first.metric_logic_executed is False
    assert first.stage_projection_executed is False
    assert first.persistence_executed is False


def test_unresolved_time_transform_fixture_fails_closed() -> None:
    with pytest.raises(M2TimeAlignmentError) as caught:
        load_m2_time_alignment(INVALID)

    assert caught.value.code == "M2_TIME_ALIGNMENT_TIME_TRANSFORM_UNRESOLVED"


def test_changed_source_bytes_fail_closed_before_projection(tmp_path: Path) -> None:
    fixture = _copy_fixture(NOMINAL, tmp_path)
    path = fixture / "source" / "time-alignment.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    source["latency_records"][0]["sensor_measurement_effective_time_us"] = 9_999_999
    _write_json(path, source)

    with pytest.raises(M2TimeAlignmentError) as caught:
        load_m2_time_alignment(fixture)

    assert caught.value.code == "M2_TIME_ALIGNMENT_SOURCE_HASH_MISMATCH"


def test_authority_drift_fails_closed(tmp_path: Path) -> None:
    fixture = _copy_fixture(NOMINAL, tmp_path)
    path = fixture / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["authority_refs"]["metric_codes"] = ["P1-QA-003"]
    _write_json(path, manifest)

    with pytest.raises(M2TimeAlignmentError) as caught:
        load_m2_time_alignment(fixture)

    assert caught.value.code == "M2_TIME_ALIGNMENT_AUTHORITY_MISMATCH"
