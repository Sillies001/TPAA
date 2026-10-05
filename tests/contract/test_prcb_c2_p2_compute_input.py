from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_p2_precompute_inputs_are_durable_and_fixture_free() -> None:
    source = (
        ROOT / "src" / "tpaa_application" / "p2_persistence.py"
    ).read_text(encoding="utf-8")
    assert "TPAA_P2_DURABLE_COMPUTE_INPUT_V1" in source
    assert "def exact_compute_input(" in source
    assert "cohort_feature_sets" in source
    assert "reference_factor_values" in source
    assert "tests/fixtures" not in source
