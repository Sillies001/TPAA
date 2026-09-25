from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tpaa_ingest import M2ReferenceTruthError, load_m2_reference_truth

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "m2" / "RT_M2_NOMINAL_V1"


def _copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "RT_M2_NOMINAL_V1"
    shutil.copytree(FIXTURE, target)
    return target


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_reference_truth_projection_preserves_pair_identity_frames_and_time() -> None:
    projection = load_m2_reference_truth(FIXTURE)

    assert projection.fixture_id == "RT_M2_NOMINAL_V1"
    assert projection.own_identity.source_entity_key == "OWN-REF-01"
    assert projection.target_identity.source_entity_key == "TARGET-REF-01"
    assert projection.frame_provenance.position_frame == "ECEF"
    assert projection.frame_provenance.velocity_frame == "ECEF"
    assert projection.frame_provenance.own_attitude_frame_ref == (
        "reference-frame:own-attitude:v1"
    )
    assert [row.source_time_us for row in projection.rows] == [0, 1_000_000, 2_000_000]
    assert [row.session_time_us for row in projection.rows] == [
        1_000_000,
        2_000_000,
        3_000_000,
    ]


def test_projection_preserves_reference_vectors_jacobian_and_uncertainty_refs() -> None:
    projection = load_m2_reference_truth(FIXTURE)
    first = projection.rows[0]

    assert first.own_position_ecef_m == (6_378_137.0, 0.0, 0.0)
    assert first.target_position_ecef_m == (6_378_137.0, 1_000.0, 100.0)
    assert first.own_velocity_ecef_mps == (0.0, 200.0, 0.0)
    assert first.target_velocity_ecef_mps == (0.0, 180.0, 0.0)
    assert first.own_attitude_quat == (1.0, 0.0, 0.0, 0.0)
    assert first.sensor_boresight_quat is None
    assert first.relative_state_jacobian == (
        (1.0, 0.0, 0.0, -1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, -1.0),
    )
    assert first.uncertainty_refs["own_position_uncertainty_ref"] == (
        "navu:own-position:v1"
    )
    assert first.uncertainty_refs["target_position_uncertainty_ref"] == (
        "navu:target-position:v1"
    )
    assert first.uncertainty_refs["time_alignment_uncertainty_ref"] == (
        "navu:time-alignment:v1"
    )
    assert set(first.uncertainty_refs.values()) <= set(projection.uncertainty_records)


def test_projection_is_replay_stable_and_does_not_cross_m2_batch_boundary() -> None:
    first = load_m2_reference_truth(FIXTURE)
    second = load_m2_reference_truth(FIXTURE)

    assert first == second
    assert first.logical_hash == second.logical_hash
    assert len(first.logical_hash) == 64
    assert first.metric_logic_executed is False
    assert first.stage_projection_executed is False
    assert first.persistence_executed is False


def test_changed_source_bytes_fail_closed_before_projection(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    path = fixture / "source" / "reference-truth.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    source["records"][0]["target"]["position_ecef_m"][1] = 9_999
    _write_json(path, source)

    with pytest.raises(M2ReferenceTruthError) as caught:
        load_m2_reference_truth(fixture)

    assert caught.value.code == "M2_REFERENCE_TRUTH_SOURCE_HASH_MISMATCH"


def test_authority_drift_fails_closed(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    path = fixture / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["authority_refs"]["metric_codes"] = ["P1-QA-001"]
    _write_json(path, manifest)

    with pytest.raises(M2ReferenceTruthError) as caught:
        load_m2_reference_truth(fixture)

    assert caught.value.code == "M2_REFERENCE_TRUTH_AUTHORITY_MISMATCH"
