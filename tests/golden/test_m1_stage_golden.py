from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_episode import project_basic_flight_stage_quality

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"


@pytest.mark.parametrize("bundle", sorted(path for path in FIXTURES.iterdir() if path.is_dir()))
def test_four_stage_boundaries_match_independent_golden_exactly(bundle: Path) -> None:
    expected = json.loads((bundle / "expected" / "expected.json").read_text(encoding="utf-8"))
    projection = project_basic_flight_stage_quality(bundle, authority_root=AUTHORITY_ROOT)

    actual = [
        {
            "stage_type": stage.stage_type,
            "start_session_time_us": str(stage.start_session_time_us),
            "end_session_time_us": str(stage.end_session_time_us),
        }
        for stage in projection.stages
    ]
    assert actual == expected["stages"]
    assert [stage.stage_order for stage in projection.stages] == [0, 1, 2, 3]
    assert all(stage.stage_status == "VALID" for stage in projection.stages)
    assert all(stage.coverage == 1.0 for stage in projection.stages)
    assert all(stage.confidence == 1.0 for stage in projection.stages)
