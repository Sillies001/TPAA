from __future__ import annotations

import json
from pathlib import Path

from tpaa_ingest.m2_measurement_alignment import (
    EXPECTED_MEASUREMENT_AUTHORITY,
    EXPECTED_METRIC_CODES,
    EXPECTED_REFERENCE_MATCH_QUALITY_CONTRACT,
    EXPECTED_REFERENCE_RELATIVE_STATE_CONTRACT,
    load_m2_measurement_alignment,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURES = ROOT / "tests" / "fixtures" / "m2"


def test_data_004_metric_input_authority_scope_is_exact() -> None:
    matrix = json.loads(
        (AUTHORITY / "METRIC_INPUT_AUTHORITY_MATRIX.json").read_text(encoding="utf-8")
    )
    codes = set(EXPECTED_METRIC_CODES)
    bindings = [row for row in matrix["bindings"] if row["metric_code"] in codes]

    assert codes == {"P1-QA-006", *(f"P1-SNS-{index:03d}" for index in range(5, 22))}
    assert {row["metric_code"] for row in bindings} == codes
    assert EXPECTED_MEASUREMENT_AUTHORITY in {row["authority_id"] for row in bindings}
    assert EXPECTED_REFERENCE_RELATIVE_STATE_CONTRACT in {
        row["authority_id"] for row in bindings
    }
    assert EXPECTED_REFERENCE_MATCH_QUALITY_CONTRACT in {
        row["authority_id"] for row in bindings
    }


def test_data_004_fixture_provenance_and_subject_links_are_exact() -> None:
    projection = load_m2_measurement_alignment(FIXTURES / "MA_M2_NOMINAL_V1")

    assert projection.session_id == "11111111-1111-4111-8111-111111111111"
    assert (
        projection.mission_system_instance_id
        == "77777777-7777-4777-8777-777777777701"
    )
    assert projection.target_pair_id == (
        "22222222-2222-4222-8222-222222222222:"
        "33333333-3333-4333-8333-333333333333"
    )
    assert len(projection.reference_truth_logical_hash) == 64
    assert len(projection.mission_system_logical_hash) == 64
    assert len(projection.logical_hash) == 64
    assert projection.quality_profile.profile_id == "M2_REFERENCE_MATCH_QUALITY_V1"
    assert projection.quality_profile.profile_version == "1.0.0"
    assert len(projection.quality_profile.profile_hash) == 64
