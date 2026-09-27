from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_ingest.m2_measurement_alignment import (
    EXPECTED_METRIC_CODES,
    M2MeasurementAlignmentError,
    load_m2_measurement_alignment,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m2"


def test_nominal_measurement_alignment_is_replay_stable_and_complete() -> None:
    first = load_m2_measurement_alignment(FIXTURES / "MA_M2_NOMINAL_V1")
    second = load_m2_measurement_alignment(FIXTURES / "MA_M2_NOMINAL_V1")

    assert first == second
    assert first.status == "READY"
    assert first.reason_codes == ()
    assert first.coverage == 1.0
    assert first.max_observed_gap_us == 5000
    assert first.metric_codes == EXPECTED_METRIC_CODES
    assert first.quality_profile.profile_id == "M2_REFERENCE_MATCH_QUALITY_V1"
    assert first.quality_profile.profile_version == "1.1.0"
    assert (
        first.quality_profile.profile_hash
        == "904100e467f10e89aca1f06b1e9eeff86923121063ec9a41a2d73f84cc2400f1"
    )
    assert first.quality_profile.max_gap_us == 50000
    assert first.quality_profile.max_interpolation_age_us == 50000
    assert first.quality_profile.accepted_reference_quality_statuses == ("ACCEPTED",)
    assert first.quality_profile.required_uncertainty_components == (
        "reference_truth_uncertainty",
        "alignment_uncertainty",
        "sensor_measurement_uncertainty",
    )
    assert set(first.quality_profile.max_sigma_by_error_domain) == {
        "AZIMUTH",
        "CROSS_RANGE",
        "ELEVATION",
        "POSITION_3D",
        "RADIAL_POSITION",
        "RADIAL_VELOCITY",
        "RANGE",
        "VERTICAL_POSITION",
    }
    assert all(
        value is None
        for value in first.quality_profile.max_sigma_by_error_domain.values()
    )
    assert len(first.rows) == 3
    assert {row.match_status for row in first.rows} == {"MATCHED"}
    assert all(row.measurement_error == 5.0 for row in first.rows)
    assert all(row.reference_truth_uncertainty == 3.0 for row in first.rows)
    assert all(row.alignment_uncertainty == 1.0 for row in first.rows)
    assert all(row.sensor_measurement_uncertainty == 2.0 for row in first.rows)
    assert all(
        set(row.uncertainty_provenance)
        == {
            "alignment_uncertainty_ref",
            "reference_uncertainty_ref",
            "sensor_measurement_uncertainty_ref",
        }
        for row in first.rows
    )
    assert not first.metric_logic_executed
    assert not first.stage_projection_executed
    assert not first.persistence_executed
    assert not first.publication_executed


def test_gap_fixture_preserves_quality_failure_without_fabricating_match() -> None:
    projection = load_m2_measurement_alignment(FIXTURES / "MA_M2_GAP_V1")

    assert projection.status == "INSUFFICIENT"
    assert projection.reason_codes == ("MAX_GAP_EXCEEDED", "MIN_COVERAGE_NOT_MET")
    assert projection.coverage == pytest.approx(2 / 3)
    assert projection.max_observed_gap_us == 200000
    assert [row.match_status for row in projection.rows] == [
        "MATCHED",
        "REJECTED_QUALITY",
        "MATCHED",
    ]


def test_measurement_alignment_fails_closed_on_source_hash_drift(tmp_path: Path) -> None:
    bundle = tmp_path / "MA_M2_NOMINAL_V1"
    source_dir = bundle / "source"
    source_dir.mkdir(parents=True)
    original = FIXTURES / "MA_M2_NOMINAL_V1"
    (bundle / "manifest.json").write_bytes((original / "manifest.json").read_bytes())
    source = (original / "source" / "measurement-alignment.json").read_text(encoding="utf-8")
    (source_dir / "measurement-alignment.json").write_text(
        source.replace('"measured_range_m": 1005', '"measured_range_m": 1006', 1),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(M2MeasurementAlignmentError) as exc:
        load_m2_measurement_alignment(bundle)
    assert exc.value.code == "M2_MEASUREMENT_ALIGNMENT_SOURCE_HASH_MISMATCH"
